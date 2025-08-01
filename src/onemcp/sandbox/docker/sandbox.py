# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""Docker-based Sandbox implementation for OneMCP."""

import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class DockerSandboxError(Exception):
    """Base exception for Docker sandbox operations."""

    pass


class DockerContainer:
    name: str
    proc: subprocess.Popen

    def pid(self) -> int:
        """
        Return the process identifier for the underlying process running the
        docker container.
        """
        return self.proc.pid

    def container_id(self) -> int:
        """
        Return the process identifier for the underlying process running the
        docker container.
        """
        return self.proc.pid

    async def start(
        self, sandbox_id: str, bootstrap_metadata: dict[str, Any], port: int
    ) -> None:
        # Create temporary directory for this sandbox
        self.name: str = sandbox_id
        sandbox_dir = Path(tempfile.mkdtemp(prefix=f"sandbox_{self.name}_"))

        try:
            # Get the container image tag from bootstrap metadata
            container_image_tag = bootstrap_metadata.get(
                "container_image_tag", "onemcp-default"
            )

            # Run Docker container
            docker_params = [
                "run",
                "-i",
                "-p",
                f"{port}:8000",  # Port mapping
                "--name",
                self.name,
                container_image_tag
            ]

            logger.info(f"Starting Docker container: docker {' '.join(docker_params)}")

            self.port = port
            server_params = StdioServerParameters(
                command="docker",
                args=docker_params,
                env=None,
            )

            stdio_transport = stdio_client(server_params)
            self.stdio, self.write = stdio_transport
            self.session = ClientSession(self.stdio, self.write)

            await self.session.initialize()

            response = await self.session.list_tools()
            self.tools = response.tools

        except Exception as e:
            # Clean up on failure
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            raise DockerSandboxError(f"Failed to start container: {e}") from e

    async def stop(self) -> None:
        try:
            # Stop the container
            stop_cmd = ["docker", "stop", self.name]
            result = await asyncio.create_subprocess_exec(
                *stop_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()

            # Container should be automatically removed due to --rm flag
            logger.info(f"Stopped container {self.name}")

        except Exception as e:
            logger.error(f"Failed to stop container {self.name}: {e}")
            raise DockerSandboxError(f"Failed to stop container: {e}") from e


    def get_tools(self) -> Any:
        return self.tools


    async def call_tool(self, tool_name: str, *args: Any) -> Any:
        """
        Call a tool in the Docker container.

        Args:
            tool_name (str): The name of the tool to call.
            *args: Arguments to pass to the tool.

        Returns:
            Any: The result of the tool call.
        """
        if not self.session:
            raise DockerSandboxError("Session is not initialized")

        try:
            response = await self.session.call_tool(tool_name, *args)
            return response
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            raise DockerSandboxError(f"Tool call failed: {e}") from e


    def write(self, data: str) -> None:
        if self.proc.stdin is None:
            raise DockerSandboxError("Docker container has no STDIN")

        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def read(self) -> str:
        if self.proc.stdout is None:
            raise DockerSandboxError("Docker container has no STDIN")

        line: str = self.proc.stdout.readline()
        return line
