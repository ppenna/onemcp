# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from src.onemcp.sandbox.docker.sandbox import DockerContainer

# Default protocol version for MCP server communication
DEFAULT_PROTOCOL_VERSION: str = "2024-11-05"

# Default read delay when reading data from a container.
DEFAULT_READ_DELAY: float = 0.01

# Default timeout for reading data from a container.
DEFAULT_READ_TIMEOUT: float = 10.0

logger = logging.getLogger(__name__)


@dataclass
class McpServer:
    """Represents an MCP server interface for communicating with MCP servers running in containers."""

    endpoint: str
    status: str = "running"

    def _initialize(
        self, protocol_version: str = DEFAULT_PROTOCOL_VERSION
    ) -> dict[str, Any]:
        """
        Constructs and returns a JSON-RPC 2.0 initialization request payload.

        Args:
            protocol_version (str, optional): The protocol version to use in the request.
                Defaults to DEFAULT_PROTOCOL_VERSION.

        Returns:
            dict[str, Any]: A dictionary representing the JSON-RPC initialization request,
                including protocol version, capabilities, and client information.
        """
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
        """
        Creates a JSON-RPC notification message indicating that the server has been initialized.

        Returns:
            dict[str, str]: A dictionary representing the JSON-RPC notification with
            the "jsonrpc" version set to "2.0" and the "method" set to "notifications/initialized".
        """
        return {"jsonrpc": "2.0", "method": "notifications/initialized"}

    def _tools_list(self) -> dict[str, Any]:
        """
        Constructs and returns a JSON-RPC request dictionary for listing available tools.

        Returns:
            dict[str, Any]: A dictionary representing a JSON-RPC 2.0 request with the method
            "tools/list" and empty parameters.
        """
        return {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    def send(self, proc: DockerContainer, obj: dict[str, Any]) -> None:
        """
        Sends a JSON-encoded dictionary object to a DockerContainer process.

        Args:
            proc (DockerContainer): The Docker container process to send data to.
            obj (dict[str, Any]): The dictionary object to be serialized and sent.

        Returns:
            None

        Notes:
            The dictionary is serialized to a compact JSON string and a newline character is
            appended. The resulting string is written to the DockerContainer process.
        """
        line: str = json.dumps(obj, separators=(",", ":")) + "\n"
        proc.write(line)

    def _read_until_id(
        self,
        container: DockerContainer,
        expect_id: int,
        timeout: float = DEFAULT_READ_TIMEOUT,
    ) -> dict[str, Any]:
        """
        Reads lines from the DockerContainer's output until a JSON-RPC response
        with the specified 'id' is received or a timeout occurs.

        Args:
            container (DockerContainer): The Docker container process to read from.
            expect_id (int): The JSON-RPC response 'id' to wait for.
            timeout (float, optional): Maximum time in seconds to wait for the response.
                Defaults to DEFAULT_READ_TIMEOUT.

        Returns:
            dict[str, Any]: The parsed JSON-RPC response dictionary with the expected 'id'.

        Raises:
            TimeoutError: If the expected response is not received within the timeout.

        Notes:
            - Lines that cannot be parsed as JSON are logged as warnings and ignored.
            - Only responses with a matching 'id' are returned.
            - Notifications (messages with a "method" but no "id") are ignored.
        """
        start = time.time()
        while True:
            if time.time() - start > timeout:
                logger.error(
                    f"Timeout waiting for response with id={expect_id} after {timeout} seconds"
                )
                raise TimeoutError(f"Timed out waiting for response id={expect_id}")
            line: str = container.read()
            if not line:
                time.sleep(DEFAULT_READ_DELAY)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to decode JSON: {e} - Line: {line}")
                continue
            if isinstance(msg, dict) and msg.get("id") == expect_id:
                return msg
            if "method" in msg and "id" not in msg:
                # Notification received; ignore and continue reading.
                pass

    def get_tools(self, container: DockerContainer) -> Any:
        """
        Queries the MCP server running in the specified Docker container for its list of tools.

        Args:
            container (DockerContainer): The Docker container instance where the MCP server is running.

        Returns:
            Any: A list of tools provided by the server.

        Raises:
            RuntimeError: If an error occurs during initialization or tool retrieval.
        """
        # Send the initialization request.
        self.send(container, self._initialize())
        init_resp = self._read_until_id(container, expect_id=1)
        if "error" in init_resp:
            logger.error(f"MCP server initialization failed: {init_resp['error']}")
            raise RuntimeError(f"Initialization error: {init_resp['error']}")

        # Send the initialized notification.
        self.send(container, self._notif_initialized())

        # Request the list of tools.
        self.send(container, self._tools_list())
        tools_resp = self._read_until_id(container, expect_id=2)

        if "error" in tools_resp:
            logger.error(
                f"Failed to retrieve tools from MCP server: {tools_resp['error']}"
            )
            raise RuntimeError(f"Tools retrieval error: {tools_resp['error']}")

        logger.debug(f"Tools response: {tools_resp}")
        result = tools_resp.get("result", {})
        tools = result.get("tools", [])

        logger.debug(f"Retrieved tools: {tools}")

        return tools

    def call_tool(self, container: DockerContainer, body: dict[str, Any]) -> Any:
        """
        Queries the MCP server running in the specified Docker container to run a specific tool.

        Args:
            container (DockerContainer): The Docker container instance where the MCP server is running.
            body: The body of the tools/call request

        Returns:
            Any: The response of the tool

        Raises:
            RuntimeError: If an error occurs during initialization or tool execution.
        """
        # Send the initialization request.
        self.send(container, self._initialize())
        init_resp = self._read_until_id(container, expect_id=1)
        if "error" in init_resp:
            logger.error(f"MCP server initialization failed: {init_resp['error']}")
            raise RuntimeError(f"Initialization error: {init_resp['error']}")

        # Send the initialized notification.
        self.send(container, self._notif_initialized())

        # Request the list of tools.
        body["id"] = 2
        self.send(container, body)
        tools_resp = self._read_until_id(container, expect_id=2)

        if "error" in tools_resp:
            logger.error(f"Failed to call tool from MCP server: {tools_resp['error']}")
            raise RuntimeError(f"Tool execution error: {tools_resp['error']}")

        logger.debug(f"Tools resp: {tools_resp}")

        return tools_resp
