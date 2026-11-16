<?php
// Run Lighthouse on a page with the Semust Lighthouse & On-Page API (PHP 7.4+ with the curl extension).
//
//   export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
//   php on_page.php https://www.wikipedia.org/ desktop

const API = "https://data.semust.com";
const WAIT = 60; // seconds the API holds the request open before answering 202

function request(string $method, string $url, ?array $payload = null): array
{
    $ch = curl_init($url);
    $headers = [];
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => WAIT + 30,
        CURLOPT_HTTPHEADER => [
            "Content-Type: application/json",
            "SEMUST-API-USER: " . getenv("SEMUST_API_USER"),
            "SEMUST-API-PASSWORD: " . getenv("SEMUST_API_PASSWORD"),
        ],
        CURLOPT_HEADERFUNCTION => function ($ch, $line) use (&$headers) {
            $parts = explode(":", $line, 2);
            if (count($parts) === 2) {
                $headers[strtolower(trim($parts[0]))] = trim($parts[1]);
            }
            return strlen($line);
        },
    ]);
    if ($payload !== null) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
    }
    $body = curl_exec($ch);
    if ($body === false) {
        fwrite(STDERR, "Request failed: " . curl_error($ch) . "\n");
        exit(1);
    }
    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return [$status, $headers, $body];
}

// POST a request and return the final response, polling if the API answers 202.
function call(string $path, array $payload): array
{
    [$status, $headers, $body] = request("POST", API . $path . "?wait=" . WAIT, $payload);
    while ($status === 202) {
        $task = json_decode($body, true);
        sleep((int)($headers["retry-after"] ?? 5));
        [$status, $headers, $body] = request("GET", $task["poll_url"]);
    }
    return [$status, $body];
}

$url = $argv[1] ?? "https://www.wikipedia.org/";
$device = $argv[2] ?? "desktop";
[$status, $body] = call("/v1/on-page", [
    "type" => "lighthouse", // or "audit" / "content"
    "url" => $url,
    "device" => $device, // "mobile" (the API default) or "desktop"
]);

if ($status !== 200) {
    fwrite(STDERR, "Error {$status}: {$body}\n");
    exit(1);
}

$result = json_decode($body, true);
$data = $result["data"];
printf("%s · %s · Lighthouse %s\n", $data["final_url"], $device, $data["lighthouse_version"]);
foreach ($data["scores"] as $category => $score) {
    if ($score !== null) {
        printf("  %-15s %3d\n", $category, $score);
    }
}
if ($m = $data["metrics"]) {
    printf("\n  LCP %s ms · CLS %s · TBT %s ms\n",
        $m["largest_contentful_paint_ms"], $m["cumulative_layout_shift"], $m["total_blocking_time_ms"]);
}
foreach ($data["failed_audits"] as $a) {
    printf("  [%s] %s%s\n", $a["category"], $a["title"], $a["display_value"] ? " ({$a["display_value"]})" : "");
}
printf("\nCost: $%s\n", $result["cost"]);
