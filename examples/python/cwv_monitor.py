"""Track Core Web Vitals (lab) for a list of URLs and append them to a CSV, one row per URL per run.

    pip install requests
    export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
    python cwv_monitor.py urls.txt --device mobile          # one URL per line
    python cwv_monitor.py https://www.wikipedia.org/ --device desktop

Run it daily (cron, GitHub Actions) and chart core_web_vitals.csv. Each URL costs $0.0055;
blocked or unreachable pages are logged with their error and not charged.
Ratings use Google's thresholds: LCP <= 2.5 s, CLS <= 0.1 are good; Total Blocking Time is the lab
stand-in for responsiveness (<= 200 ms good, as Lighthouse scores it).
"""
import argparse
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

API = "https://data.semust.com"
HEADERS = {
    "SEMUST-API-USER": os.environ["SEMUST_API_USER"],
    "SEMUST-API-PASSWORD": os.environ["SEMUST_API_PASSWORD"],
}
WAIT = 60
COLUMNS = ["checked_at", "url", "device", "performance", "lcp_ms", "cls", "tbt_ms", "fcp_ms",
           "lcp_rating", "cls_rating", "tbt_rating", "error"]
# metric: (good up to, poor above)
THRESHOLDS = {"lcp_ms": (2500, 4000), "cls": (0.1, 0.25), "tbt_ms": (200, 600)}


def call(path, payload):
    resp = requests.post(f"{API}{path}", params={"wait": WAIT}, json=payload,
                         headers=HEADERS, timeout=WAIT + 30)
    while resp.status_code == 202:
        task = resp.json()
        time.sleep(int(resp.headers.get("Retry-After", 5)))
        resp = requests.get(task["poll_url"], headers=HEADERS, timeout=30)
    return resp


def rating(metric, value):
    if value is None:
        return ""
    good, poor = THRESHOLDS[metric]
    return "good" if value <= good else "poor" if value > poor else "needs-improvement"


def measure(url, device):
    row = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "url": url, "device": device}
    try:
        # Only the performance category: the price is the same, the run is shorter.
        resp = call("/v1/on-page", {"type": "lighthouse", "url": url, "device": device,
                                    "categories": ["performance"]})
    except requests.RequestException as e:
        return {**row, "error": str(e)}
    if resp.status_code != 200:
        return {**row, "error": f"{resp.status_code} {resp.text[:200].strip()}"}

    data = resp.json()["data"]
    m = data["metrics"] or {}
    row.update({
        "performance": data["scores"]["performance"],
        "lcp_ms": m.get("largest_contentful_paint_ms"),
        "cls": m.get("cumulative_layout_shift"),
        "tbt_ms": m.get("total_blocking_time_ms"),
        "fcp_ms": m.get("first_contentful_paint_ms"),
    })
    for metric in THRESHOLDS:
        row[metric.split("_")[0] + "_rating"] = rating(metric, row[metric])
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+", help="URLs, or a text file with one URL per line")
    ap.add_argument("--device", default="mobile", choices=["mobile", "desktop"])
    ap.add_argument("--out", default="core_web_vitals.csv")
    ap.add_argument("--workers", type=int, default=3, help="parallel requests")
    args = ap.parse_args()

    urls = []
    for item in args.urls:
        path = Path(item)
        if path.is_file():
            urls += [line.strip() for line in path.read_text().splitlines()
                     if line.strip() and not line.startswith("#")]
        else:
            urls.append(item)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda u: measure(u, args.device), urls))

    new_file = not Path(args.out).exists()
    with open(args.out, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)

    for r in rows:
        if r.get("error"):
            print(f"{r['url']}\n    error: {r['error']}")
        else:
            print(f"{r['url']}\n    perf {r['performance']} · LCP {r['lcp_ms']} ms ({r['lcp_rating']}) · "
                  f"CLS {r['cls']} ({r['cls_rating']}) · TBT {r['tbt_ms']} ms ({r['tbt_rating']})")
    print(f"\n{len(rows)} rows appended to {args.out}")


if __name__ == "__main__":
    main()
