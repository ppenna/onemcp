#!/bin/bash

set -euo pipefail

CALCULATOR_README=$(wget -qO- https://raw.githubusercontent.com/githejie/mcp-server-calculator/refs/heads/main/README.md | sed ':a;N;$!ba;s/\n/\\n/g')

DISCOVER_JSON=$(jq -n \
    --arg repository_url  "https://github.com/githejie/mcp-server-calculator" \
    --arg repository_readme  "${CALCULATOR_README}" \
    '{repository_url: $repository_url, repository_readme: $repository_readme}'
)
curl \
  -X POST \
  --header "Content-Type: application/json" \
  --header "X-OneMCP-Message-Type: DISCOVER" \
  --data "${DISCOVER_JSON}" \
  http://localhost:8080/sandbox
