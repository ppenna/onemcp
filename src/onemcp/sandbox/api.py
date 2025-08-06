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

        print(f"Starting sandbox with metadata: {bootstrap_metadata}")
        response = requests.post(
            self.sandbox_endpoint,
            json={"bootstrap_metadata": bootstrap_metadata},
            headers=headers,
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

    def call_tool_continue(
        self,
        sandbox_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        request_id: int = 1,
    ) -> Any:
        data = {
            "sandbox_id": sandbox_id,
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        headers = {
            "Content-Type": "application/json",
            "X-OneMCP-Message-Type": "CALL_TOOL_CONTINUE",
        }

        print(f"Calling tool '{tool_name}' with arguments: {arguments}")
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


if __name__ == "__main__":
    import json
    import time

    # Example usage based on demo-sandbox-http-api.sh
    sandbox = SandboxAPI()

    # Example 1: Complete workflow with calculator MCP server
    print("=== Example 1: Calculator MCP Server Workflow ===")

    # Bootstrap metadata for the calculator MCP server
    bootstrap_metadata = {
        "bootstrap_metadata": {
            "repository_url": "https://github.com/githejie/mcp-server-calculator",
            "setup_script": """#!/bin/bash

# Update package list and install git
apt-get update
apt-get install -y git

# Clone the MCP server repository
git clone https://github.com/githejie/mcp-server-calculator
cd mcp-server-calculator

# Install Python3, pip, and python3-venv
apt-get install -y python3 python3-pip python3-venv

# Create a Python3 virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install the MCP server using pip
pip install mcp-server-calculator

# Create a script to run the MCP server
cat <<EOL > /run_mcp.sh
#!/bin/bash
source $(pwd)/venv/bin/activate
python3 -m mcp_server_calculator
EOL

chmod +x /run_mcp.sh""",
        }
    }

    try:
        # Start the sandbox
        print("Starting sandbox...")
        sandbox_id = sandbox.start_sandbox(bootstrap_metadata)
        print(f"Sandbox started with ID: {sandbox_id}")

        # Wait for sandbox to be ready
        time.sleep(2)

        # Get available tools
        print("Getting available tools...")
        tools_response = sandbox.get_tools(sandbox_id)
        print(f"Available tools: {json.dumps(tools_response, indent=2)}")

        # Wait before calling tool
        time.sleep(2)

        # Call the calculate tool
        print("Calling 'calculate' tool with expression '0.5 + 0.25'...")
        result = sandbox.call_tool(
            sandbox_id=sandbox_id,
            tool_name="calculate",
            arguments={"expression": "0.5 + 0.25"},
        )

        # Extract and display the result
        calculation_result = (
            result.get("response", {})
            .get("result", {})
            .get("structuredContent", {})
            .get("result")
        )
        print(f"Calculation result: {calculation_result}")

        # Wait before stopping
        time.sleep(2)

        # Stop the sandbox
        print("Stopping sandbox...")
        stop_response = sandbox.stop_sandbox(sandbox_id)
        print("Sandbox stopped successfully!")

    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 50 + "\n")

    # Example 2: Error handling and multiple tool calls
    print("=== Example 2: Multiple Tool Calls with Error Handling ===")

    try:
        # Start sandbox
        sandbox_id = sandbox.start_sandbox(bootstrap_metadata)
        print(f"Started sandbox: {sandbox_id}")

        # Multiple calculations
        expressions = ["1 + 1", "10 * 5", "sqrt(16)", "2^3"]

        for i, expr in enumerate(expressions, 1):
            try:
                print(f"Calculation {i}: {expr}")
                result = sandbox.call_tool(
                    sandbox_id=sandbox_id,
                    tool_name="calculate",
                    arguments={"expression": expr},
                    request_id=i,
                )

                calculation_result = (
                    result.get("response", {})
                    .get("result", {})
                    .get("structuredContent", {})
                    .get("result")
                )
                print(f"  Result: {calculation_result}")

            except Exception as e:
                print(f"  Error calculating '{expr}': {e}")

        # Clean up
        sandbox.stop_sandbox(sandbox_id)
        print("Sandbox stopped.")

    except Exception as e:
        print(f"Failed to start sandbox: {e}")

    print("\n" + "=" * 50 + "\n")

    # Example 3: Custom base URL
    print("=== Example 3: Custom Base URL ===")

    # Create API client with custom URL
    custom_sandbox = SandboxAPI(base_url="http://my-custom-server:9090")
    print(f"Custom sandbox endpoint: {custom_sandbox.sandbox_endpoint}")

    # Example 4: Minimal usage pattern
    print("\n=== Example 4: Minimal Usage Pattern ===")
    print("""
    # Minimal usage pattern:

    sandbox = SandboxAPI()

    # 1. Start sandbox
    sandbox_id = sandbox.start_sandbox(bootstrap_metadata)

    # 2. Get tools (optional, for discovery)
    tools = sandbox.get_tools(sandbox_id)

    # 3. Call tools as needed
    result = sandbox.call_tool(sandbox_id, "tool_name", {"arg": "value"})

    # 4. Stop sandbox when done
    sandbox.stop_sandbox(sandbox_id)
    """)
