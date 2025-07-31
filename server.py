#!/usr/bin/env python3
import argparse
import json
import logging
import shlex
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

# Basic MCP JSON-RPC messages


def initialize(protocol_version="2024-11-05"):
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


def notif_initialized():
    return {"jsonrpc": "2.0", "method": "notifications/initialized"}


def tools_list():
    return {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}


def send(proc, obj):
    line = json.dumps(obj, separators=(",", ":")) + "\n"
    proc.stdin.write(line)
    proc.stdin.flush()


def read_until_id(proc, expect_id, timeout=5.0):
    """Read lines until we see a JSON-RPC response with the given id."""
    start = time.time()
    while True:
        if time.time() - start > timeout:
            raise TimeoutError(f"Timed out waiting for response id={expect_id}")
        line = proc.stdout.readline()
        if not line:
            # Process may be buffering; small sleep and try again
            time.sleep(0.01)
            continue
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # Server printed non-JSON text; ignore or print to stderr
            logger.error(f"[server-stdout] {line}")
            continue
        if isinstance(msg, dict) and msg.get("id") == expect_id:
            return msg
        # You may also want to surface server-side notifications/logs:
        if "method" in msg and "id" not in msg:
            # notification; ignore in this simple client
            pass


def main():
    ap = argparse.ArgumentParser(description="List MCP tools from a stdio server")
    ap.add_argument("--cmd", default="python3 -m mcp_server_calculator",
                    help='Command to launch the MCP server (default: "python3 -m mcp_server_calculator")')
    ap.add_argument("--protocol", default="2024-11-05",
                    help="MCP protocolVersion to send in initialize (default: 2024-11-05)")
    args = ap.parse_args()

    # Start the server with stdin/stdout piped
    proc = subprocess.Popen(
        args.cmd if sys.platform == "win32" else shlex.split(args.cmd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        # 1) initialize
        send(proc, initialize(args.protocol))
        init_resp = read_until_id(proc, expect_id=1, timeout=10.0)
        if "error" in init_resp:
            logger.error(f"Initialize error: {init_resp['error']}")
            sys.exit(2)

        # 2) notifications/initialized (no response expected)
        send(proc, notif_initialized())

        # 3) tools/list
        send(proc, tools_list())
        tools_resp = read_until_id(proc, expect_id=2, timeout=10.0)

        if "error" in tools_resp:
            logger.error(f"tools/list error: {tools_resp['error']}")
            sys.exit(3)

        # Pretty-print the tools the server exposes
        result = tools_resp.get("result", {})
        tools = result.get("tools", [])
        logger.info(json.dumps(tools, indent=2))

    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
