#!/bin/bash

set -euo pipefail

echo -n "Sending START request..."
setup_script=$(cat assets/test/explored-mcp-server.json | jq -r .bootstrap_metadata.setup_script)
repository_url=$(cat assets/test/explored-mcp-server.json | jq -r .bootstrap_metadata.repository_url)
START_JSON=$(jq -n \
    --arg repository_url "$repository_url" \
    --arg setup_script "$setup_script" \
    '{bootstrap_metadata: {repository_url: $repository_url, setup_script: $setup_script}}'
)
SANDBOX_ID=$(curl \
  --silent \
  -X POST \
  --header "Content-Type: application/json" \
  --header "X-OneMCP-Message-Type: START" \
  --data "${START_JSON}" \
  http://localhost:8080/sandbox | jq -r .sandbox_id)

echo "got sandbox ID: ${SANDBOX_ID}!"

sleep 2

echo "Getting the tools from the MCP..."
TOOLS_JSON=$(jq -n \
    --arg sandbox_id  "${SANDBOX_ID}" \
    '{sandbox_id: $sandbox_id}'
)
TOOLS_RESPONSE=$(curl \
  --silent \
  -X POST \
  --header "Content-Type: application/json" \
  --header "X-OneMCP-Message-Type: GET_TOOLS" \
  --data "${TOOLS_JSON}" \
  http://localhost:8080/sandbox)

sleep 2

# WARNING: This would be the request sent by the LLM plus the sandbox_id
# field. The orchestrator will have to unpack the JSON, and package it again.
echo -n "Calling 'calculate' '0.5 + 0.25'..."
CALL_TOOL_JSON=$(jq -n \
  --arg sandbox_id  "${SANDBOX_ID}" \
  --arg expression "0.5 + 0.25" \
  '{
    sandbox_id: $sandbox_id,
    jsonrpc: "2.0",
    id: 1,
    method: "tools/call",
    params: {
      name: "calculate",
      arguments: { expression: $expression }
    }
  }'
)
RESULT=$(curl \
  --silent \
  -X POST \
  --header "Content-Type: application/json" \
  --header "X-OneMCP-Message-Type: CALL_TOOL" \
  --data "${CALL_TOOL_JSON}" \
  http://localhost:8080/sandbox | jq -r .response.result.structuredContent.result)
echo "got result: ${RESULT}!"

sleep 2

echo -n "Stopping sandbox..."
STOP_JSON=$(jq -n \
    --arg sandbox_id  "${SANDBOX_ID}" \
    '{sandbox_id: $sandbox_id}'
)
STOP_RESPONSE=$(curl \
  --silent \
  -X POST \
  --header "Content-Type: application/json" \
  --header "X-OneMCP-Message-Type: STOP" \
  --data "${STOP_JSON}" \
  http://localhost:8080/sandbox)
echo "success!"
