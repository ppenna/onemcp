# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import sys
import time
from dataclasses import dataclass
from typing import Any

from onemcp.sandbox.docker.sandbox import DockerContainer


@dataclass
class McpServer:
    """Represents a running sandbox instance."""

    endpoint: str
    status: str = "running"

    # Basic MCP JSON-RPC messages
    def _initialize(self, protocol_version: str = "2024-11-05") -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "cli-mcp", "version": "0.1"},
            },
        }

    def _notif_initialized(self) -> dict[str, str]:
        return {"jsonrpc": "2.0", "method": "notifications/initialized"}

    def _tools_list(self) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    def send(self, proc: DockerContainer, obj: dict[str, Any]) -> None:
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        proc.write(line)

    def _read_until_id(self, proc: DockerContainer, expect_id: int, timeout: float = 5.0) -> dict[str, Any]:
        """
        This is an internal method used to read from the stdin of a running
        docker container until we see a JSON-RPC response with a given id.

        It must only be called from inside this class.
        """
        start = time.time()
        while True:
            if time.time() - start > timeout:
                raise TimeoutError(f"Timed out waiting for response id={expect_id}")
            line = proc.read()
            if not line:
                # Process may be buffering; small sleep and try again
                time.sleep(0.01)
                continue
            line = line.strip()
            print(f"read line: {line}")
            if not line:
                continue
            try:
                msg = json.loads(line)
                print(f"message: {msg}")
            except json.JSONDecodeError:
                # Server printed non-JSON text; ignore or print to stderr
                print(f"[server-stdout] {line}", file=sys.stderr)
                continue
            if isinstance(msg, dict) and msg.get("id") == expect_id:
                return msg
            # You may also want to surface server-side notifications/logs:
            if "method" in msg and "id" not in msg:
                # notification; ignore in this simple client
                pass

    def get_tools(self, proc: DockerContainer) -> Any:
        """
        This method takes as an argument an MCP server running inside a docker
        container, and it communicates with it over STDIO in order to get the
        list of tools that it exposes.
        """
        # 1) initialize
        self.send(proc, self._initialize())
        init_resp = self._read_until_id(proc, expect_id=1, timeout=10.0)
        if "error" in init_resp:
            print("Initialize error:", init_resp["error"], file=sys.stderr)
            sys.exit(2)

        # 2) notifications/initialized (no response expected)
        self.send(proc, self._notif_initialized())

        # 3) tools/list
        self.send(proc, self._tools_list())
        tools_resp = self._read_until_id(proc, expect_id=2, timeout=10.0)

        if "error" in tools_resp:
            print("tools/list error:", tools_resp["error"], file=sys.stderr)
            sys.exit(3)

        # Pretty-print the tools the server exposes
        result = tools_resp.get("result", {})
        tools = result.get("tools", [])
        print(json.dumps(tools, indent=2))

        return tools
