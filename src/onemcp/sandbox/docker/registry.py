# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""Docker-based Sandbox implementation for OneMCP."""

import asyncio
import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

from src.onemcp.sandbox.docker.sandbox import DockerContainer
from src.onemcp.sandbox.mcp_server import McpServer
from src.onemcp.util.env import ONEMCP_SRC_ROOT

logger = logging.getLogger(__name__)

DISCOVERY_PROMPT_FILE_PATH = os.path.join(
    ONEMCP_SRC_ROOT, "sandbox", "discovery-prompt-header.md"
)
INSTALL_MCP_DOCKERFILE_PATH = os.path.join(
    ONEMCP_SRC_ROOT, "sandbox", "install_mcp.dockerfile"
)
SETUP_SCRIPT_TEMPLATE_PATH = os.path.join(
    ONEMCP_SRC_ROOT, "sandbox", "try-install-mcp-server.sh"
)
USE_HEURISTIC_DISCOVERY = (
    os.getenv("USE_HEURISTIC_DISCOVERY", "false").lower() == "true"
)


class ReadmeNotFound(Exception):
    pass


class DockerSandboxError(Exception):
    """Base exception for Docker sandbox operations."""

    pass


class DockerSandboxRegistry:
    """Docker-based sandbox for MCP servers."""

    def __init__(self, base_port: int = 8000, max_instances: int = 10):
        """Initialize the Docker sandbox.

        Args:
            base_port: Starting port for sandbox instances
            max_instances: Maximum number of concurrent sandbox instances
        """
        self.base_port = base_port
        self.max_instances = max_instances
        self.instances: dict[str, tuple[DockerContainer, McpServer]] = {}
        self.used_ports: set = set()
        self._lock = asyncio.Lock()

    async def discover(
        self, repository_url: str, repository_readme: str
    ) -> dict[str, Any]:
        """Discover capabilities and setup instructions for an MCP Server.

        Args:
            repository_url: URL of the repository to discover
            repository_readme: Contents of the repository's README

        Returns:
            Dictionary containing discovery information
        """
        try:
            logger.info(f"Discovering MCP server at {repository_url}")

            # Analyze repository structure
            discovery_info = await self._analyze_repository(
                repository_url, repository_readme
            )

            return {
                "response_code": "200",
                "tools": discovery_info["tools"],
                "setup_script": discovery_info["setup_script"],
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
                container: DockerContainer = self._start_docker_container(
                    sandbox_id, bootstrap_metadata, port
                )

                # Create sandbox instance
                instance = McpServer(
                    endpoint=f"localhost:{port}",
                    status="running",
                )

                self.instances[sandbox_id] = (container, instance)
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

    async def call_tool(self, sandbox_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Call a tool exposed by an MCP server running in `sandbox_id`.

        Args:
            The tools/call payload of the MCP protocol.

        Returns:
            The response for the tool execution.
        """
        logger.info(
            "Calling tool {} for sandbox ID: {}".format(
                body["params"]["name"], sandbox_id
            )
        )

        (container, instance) = self.instances.get(sandbox_id, [None, None])

        if instance is not None and container is not None:
            response = instance.call_tool(container, body)
        else:
            return {
                "response_code": "404",
                "error_description": f"Sandbox {sandbox_id} not found",
            }

        return {"response": response}

    async def get_tools(self, sandbox_id: str) -> dict[str, Any]:
        """Get the tools exposed by an MCP server.

        Args:
            sandbox_id: ID of the sandbox to query

        Returns:
            List of available tools
        """
        logger.info(f"Getting tools for sandbox ID: {sandbox_id}")
        (container, instance) = self.instances.get(sandbox_id, [None, None])

        if container is not None and instance is not None:
            tools = instance.get_tools(container)
            logger.info(f"Got tools: {tools}")
        else:
            return {
                "response_code": "404",
                "error_description": f"Sandbox {sandbox_id} not found",
            }

        return {"tools": tools}

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

                container, instance = self.instances[sandbox_id]
                await container.stop()

                logger.info(f"Stopped sandbox {sandbox_id}")

                return {"response_code": "200"}

            except Exception as e:
                logger.error(f"Failed to stop sandbox {sandbox_id}: {e}")
                return {
                    "response_code": "500",
                    "error_description": f"Failed to stop sandbox: {str(e)}",
                }

    async def cleanup(self, sandbox_id: str) -> None:
        """Clean up resources for a specific sandbox instance.

        Args:
            sandbox_id: ID of the sandbox to clean up
        """
        async with self._lock:
            if sandbox_id in self.instances:
                container, _ = self.instances[sandbox_id]

                await container.remove()
                logger.info(f"Cleaned up sandbox {sandbox_id}")

                await container.prune_images()
                logger.info("Removed orphaned images")

                self.used_ports.discard(container.port)
                del self.instances[sandbox_id]

            else:
                logger.warning(f"Sandbox {sandbox_id} not found for cleanup")

    async def cleanup_all(self) -> None:
        """Stop all running sandbox instances."""
        sandbox_ids = list(self.instances.keys())
        for sandbox_id in sandbox_ids:
            await self.stop(sandbox_id)
            await self.cleanup(sandbox_id)

    def _allocate_port(self) -> Optional[int]:
        """Allocate an available port for a new sandbox instance."""
        for port in range(self.base_port, self.base_port + 1000):
            if port not in self.used_ports:
                return port
        return None

    def _build_prompt(self, repository_url: str, repository_readme: str) -> str:
        prompt = f"The GitHub URL for the MCP server is {repository_url}. Here "
        prompt += f"is the README:\n{repository_readme}"

        return prompt

    def _generate_dockerfile(self, setup_script: str, image_tag: str) -> None:
        dockerfile_path = INSTALL_MCP_DOCKERFILE_PATH

        logger.info(f"Generating docker file (tag={image_tag}, path={dockerfile_path})")

        # Dump the setup script on a temporary file that we delete afterwards.
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp.write(setup_script)
            tmp.flush()

            tmp_name_basename = os.path.basename(tmp.name)
            tmp_name_dirname = os.path.dirname(tmp.name)
            docker_cmd = [
                "docker",
                "build",
                f"-t {image_tag}",
                f"-f {dockerfile_path}",
                f"--build-arg SCRIPT_PATH={tmp_name_basename}",
                f"--build-context scriptctx={tmp_name_dirname}",
                ".",
            ]

            docker_cmd_str = " ".join(docker_cmd)
            logger.info(f"docker_cmd: {docker_cmd_str}")
            subprocess.run(docker_cmd_str, shell=True, check=True)

            logger.info(f"Generated dockerfile at: {image_tag}")

    def get_image_tag_from_repo_url(self, repository_url: str) -> str:
        domain = "github.com/"
        idx = repository_url.find(domain) + len(domain)
        version = "v1"
        return f"onemcp/{domain}{repository_url[idx:]}:{version}"

    def ask_openai(self, repository_url: str, repository_readme: str) -> str:
        # First get the repository readme file.
        prompt = self._build_prompt(repository_url, repository_readme)

        system_prompt_file = Path(DISCOVERY_PROMPT_FILE_PATH)
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

        return setup_script

    def try_template_file(self, repository_url: str) -> str:
        # Read the template file
        template_file_path = Path(SETUP_SCRIPT_TEMPLATE_PATH)

        # Add the repository URL to the template
        if not template_file_path.exists():
            raise Exception(f"Error: File {template_file_path} does not exist.")
        template_content = template_file_path.read_text()
        setup_script = template_content.replace(
            "REPOSITORY_URL=", f"REPOSITORY_URL={repository_url}"
        )
        return setup_script

    async def _analyze_repository(
        self, repository_url: str, repository_readme: str
    ) -> dict[str, Any]:
        """Analyze repository to extract MCP server information.

        Args:
            repo_path: Path to the cloned repository

        Returns:
            Dictionary containing analysis results
        """

        if USE_HEURISTIC_DISCOVERY:
            # Use the template file to generate the setup script.
            logger.info(
                f"Using template file to generate setup script for {repository_url}"
            )
            setup_script = self.try_template_file(repository_url)
        else:
            # Ask OpenAI to generate the setup script.
            logger.info(f"Using OpenAI to generate setup script for {repository_url}")
            setup_script = self.ask_openai(repository_url, repository_readme)

        logger.debug(f"Generated set-up script for MCP server at url: {repository_url}")
        logger.debug(f"{setup_script}")

        # Generate temporary dockerfile from the set-up.
        container_image_tag = self.get_image_tag_from_repo_url(repository_url)
        self._generate_dockerfile(setup_script, container_image_tag)

        overview = "MCP Server Repository"
        tools: list[Any] = []
        # TODO: update
        bootstrap_metadata = {
            "container_image_tag": container_image_tag,
        }

        # Start docker container
        response = await self.start(bootstrap_metadata)
        sandbox_id = response.get("sandbox_id", "")

        (container, instance) = self.instances.get(sandbox_id, [None, None])
        try:
            if container is not None and instance is not None:
                tools = instance.get_tools(container)
            else:
                return {
                    "response_code": "404",
                    "error_description": f"Sandbox {sandbox_id} not found",
                }
        except Exception:
            logger.error(
                f"Error getting tools for sandbox {sandbox_id} from repo {repository_url}"
            )

            # Attempt to stop the sandbox and check for errors.
            stop_response: dict[str, Any] = await self.stop(sandbox_id)
            if stop_response.get("response_code") != "200":
                logger.error(
                    f"Failed to stop sandbox {sandbox_id} after error: {stop_response}"
                )

            # Clean up the sandbox instance.
            await self.cleanup(sandbox_id)

            return {
                "response_code": "500",
                "error_description": "Failed to retrieve tools from MCP server",
            }

        await self.stop(sandbox_id)

        print(f"Got tools: {tools}")

        return {
            "overview": overview,
            "tools": tools,
            "bootstrap_metadata": bootstrap_metadata,
            "setup_script": setup_script,
        }

    def _start_docker_container(
        self, sandbox_id: str, bootstrap_metadata: dict[str, Any], port: int
    ) -> DockerContainer:
        container: DockerContainer = DockerContainer()
        container.start(
            sandbox_id=sandbox_id,
            bootstrap_metadata=bootstrap_metadata,
            port=port,
        )
        return container
