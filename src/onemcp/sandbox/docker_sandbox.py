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


class ReadmeNotFound(Exception):
    pass


@dataclass
class SandboxedMcpServer:
    """Represents a running sandbox instance."""

    sandbox_id: str
    process_id: str
    endpoint: str
    port: int
    proc: Optional[subprocess.Popen] = None
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

    def send(self, proc, obj):
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()

    def _read_until_id(self, proc, expect_id, timeout=5.0):
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
            self.send(self.proc, self._initialize())
            init_resp = self._read_until_id(self.proc, expect_id=1, timeout=10.0)
            if "error" in init_resp:
                print("Initialize error:", init_resp["error"], file=sys.stderr)
                sys.exit(2)

            # 2) notifications/initialized (no response expected)
            self.send(self.proc, self._notif_initialized())

            # 3) tools/list
            self.send(self.proc, self._tools_list())
            tools_resp = self._read_until_id(self.proc, expect_id=2, timeout=10.0)

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
        self.instances: dict[str, SandboxedMcpServer] = {}
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

            # Analyze repository structure
            discovery_info = await self._analyze_repository(repository_url)

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
                proc = self._start_docker_container(
                    sandbox_id, bootstrap_metadata, port
                )

                process_id = proc.pid

                # Create sandbox instance
                instance = SandboxedMcpServer(
                    sandbox_id=sandbox_id,
                    process_id=process_id,
                    endpoint=f"localhost:{port}",
                    port=port,
                    proc=proc,
                    status="running",
                )

                instance._get_tools()

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
                await self._stop_docker_container(instance.process_id)

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

    def _parse_repo_url(self, url: str) -> tuple[str, str]:
        """Extract (owner, repo) from a GitHub repository URL."""
        url = url.strip()

        # SSH: git@github.com:owner/repo(.git)
        if url.startswith("git@github.com:"):
            path = url.split("git@github.com:")[1]
            if path.endswith(".git"):
                path = path[:-4]
            owner, repo = path.split("/", 1)
            return owner, repo

        # HTTPS: https://github.com/owner/repo(.git)[/...]
        parsed = urlparse(url)
        if parsed.netloc not in {"github.com", "www.github.com"}:
            raise ValueError("URL must be a github.com repository URL")
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError(
                "Repository URL must be like https://github.com/<owner>/<repo>"
            )
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo

    def _get_repo_readme(
        self, repo_url: str, token: Optional[str] = None, timeout: int = 20
    ) -> str:
        """
        Return the root README text for a GitHub repository URL.

        Works for public repos; for private repos pass a token or set GITHUB_TOKEN.
        """
        owner, repo = self._parse_repo_url(repo_url)
        headers = {
            "Accept": "application/vnd.github.v3.raw",
            "User-Agent": "readme-minimal/1.0",
        }
        token = token or os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 404:
            raise ReadmeNotFound("No README found in the repository root.")
        r.raise_for_status()
        return r.text

    def _build_prompt(self, repository_url: str) -> str:
        try:
            readme_text = self._get_repo_readme(repository_url)
        except ReadmeNotFound:
            print(f"Could not find readme at: {repository_url}. Exitting...")
            exit(1)

        prompt = f"The GitHub URL for the MCP server is {repository_url}. Here "
        prompt += f"is the README:\n{readme_text}"

        return prompt

    def _generate_dockerfile(self, setup_script: str, image_tag: str) -> None:
        dockerfile_path = os.path.join(
            ONEMCP_SRC_ROOT, "sandbox", "install_mcp.dockerfile"
        )

        logger.info(f"Generating docker file (tag={image_tag}, path={dockerfile_path})")

        with open("/tmp/setup.sh", "w") as fh:
            fh.write(setup_script)

        # Dump the setup script on a temporary file that we delete afterwards.
        with tempfile.NamedTemporaryFile(mode="w+", delete=True) as tmp:
            tmp.write(setup_script)

            tmp_name_basename = "setup.sh"
            tmp_name_dirname = "/tmp"
            # tmp_name_basename = os.path.basename(tmp.name)
            # tmp_name_dirname = os.path.dirname(tmp.name)
            docker_cmd = [
                "docker",
                "build",
                f"-t {image_tag}",
                f"-f {dockerfile_path}",
                f"--build-arg SCRIPT_PATH={tmp_name_basename}",
                f"--build-context scriptctx={tmp_name_dirname}",
                ".",
            ]
            print(f"tmp.name: {tmp.name}")
            print(f"docker_cmd: {docker_cmd}")

            docker_cmd_str = " ".join(docker_cmd)
            subprocess.run(docker_cmd_str, shell=True, check=True)

            logger.info("Generated dockerfile at: {image_tag}")

    async def _analyze_repository(self, repository_url: str) -> dict[str, Any]:
        """Analyze repository to extract MCP server information.

        Args:
            repo_path: Path to the cloned repository

        Returns:
            Dictionary containing analysis results
        """
        # First get the repository readme file.
        prompt = self._build_prompt(repository_url)

        system_prompt_file = Path(
            os.path.join(ONEMCP_SRC_ROOT, "sandbox", "discovery-prompt-header.md")
        )
        if not system_prompt_file.exists():
            raise Exception(f"Error: File {system_prompt_file} does not exist.")

        # Read the system prompt from the file.
        system_prompt = system_prompt_file.read_text().strip()

        # Get the installation instructions from an LLM.
        # FIXME: this is using carlos' personal API key.
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        # Catch if the model returns a markdown blob, even if instructed to not
        # do so.
        setup_script: str = response.choices[0].message.content or ""
        if setup_script.startswith("```") and setup_script.endswith("```"):
            setup_script = "\n".join(setup_script.split("\n")[1:-1])

        logger.info("Generated set-up script for MCP server at url: {repository_url}")

        # Generate temporary dockerfile from the set-up.
        # TODO: randomize
        container_image_tag = "onemcp-smoke-test"
        self._generate_dockerfile(setup_script, container_image_tag)

        overview = "MCP Server Repository"
        tools: list[Any] = []
        # TODO: update
        bootstrap_metadata = {
            "container_image_tag": container_image_tag,
        }

        # Start docker container
        port = await self.start(bootstrap_metadata)

        return {
            "overview": overview,
            "tools": tools,
            "bootstrap_metadata": bootstrap_metadata,
        }

    def _start_docker_container(
        self, sandbox_id: str, bootstrap_metadata: dict[str, Any], port: int
    ) -> subprocess.Popen:
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

            proc = subprocess.Popen(
                run_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                # stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            return proc

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
