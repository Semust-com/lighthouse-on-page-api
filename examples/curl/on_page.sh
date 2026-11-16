#!/usr/bin/env bash
# Run Lighthouse on a page with the Semust Lighthouse & On-Page API.
#   export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
#   ./on_page.sh
# A request still running after `wait` seconds answers 202; poll the task with the second command.
set -euo pipefail

curl -sS -X POST "https://data.semust.com/v1/on-page?wait=60" \
  --max-time 90 \
  -H "Content-Type: application/json" \
  -H "SEMUST-API-USER: ${SEMUST_API_USER}" \
  -H "SEMUST-API-PASSWORD: ${SEMUST_API_PASSWORD}" \
  -d '{
    "type": "lighthouse",
    "url": "https://www.wikipedia.org/",
    "device": "desktop"
  }'

# The other reports use the same endpoint:
#   -d '{"type": "audit", "url": "https://www.wikipedia.org/"}'
#   -d '{"type": "content", "url": "https://www.wikipedia.org/", "markdown": true}'

# If you received 202, fetch the result with the task_id from the response:
# curl -sS "https://data.semust.com/v1/tasks/$TASK_ID" \
#   -H "SEMUST-API-USER: ${SEMUST_API_USER}" -H "SEMUST-API-PASSWORD: ${SEMUST_API_PASSWORD}"
