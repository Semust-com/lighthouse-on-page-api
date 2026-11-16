"""Run Lighthouse on a page with the Semust Lighthouse & On-Page API.

    pip install requests
    export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
    python on_page.py https://www.wikipedia.org/ desktop
"""
import json
import os
import sys
import time

import requests

API = "https://data.semust.com"
HEADERS = {
    "SEMUST-API-USER": os.environ["SEMUST_API_USER"],
    "SEMUST-API-PASSWORD": os.environ["SEMUST_API_PASSWORD"],
}
WAIT = 60  # seconds the API holds the request open before answering 202


def call(path, payload):
    """POST a request and return the final response, polling if the API answers 202."""
    resp = requests.post(f"{API}{path}", params={"wait": WAIT}, json=payload,
                         headers=HEADERS, timeout=WAIT + 30)
    while resp.status_code == 202:
        task = resp.json()
        time.sleep(int(resp.headers.get("Retry-After", 5)))
        resp = requests.get(task["poll_url"], headers=HEADERS, timeout=30)
    return resp


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.wikipedia.org/"
    device = sys.argv[2] if len(sys.argv) > 2 else "desktop"
    resp = call("/v1/on-page", {
        "type": "lighthouse",   # or "audit" (on-page SEO audit) / "content" (main text, Markdown)
        "url": url,
        "device": device,       # "mobile" (the API default) or "desktop"
        # "categories": ["performance", "seo"],  # default: all four
        # "language": "en",                      # language of audit titles and descriptions
    })
    if resp.status_code != 200:
        sys.exit(f"Error {resp.status_code}: {resp.text}")

    result = resp.json()
    data = result["data"]
    print(f"{data['final_url']} · {device} · Lighthouse {data['lighthouse_version']}")
    for category, score in data["scores"].items():
        if score is not None:
            print(f"  {category:<15} {score:>3}")

    m = data["metrics"]
    if m:
        print(f"\n  LCP {m['largest_contentful_paint_ms']} ms · CLS {m['cumulative_layout_shift']} · "
              f"TBT {m['total_blocking_time_ms']} ms · FCP {m['first_contentful_paint_ms']} ms")

    print(f"\n{data['failed_count']} failed audits:")
    for audit in data["failed_audits"]:
        extra = f" ({audit['display_value']})" if audit["display_value"] else ""
        print(f"  [{audit['category']}] {audit['title']}{extra}")

    with open("on_page_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nCost: ${result['cost']} · full response saved to on_page_result.json")


if __name__ == "__main__":
    main()
