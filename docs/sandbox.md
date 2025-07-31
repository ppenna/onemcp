## Sandbox Subsystem

To run the sandbox HTTP server, from the root of the directory, run:

```bash
python3 -m src.onemcp.sandbox
```

to test the discover API, you may run:

```bash
DISCOVER_JSON=$(jq -n \
    --arg repository_url "https://github.com/githejie/mcp-server-calculator" \
    '{repository_url: $repository_url}'
)
curl \
  -X POST \
  --header "Content-Type: application/json" \
  --header "X-OneMCP-Message-Type: DISCOVER" \
  --data "${DISCOVER_JSON}" \
  http://localhost:8080/sandbox
```
