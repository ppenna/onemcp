# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Any

import requests


class SandboxAPI:
    """Client for interacting with the OneMCP sandbox HTTP API."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")
        self.sandbox_endpoint = f"{self.base_url}/sandbox"

    def start_sandbox(self, bootstrap_metadata: dict[str, Any]) -> Any:
        """
        Start a new sandbox with the specified container image.

        Args:
            bootstrap_metadata: Metadata to bootstrap the sandbox

        Returns:
            The sandbox ID

        Raises:
            requests.RequestException: If the request fails
            KeyError: If the response doesn't contain sandbox_id
        """

        headers = {"Content-Type": "application/json", "X-OneMCP-Message-Type": "START"}

        response = requests.post(
            self.sandbox_endpoint, json=bootstrap_metadata, headers=headers
        )
        response.raise_for_status()

        result = response.json()
        return result["sandbox_id"]

    def get_tools(self, sandbox_id: str) -> Any:
        """
        Get the available tools from the MCP server in the sandbox.

        Args:
            sandbox_id: The ID of the sandbox

        Returns:
            The tools response from the MCP server

        Raises:
            requests.RequestException: If the request fails
        """
        data = {"sandbox_id": sandbox_id}

        headers = {
            "Content-Type": "application/json",
            "X-OneMCP-Message-Type": "GET_TOOLS",
        }

        response = requests.post(self.sandbox_endpoint, json=data, headers=headers)
        response.raise_for_status()

        return response.json()

    def call_tool(
        self,
        sandbox_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        request_id: int = 1,
    ) -> Any:
        """
        Call a tool in the MCP server within the sandbox.

        Args:
            sandbox_id: The ID of the sandbox
            tool_name: The name of the tool to call
            arguments: The arguments to pass to the tool
            request_id: The JSON-RPC request ID (default: 1)

        Returns:
            The tool call response

        Raises:
            requests.RequestException: If the request fails
        """
        data = {
            "sandbox_id": sandbox_id,
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        headers = {
            "Content-Type": "application/json",
            "X-OneMCP-Message-Type": "CALL_TOOL",
        }

        response = requests.post(self.sandbox_endpoint, json=data, headers=headers)
        response.raise_for_status()

        return response.json()

    def stop_sandbox(self, sandbox_id: str) -> Any:
        """
        Stop a sandbox.

        Args:
            sandbox_id: The ID of the sandbox to stop

        Returns:
            The stop response

        Raises:
            requests.RequestException: If the request fails
        """
        data = {"sandbox_id": sandbox_id}

        headers = {"Content-Type": "application/json", "X-OneMCP-Message-Type": "STOP"}

        response = requests.post(self.sandbox_endpoint, json=data, headers=headers)
        response.raise_for_status()

        return response.json()
