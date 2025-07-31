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

    def start(
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
            run_cmd = [
                "docker",
                "run",
                "-i",
                "-p",
                f"{port}:8000",  # Port mapping
                "--name",
                self.name,
            ]

            # Add environment variables (if any are provided)
            env_vars = bootstrap_metadata.get("environment_variables", {})
            for key, value in env_vars.items():
                run_cmd.extend(["-e", f"{key}={value}"])

            # Set working directory if specified
            working_dir = bootstrap_metadata.get("working_directory", "/app")
            run_cmd.extend(["-w", working_dir])

            # Add image tag
            run_cmd.append(container_image_tag)

            # Add entrypoint if specified
            entrypoint = bootstrap_metadata.get("entrypoint")
            if entrypoint:
                run_cmd.extend(entrypoint.split())

            logger.info(f"Starting Docker container: {' '.join(run_cmd)}")

            self.port = port
            self.proc = subprocess.Popen(
                run_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

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
