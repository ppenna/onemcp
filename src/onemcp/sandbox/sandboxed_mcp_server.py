# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""Docker-based Sandbox implementation for OneMCP."""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
import argparse
import json
import shlex
import subprocess
import sys
import time

from onemcp.sandbox.docker_container import DockerContainer
import requests
from openai import OpenAI

from src.onemcp.util.env import ONEMCP_SRC_ROOT


@dataclass
class SandboxedMcpServer:
    """Represents a running sandbox instance."""

    endpoint: str
    proc: Optional[DockerContainer] = None
    status: str = "running"

    # Basic MCP JSON-RPC messages
    def _initialize(self, protocol_version="2024-11-05"):
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {},        # minimal; add if your client supports more
                "clientInfo": {"name": "cli-mcp", "version": "0.1"},
            },
        }

    def _notif_initialized(self):
        return {"jsonrpc": "2.0", "method": "notifications/initialized"}

    def _tools_list(self):
        return {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    def send(self, obj):
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        self.proc.write(line)

    def _read_until_id(self, expect_id, timeout=5.0):
        """Read lines until we see a JSON-RPC response with the given id."""
        start = time.time()
        while True:
            if time.time() - start > timeout:
                raise TimeoutError(f"Timed out waiting for response id={expect_id}")
            line = self.proc.read()
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

    def _get_tools(self):

        try:
            # 1) initialize
            self.send(self._initialize())
            init_resp = self._read_until_id(expect_id=1, timeout=10.0)
            if "error" in init_resp:
                print("Initialize error:", init_resp["error"], file=sys.stderr)
                sys.exit(2)

            # 2) notifications/initialized (no response expected)
            self.send(self._notif_initialized())

            # 3) tools/list
            self.send(self._tools_list())
            tools_resp = self._read_until_id(expect_id=2, timeout=10.0)

            if "error" in tools_resp:
                print("tools/list error:", tools_resp["error"], file=sys.stderr)
                sys.exit(3)

            # Pretty-print the tools the server exposes
            result = tools_resp.get("result", {})
            tools = result.get("tools", [])
            print(json.dumps(tools, indent=2))

        finally:
            try:
                self.proc.terminate()
            except Exception:
                pass

    def stop(self) -> None:
        """Stop the sandboxed MCP server."""
        if self.proc:
            try:
                self.proc.stop()
            except Exception as e:
                logging.error(f"Failed to stop sandboxed MCP server: {e}")
            finally:
                self.proc = None
        else:
            logging.warning("No running sandboxed MCP server to stop.")
