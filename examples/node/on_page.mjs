// Run Lighthouse on a page with the Semust Lighthouse & On-Page API (Node.js 18+, no dependencies).
//
//   export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
//   node on_page.mjs https://www.wikipedia.org/ desktop

const API = "https://data.semust.com";
const HEADERS = {
  "Content-Type": "application/json",
  "SEMUST-API-USER": process.env.SEMUST_API_USER,
  "SEMUST-API-PASSWORD": process.env.SEMUST_API_PASSWORD,
};
const WAIT = 60; // seconds the API holds the request open before answering 202

const sleep = (s) => new Promise((r) => setTimeout(r, s * 1000));

// POST a request and return the final response, polling if the API answers 202.
async function call(path, payload) {
  let resp = await fetch(`${API}${path}?wait=${WAIT}`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout((WAIT + 30) * 1000),
  });
  while (resp.status === 202) {
    const task = await resp.json();
    await sleep(Number(resp.headers.get("Retry-After") ?? 5));
    resp = await fetch(task.poll_url, { headers: HEADERS });
  }
  return resp;
}

const url = process.argv[2] ?? "https://www.wikipedia.org/";
const device = process.argv[3] ?? "desktop";
const resp = await call("/v1/on-page", {
  type: "lighthouse", // or "audit" / "content"
  url,
  device, // "mobile" (the API default) or "desktop"
});

if (resp.status !== 200) {
  console.error(`Error ${resp.status}: ${await resp.text()}`);
  process.exit(1);
}

const { data, cost } = await resp.json();
console.log(`${data.final_url} · ${device} · Lighthouse ${data.lighthouse_version}`);
for (const [category, score] of Object.entries(data.scores)) {
  if (score !== null) console.log(`  ${category.padEnd(15)} ${String(score).padStart(3)}`);
}
const m = data.metrics;
if (m) {
  console.log(`\n  LCP ${m.largest_contentful_paint_ms} ms · CLS ${m.cumulative_layout_shift} · TBT ${m.total_blocking_time_ms} ms`);
}
for (const a of data.failed_audits) {
  console.log(`  [${a.category}] ${a.title}${a.display_value ? ` (${a.display_value})` : ""}`);
}
console.log(`\nCost: $${cost}`);
