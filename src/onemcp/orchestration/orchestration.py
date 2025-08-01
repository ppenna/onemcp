import json
import logging
import pathlib
import re
import sys

import pydantic_core

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from collections.abc import Sequence
from itertools import chain
from typing import Any

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
from mcp.server.fastmcp.server import Context
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import (
    EmbeddedResource,
    ImageContent,
    SamplingMessage,
    TextContent,
)

# from qdrant_client import QdrantClient, models
# from sentence_transformers import SentenceTransformer
from onemcp import Registry, ToolEntry


class MockSandbox:
    """A mock sandbox for testing purposes."""

    async def call_tool(self, sandbox_id: str, name: str, args: dict[str, Any]) -> Any:
        print(
            f"Mock call to tool: {name} with args: {args} and sandbox_id: {sandbox_id}"
        )
        return f"Mock response from {name} with args {args} and sandbox_id {sandbox_id}"

    async def run_server(self, bootstrap_metadata: dict[str, str]) -> str:
        print(f"Mock sandbox server is running with metadata: {bootstrap_metadata}")
        return "sanbox-server-id"


class LocalState:
    """A simple class to hold local state for the MCP server."""

    def __init__(self) -> None:
        self._dynamic_tools: list[types.Tool] = []
        self._lookup_tools: dict[str, types.Tool] = {}
        self._available_servers: set[str] = set()
        self._available_tools: dict[str, list[types.Tool]] = {}
        self._id_url_map: dict[str, str] = {}
        self._url_id_map: dict[str, str] = {}

        # self._rag = QdrantClient(":memory:")  # Create in-memory Qdrant instance
        # self._encoder = SentenceTransformer("thenlper/gte-small")

        # self._rag.create_collection(
        #     collection_name="tools",
        #     vectors_config=models.VectorParams(
        #         size=self._encoder.get_sentence_embedding_dimension(),
        #         distance=models.Distance.COSINE,
        #     ),
        # )

    @property
    def dynamic_tools(self) -> list[types.Tool]:
        return self._dynamic_tools

    def clear_dynamic(self) -> None:
        self._dynamic_tools.clear()

    def add_dynamic(self, tool: types.Tool) -> None:
        self._dynamic_tools.append(tool)

    # add/remove entire MCP servers
    def has_server(self, server: str) -> bool:
        return server in self._available_servers

    def add_server(
        self, sandbox_id: str, server_url: str, tools: list[types.Tool]
    ) -> None:
        self._available_servers.add(server_url)
        self._available_tools[server_url] = tools
        self._id_url_map[sandbox_id] = server_url
        self._url_id_map[server_url] = sandbox_id

        for tool in tools:
            self._lookup_tools[tool.name] = tool
            tool.sandbox_id = sandbox_id

        # self._rag.upload_points(
        #     collection_name="tools",
        #     points=[
        #         models.PointStruct(
        #             id=(server, tool.name),
        #             vector=self._encoder.encode(tool.description).tolist(),
        #             payload=tool,
        #         )
        #         for i, tool in enumerate(tools)
        #     ],
        # )

    def remove_server(self, server: str) -> None:
        if server in self._available_servers:
            self._available_servers.remove(server)
            self._available_tools.pop(server, None)

        # TODO: remove all tools from dynamic tools and lookup tools
        # TODO: remove from Qdrant collection

    # lookup tools by fuzzy search
    def find_tools(self, query: str, k: int = 3) -> list[types.Tool]:
        """Find tools by fuzzy search."""
        # results = self._rag.query_points(
        #     collection_name="tools", query=self._encoder.encode(query).tolist(), limit=3
        # )

        # return results.points
        return []

    def get_tool(self, name: str) -> types.Tool | None:
        """Get a tool by name."""
        if name in self._lookup_tools:
            return self._lookup_tools[name]
        return None


logger = logging.getLogger(__name__)
server = FastMCP("OneMCP")
local_state = LocalState()


def extract_code_blocks(markdown_text: str) -> list[dict]:
    """Extract code blocks from markdown text."""
    code_block_pattern = r"```(\w+)?\n(.*?)```"
    matches = re.findall(code_block_pattern, markdown_text, re.DOTALL)

    # Convert matches into a structured JSON format
    code_blocks = [
        {"language": match[0] or "plaintext", "code": match[1].strip()}
        for match in matches
    ]
    return code_blocks


async def guess_required_tool_descriptions(
    prompt: str, files: list[str], context: Context
) -> list[str]:
    """Guess high-level required tool descriptions based on the prompt."""

    # Get the path to the prompt template relative to this file
    prompt_path = pathlib.Path(__file__).parent / "tool_extraction.prompt.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")
    prompt = prompt_template.format(
        user_prompt=prompt, context=(", ".join(files) if files else "")
    )

    # MCP sampling for LLM callback
    result = await context.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=100,
    )

    # Assume result.content.text is a JSON array string
    try:
        if result.content.type == "text":
            result.content.text = extract_code_blocks(result.content.text)[0]["code"]

            print(f"Parsing tools from: {result.content.text}")

            tools = json.loads(result.content.text)
            if isinstance(tools, list):
                extracted_tools = [
                    tool["type"] + ": " + tool["context"] for tool in tools
                ]
            else:
                extracted_tools = [str(tools)]
        else:
            extracted_tools = [str(result.content)]
    except Exception as e:
        extracted_tools = [f"Failed to parse tools: {str(e)}"]

    return extracted_tools


##
## The OneMCP tool
##
async def suggest(prompt: str, files: list[str], ctx: Context) -> list[base.Message]:
    """Takes the user prompt and suggests which MCP tools would be appropriate."""

    # 1. Extract tool descriptions from the prompt
    extracted_tool_descriptions = await guess_required_tool_descriptions(
        prompt, files, ctx
    )
    print(f"Extracted tools: {', '.join(extracted_tool_descriptions)}")

    output = "Suggested tools based on your query:\n"
    servers = set()
    suggested_tools: set[ToolEntry] = set()

    # 2. Check local state for existing tools
    # for tool_description in extracted_tool_descriptions:
    #     found_existing_tools = local_state.find_tools(tool_description)

    #     for existing_tool in found_existing_tools:
    #         print(f"Found local tool: {existing_tool.name}")
    #         suggested_tools.add(existing_tool)

    # TODO: can I skip registry search if tools already found?

    # 3. Search the registry for suggested tools
    registry = Registry()
    for tool_description in extracted_tool_descriptions:
        found_registry_tools = registry.find_tools(query=tool_description, k=3)

        if found_registry_tools:
            output += f"\n'{tool_description}':"

            for entry in found_registry_tools:
                print(
                    f"Found registry tool: {entry.tool_name} on server: {entry.server_name}"
                )
                output += f"\n- {entry.tool_name} ({entry.server_name})"

                suggested_tools.add(entry)

                if not local_state.has_server(entry.server_url):
                    servers.add(entry.server_url)

    # install missing servers
    sandbox = MockSandbox()

    for server in servers:
        registry_server = registry.get_server(server)
        if registry_server:
            sandbox_id = await sandbox.run_server(registry_server.bootstrap_metadata)
            local_state.add_server(sandbox_id, server, registry_server.tools)

    # servers are already installed, so just add the tools
    local_state.clear_dynamic()

    for tool in suggested_tools:
        entry = local_state.get_tool(tool.tool_name)
        if entry:
            local_state.add_dynamic(entry)

    await ctx.request_context.session.send_tool_list_changed()

    return [
        base.Message(role="assistant", content=output),
        base.Message(
            role="user",
            content=f"Reevaluate the following with the new suggested tools, and call the appropriate tools if necessary: {prompt}",
        ),
    ]


async def sandbox_call(name: str, args: dict[str, Any], ctx: Context) -> Any:
    tool = local_state.get_tool(name)

    if tool:
        sandbox = MockSandbox()
        return await sandbox.call_tool(tool.sandbox_id, name, args)

    return [
        "This is a mock response from the sandbox MCP proxy for tool: "
        + name
        + " with args: "
        + str(args)
    ]


def _convert_to_content(
    result: Any,
) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Convert a result to a sequence of content objects."""
    if result is None:
        return []

    if isinstance(result, TextContent | ImageContent | EmbeddedResource):
        return [result]

    if isinstance(result, Image):
        return [result.to_image_content()]

    if isinstance(result, list | tuple):
        return list(chain.from_iterable(_convert_to_content(item) for item in result))

    if not isinstance(result, str):
        result = pydantic_core.to_json(result, fallback=str, indent=2).decode()

    return [TextContent(type="text", text=result)]


async def my_call_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Call a tool by name with arguments."""
    print(f"Calling tool: {name} with arguments: {arguments}")
    context = server.get_context()

    if name == "onemcp":
        result = await suggest(
            prompt=arguments.get("prompt", ""),
            files=arguments.get("files", []),
            ctx=context,
        )
    else:
        # pass the name and arguments to the sandbox MCP proxy
        result = await sandbox_call(name, arguments, context)

    # result = await self._tool_manager.call_tool(name, arguments, context=context)
    converted_result = _convert_to_content(result)
    return converted_result


async def my_list_tools() -> list[types.Tool]:
    """Lists all available tools."""
    print("Listing OneMCP tools...")

    return [
        types.Tool(
            name="onemcp",
            description="This tool dynamically registers and suggests MCP tools based on user prompts.",
            inputSchema={
                "properties": {
                    "prompt": {"title": "Prompt", "type": "string"},
                    "files": {
                        "items": {"type": "string"},
                        "title": "Files",
                        "type": "array",
                    },
                },
                "required": ["prompt", "files"],
                "title": "suggestArguments",
                "type": "object",
            },
            annotations=None,
        )
    ] + local_state.dynamic_tools


if __name__ == "__main__":
    server._mcp_server.list_tools()(my_list_tools)
    server._mcp_server.call_tool()(my_call_tool)
    server.run(transport="streamable-http")


# @server.tool()
# async def orchestrate(query: str, ctx: Context) -> list[base.Message]:
#     """Evaluates and dynamically orchestrates tools for a given user query."""
#     prompt = (
#         f"Analyze the query '{query}' and determine the appropriate tools to invoke."
#     )

#     result = await ctx.session.create_message(
#         messages=[
#             SamplingMessage(
#                 role="user",
#                 content=TextContent(type="text", text=prompt),
#             )
#         ],
#         max_tokens=150,
#     )

#     if result.content.type == "text":
#         return [base.Message(role="user", content=result.content.text)]
#     return [base.Message(role="user", content=str(result.content))]


# @server.tool()
# async def install(url: str, ctx: Context) -> list[base.Message]:
#     """Installs an MCP server."""

#     # 1. Check if already installed

#     registry = Registry()

#     try:
#         # 2. Otherwise, try to lookup registry for installation instructions
#         server = registry.health_check()

#         # TODO: 3. Otherwise, discovery prompt to determine installation instructions
#         if not server:
#             return [base.Message(role="assistant", content="Server not found in registry.")]

#         # 4. Try to install
#         # sandbox = MockSandbox()

#         return [base.Message(role="assistant", content="MCP server installation successful.\n Try to rerun the original user prompt.")]
#     except Exception as e:
#         return [base.Message(role="assistant", content=f"Installation failed: {str(e)}")]


# @server.tool()
# async def uninstall(query: str, ctx: Context) -> list[base.Message]:
#     """Uninstalls an MCP server."""
#     # Placeholder for uninstallation logic
#     # TODO: Implement actual uninstallation logic for MCP server
#     return [base.Message(role="user", content="Uninstallation logic not implemented")]


# @server.tool()
# async def status(query: str, ctx: Context) -> list[base.Message]:
#     """Checks the status of an MCP server."""
#     return [base.Message(role="user", content="hello")]


# @server.tool()
# async def search(query: str, ctx: Context) -> list[base.Message]:
#     """Searches for a specific resource or tool using the mock registry."""
#     try:
#         # Initialize mock registry with some sample servers
#         mockRegistry = MockRegistry()
#         mockRegistry.register_server(ServerEntry("weather-api", "https://github.com/weather/mcp-server"))
#         mockRegistry.register_server(ServerEntry("database-tools", "https://github.com/db/mcp-tools"))
#         mockRegistry.register_server(ServerEntry("file-manager", "https://github.com/files/mcp-manager"))
#         mockRegistry.register_server(ServerEntry("git-helper", "https://github.com/git/mcp-helper"))
#         mockRegistry.register_server(ServerEntry("web-scraper", "https://github.com/web/mcp-scraper"))

#         # Use the mockRegistry to find similar servers
#         similar_servers = mockRegistry.list_servers()

#         if not similar_servers:
#             return [base.Message(role="assistant", content=f"No servers found for query: {query}")]

#         # Format the results
#         results = []
#         results.append(f"Found {len(similar_servers)} similar servers for query '{query}':\n")

#         for i, server_entry in enumerate(similar_servers, 1):
#             results.append(f"{i}. {server_entry.name}")
#             results.append(f"   URL: {server_entry.url}")

#         response_text = "\n".join(results)
#         return [base.Message(role="assistant", content=response_text)]

#     except Exception as e:
#         return [base.Message(role="assistant", content=f"Search failed: {str(e)}")]


# @server.prompt()
# def tool_extraction(text: str) -> str:
#     """Extracts relevant tools and resources based on user input."""
#     prompt_path = pathlib.Path(__file__).parent / "tool_extraction.prompt.md"
#     prompt_template = prompt_path.read_text(encoding="utf-8")
#     return prompt_template.format(user_prompt=text)
