# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""Docker-based Sandbox implementation for OneMCP."""

import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SandboxInstance:
    """Represents a running sandbox instance."""

    sandbox_id: str
    container_id: str
    endpoint: str
    repository_url: str
    port: int
    status: str = "running"


class DockerSandboxError(Exception):
    """Base exception for Docker sandbox operations."""

    pass


class DockerSandbox:
    """Docker-based sandbox for MCP servers."""

    def __init__(self, base_port: int = 8000, max_instances: int = 10):
        """Initialize the Docker sandbox.

        Args:
            base_port: Starting port for sandbox instances
            max_instances: Maximum number of concurrent sandbox instances
        """
        self.base_port = base_port
        self.max_instances = max_instances
        self.instances: dict[str, SandboxInstance] = {}
        self.used_ports: set = set()
        self._lock = asyncio.Lock()

    async def discover(self, repository_url: str) -> dict[str, Any]:
        """Discover capabilities and setup instructions for an MCP Server.

        Args:
            repository_url: URL of the repository to discover

        Returns:
            Dictionary containing discovery information
        """
        try:
            logger.info(f"Discovering MCP server at {repository_url}")

            # Clone repository to temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_path = Path(temp_dir) / "repo"

                # Clone the repository
                try:
                    await self._clone_repository(repository_url, str(repo_path))
                except subprocess.CalledProcessError as e:
                    raise DockerSandboxError(f"Failed to clone repository: {e}") from e

                # Analyze repository structure
                discovery_info = await self._analyze_repository(repo_path)

                return {
                    "response_code": "200",
                    "overview": discovery_info["overview"],
                    "tools": discovery_info["tools"],
                    "bootstrap_metadata": discovery_info["bootstrap_metadata"],
                }

        except Exception as e:
            logger.error(f"Discovery failed for {repository_url}: {e}")
            return {
                "response_code": "500",
                "error_description": f"Discovery failed: {str(e)}",
            }

    async def start(self, bootstrap_metadata: dict[str, Any]) -> dict[str, Any]:
        """Start a sandbox instance using the provided bootstrap metadata.

        Args:
            bootstrap_metadata: Metadata required to start the sandbox

        Returns:
            Dictionary containing start response
        """
        async with self._lock:
            try:
                if len(self.instances) >= self.max_instances:
                    return {
                        "response_code": "429",
                        "error_description": "Maximum number of sandbox instances reached",
                    }

                # Generate unique sandbox ID
                sandbox_id = str(uuid.uuid4())

                # Allocate port
                port = self._allocate_port()
                if port is None:
                    return {
                        "response_code": "503",
                        "error_description": "No available ports for sandbox instance",
                    }

                # Start Docker container
                container_id = await self._start_docker_container(
                    sandbox_id, bootstrap_metadata, port
                )

                # Create sandbox instance
                instance = SandboxInstance(
                    sandbox_id=sandbox_id,
                    container_id=container_id,
                    endpoint=f"localhost:{port}",
                    repository_url=bootstrap_metadata.get("repository_url", ""),
                    port=port,
                )

                self.instances[sandbox_id] = instance
                self.used_ports.add(port)

                logger.info(f"Started sandbox {sandbox_id} on port {port}")

                return {
                    "response_code": "200",
                    "sandbox_id": sandbox_id,
                    "endpoint": instance.endpoint,
                }

            except Exception as e:
                logger.error(f"Failed to start sandbox: {e}")
                return {
                    "response_code": "500",
                    "error_description": f"Failed to start sandbox: {str(e)}",
                }

    async def stop(self, sandbox_id: str) -> dict[str, Any]:
        """Stop a running sandbox instance.

        Args:
            sandbox_id: ID of the sandbox to stop

        Returns:
            Dictionary containing stop response
        """
        async with self._lock:
            try:
                if sandbox_id not in self.instances:
                    return {
                        "response_code": "404",
                        "error_description": f"Sandbox {sandbox_id} not found",
                    }

                instance = self.instances[sandbox_id]

                # Stop Docker container
                await self._stop_docker_container(instance.container_id)

                # Clean up resources
                self.used_ports.discard(instance.port)
                del self.instances[sandbox_id]

                logger.info(f"Stopped sandbox {sandbox_id}")

                return {"response_code": "200"}

            except Exception as e:
                logger.error(f"Failed to stop sandbox {sandbox_id}: {e}")
                return {
                    "response_code": "500",
                    "error_description": f"Failed to stop sandbox: {str(e)}",
                }

    async def list_instances(self) -> list[dict[str, Any]]:
        """List all running sandbox instances.

        Returns:
            List of sandbox instance information
        """
        return [
            {
                "sandbox_id": instance.sandbox_id,
                "endpoint": instance.endpoint,
                "repository_url": instance.repository_url,
                "status": instance.status,
            }
            for instance in self.instances.values()
        ]

    async def cleanup_all(self) -> None:
        """Stop all running sandbox instances."""
        sandbox_ids = list(self.instances.keys())
        for sandbox_id in sandbox_ids:
            await self.stop(sandbox_id)

    def _allocate_port(self) -> Optional[int]:
        """Allocate an available port for a new sandbox instance."""
        for port in range(self.base_port, self.base_port + 1000):
            if port not in self.used_ports:
                return port
        return None

    async def _analyze_repository(self, repo_path: Path) -> dict[str, Any]:
        """Analyze repository to extract MCP server information.

        Args:
            repo_path: Path to the cloned repository

        Returns:
            Dictionary containing analysis results
        """
        overview = "MCP Server Repository"
        tools = []
        bootstrap_metadata = {
            "repository_url": "",
            "dockerfile_path": "Dockerfile",
            "entrypoint": "python server.py",
            "environment_variables": {},
            "build_args": {},
            "working_directory": "/app",
        }

        # Check for common files
        pyproject_path = repo_path / "pyproject.toml"
        package_json_path = repo_path / "package.json"
        dockerfile_path = repo_path / "Dockerfile"
        requirements_path = repo_path / "requirements.txt"
        readme_path = repo_path / "README.md"

        # Parse pyproject.toml if it exists
        if pyproject_path.exists():
            try:
                # Handle Python version compatibility for tomllib
                try:
                    import tomllib  # type: ignore[import-not-found]
                except ImportError:
                    # Fallback for Python < 3.11
                    import tomli as tomllib  # type: ignore[import-not-found]

                with open(pyproject_path, "rb") as f:
                    pyproject_data = tomllib.load(f)

                project_info = pyproject_data.get("project", {})
                overview = project_info.get("description", overview)

                # Check for MCP-specific configuration
                if "mcp" in str(pyproject_data).lower():
                    bootstrap_metadata["entrypoint"] = "python -m mcp"

            except Exception as e:
                logger.warning(f"Failed to parse pyproject.toml: {e}")

        # Parse package.json if it exists (Node.js projects)
        elif package_json_path.exists():
            try:
                with open(package_json_path) as f:
                    package_data = json.load(f)

                overview = package_data.get("description", overview)
                scripts = package_data.get("scripts", {})

                if "start" in scripts:
                    bootstrap_metadata["entrypoint"] = "npm start"
                elif "main" in package_data:
                    bootstrap_metadata["entrypoint"] = f"node {package_data['main']}"

            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")

        # Check for Dockerfile
        if dockerfile_path.exists():
            bootstrap_metadata["has_dockerfile"] = "true"
        else:
            # Generate Dockerfile content based on detected language
            if pyproject_path.exists() or requirements_path.exists():
                bootstrap_metadata["dockerfile_content"] = (
                    self._generate_python_dockerfile()
                )
            elif package_json_path.exists():
                bootstrap_metadata["dockerfile_content"] = (
                    self._generate_nodejs_dockerfile()
                )
            else:
                bootstrap_metadata["dockerfile_content"] = (
                    self._generate_generic_dockerfile()
                )

        # Parse README for additional information
        if readme_path.exists():
            try:
                with open(readme_path, encoding="utf-8") as f:
                    readme_content = f.read()

                # Extract tools information from README (basic heuristic)
                if "tools" in readme_content.lower():
                    tools.append(
                        {
                            "name": "mcp_server_tool",
                            "description": "MCP server tool extracted from README",
                        }
                    )

            except Exception as e:
                logger.warning(f"Failed to parse README.md: {e}")

        return {
            "overview": overview,
            "tools": tools,
            "bootstrap_metadata": bootstrap_metadata,
        }

    def _generate_python_dockerfile(self) -> str:
        """Generate a Dockerfile for Python MCP servers."""
        return """FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt* pyproject.toml* ./

# Install dependencies
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
RUN if [ -f pyproject.toml ]; then pip install -e .; fi

# Copy application code
COPY . .

# Expose default MCP port
EXPOSE 8000

# Run the MCP server
CMD ["python", "server.py"]
"""

    def _generate_nodejs_dockerfile(self) -> str:
        """Generate a Dockerfile for Node.js MCP servers."""
        return """FROM node:18-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose default MCP port
EXPOSE 8000

# Run the MCP server
CMD ["npm", "start"]
"""

    def _generate_generic_dockerfile(self) -> str:
        """Generate a generic Dockerfile."""
        return """FROM ubuntu:22.04

WORKDIR /app

# Install basic dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Expose default MCP port
EXPOSE 8000

# Default command
CMD ["echo", "MCP Server - please configure proper entrypoint"]
"""

    async def _start_docker_container(
        self, sandbox_id: str, bootstrap_metadata: dict[str, Any], port: int
    ) -> str:
        """Start a Docker container for the sandbox instance.

        Args:
            sandbox_id: Unique identifier for the sandbox
            bootstrap_metadata: Metadata for container configuration
            port: Port to expose the container on

        Returns:
            Container ID
        """
        # Create temporary directory for this sandbox
        sandbox_dir = Path(tempfile.mkdtemp(prefix=f"sandbox_{sandbox_id}_"))

        try:
            # Clone repository if URL provided
            repository_url = bootstrap_metadata.get("repository_url")
            if repository_url:
                await self._clone_repository(repository_url, str(sandbox_dir / "app"))
                app_dir = sandbox_dir / "app"
            else:
                app_dir = sandbox_dir

            # Create Dockerfile if not present
            dockerfile_path = app_dir / "Dockerfile"
            if (
                not dockerfile_path.exists()
                and "dockerfile_content" in bootstrap_metadata
            ):
                with open(dockerfile_path, "w") as f:
                    f.write(bootstrap_metadata["dockerfile_content"])

            # Build Docker image
            image_tag = f"onemcp-sandbox-{sandbox_id}"
            build_cmd = ["docker", "build", "-t", image_tag, str(app_dir)]

            # Add build args if specified
            build_args = bootstrap_metadata.get("build_args", {})
            for key, value in build_args.items():
                build_cmd.extend(["--build-arg", f"{key}={value}"])

            logger.info(f"Building Docker image: {' '.join(build_cmd)}")
            result = await asyncio.create_subprocess_exec(
                *build_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                raise DockerSandboxError(f"Docker build failed: {stderr.decode()}")

            # Run Docker container
            run_cmd = [
                "docker",
                "run",
                "-d",  # Run in detached mode
                "-p",
                f"{port}:8000",  # Port mapping
                "--name",
                f"sandbox-{sandbox_id}",
                "--rm",  # Remove container when it stops
            ]

            # Add environment variables
            env_vars = bootstrap_metadata.get("environment_variables", {})
            for key, value in env_vars.items():
                run_cmd.extend(["-e", f"{key}={value}"])

            # Set working directory if specified
            working_dir = bootstrap_metadata.get("working_directory", "/app")
            run_cmd.extend(["-w", working_dir])

            # Add image tag
            run_cmd.append(image_tag)

            # Add entrypoint if specified
            entrypoint = bootstrap_metadata.get("entrypoint")
            if entrypoint:
                run_cmd.extend(entrypoint.split())

            logger.info(f"Starting Docker container: {' '.join(run_cmd)}")
            result = await asyncio.create_subprocess_exec(
                *run_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                raise DockerSandboxError(f"Docker run failed: {stderr.decode()}")

            container_id = stdout.decode().strip()
            logger.info(f"Started container {container_id} for sandbox {sandbox_id}")

            return container_id

        except Exception as e:
            # Clean up on failure
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            raise e

    async def _stop_docker_container(self, container_id: str) -> None:
        """Stop and remove a Docker container.

        Args:
            container_id: ID of the container to stop
        """
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

    async def _clone_repository(self, repository_url: str, destination: str) -> None:
        """Clone a Git repository using subprocess.

        Args:
            repository_url: URL of the repository to clone
            destination: Local destination path
        """
        cmd = ["git", "clone", repository_url, destination]

        result = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode or 1, cmd, output=stdout, stderr=stderr
            )
