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

import requests
from openai import OpenAI

from src.onemcp.util.env import ONEMCP_SRC_ROOT

logger = logging.getLogger(__name__)


class DockerSandboxError(Exception):
    """Base exception for Docker sandbox operations."""

    pass


class DockerContainer:

    def id(self) -> str:
        """Return the unique identifier for this container."""
        return self.proc.pid

    def start(
        self, sandbox_id: str, bootstrap_metadata: dict[str, Any], port: int
    ):
        # Create temporary directory for this sandbox
        sandbox_dir = Path(tempfile.mkdtemp(prefix=f"sandbox_{sandbox_id}_"))

        try:
            # Get the container image tag from bootstrap metadata
            container_image_tag = bootstrap_metadata.get("container_image_tag", "onemcp-default")

            # Run Docker container
            run_cmd = [
                "docker",
                "run",
                "-i",
                "-p",
                f"{port}:8000",  # Port mapping
                "--name",
                f"sandbox-{sandbox_id}",
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

            self.proc = subprocess.Popen(
                run_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                # stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

        except Exception as e:
            # Clean up on failure
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            raise e

    async def stop(self) -> None:
        container_id: str = self.proc.pid
        try:
            # Stop the container
            stop_cmd = ["docker", "stop", container_id]
            result = await asyncio.create_subprocess_exec(
                *stop_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()

            # Container should be automatically removed due to --rm flag
            logger.info(f"Stopped container {container_id}")

        except Exception as e:
            logger.error(f"Failed to stop container {container_id}: {e}")
            raise DockerSandboxError(f"Failed to stop container: {e}") from e

    def write(self, data: str) -> None:
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def read(self) -> str:
        line: str = self.proc.stdout.readline()
        return line
