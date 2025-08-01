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

from onemcp import Registry

logger = logging.getLogger(__name__)
server = FastMCP("OneMCP")
dynamic_tools = []

def extract_code_blocks(markdown_text: str) -> list[dict]:
    # Regular expression to match code blocks (```language ... ```)
    code_block_pattern = r"```(\w+)?\n(.*?)```"
    matches = re.findall(code_block_pattern, markdown_text, re.DOTALL)

    # Convert matches into a structured JSON format
    code_blocks = [{"language": match[0] or "plaintext", "code": match[1].strip()} for match in matches]
    return code_blocks

async def suggest(prompt: str, files: list[str], ctx: Context) -> list[base.Message]:
    """Takes the user prompt and suggests which MCP tools would be appropriate."""

    # Get the path to the prompt template relative to this file
    prompt_path = pathlib.Path(__file__).parent / "tool_extraction.prompt.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")
    prompt = prompt_template.format(user_prompt=prompt, context=(", ".join(files) if files else ""))

    result = await ctx.session.create_message(
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
                extracted_tools = [tool["type"] + ": " + tool["context"] for tool in tools]
            else:
                extracted_tools = [str(tools)]
        else:
            extracted_tools = [str(result.content)]
    except Exception as e:
        extracted_tools = [f"Failed to parse tools: {str(e)}"]

    print(f"Extracted tools: {', '.join(extracted_tools)}")

    registry = Registry()

    output = "Suggested tools based on your query:\n"
    #output = f"Extracted tools: {', '.join(extracted_tools)}"
    servers = set()

    dynamic_tools.clear()

    for tool in extracted_tools:
        registry_tools = registry.find_tools(query=tool, k=3)
        if registry_tools:
            output += f"\n'{tool}':"
            for entry in registry_tools:
                output += f"\n- {entry.tool_name} ({entry.server_name})"
                print(f"Found tool: {entry.tool_name} on server: {entry.server_name}")
                servers.add(entry.server_name)

                # TODO: get the tool schema from the registry
                dynamic_tools.append(
                    types.Tool(
                        name=entry.server_name + '_' + entry.tool_name,
                        description=entry.tool_description,
                        inputSchema={
                            "properties": {
                                "prompt": {"title": "Prompt", "type": "string"},
                                "files": {"items": {"type": "string"}, "title": "Files", "type": "array"},
                            },
                            "required": ["prompt", "files"],
                            "title": "suggestArguments",
                            "type": "object",
                        },
                        annotations=None,
                    )
                )


    #output += "\nSuggested MCP servers:\n" + "\n- ".join(servers) if servers else "No servers found."
    #output += "\n\n#mcp_onemcp_install these servers."

    await ctx.request_context.session.send_tool_list_changed()

    # try:
    #     # 2. Otherwise, try to lookup registry for installation instructions
    #     server = registry.find_tools()
    return [base.Message(role="assistant", content=output),
            base.Message(role="user", content="Please retry the original prompt with the suggested tools.")]


async def sandbox_call(name: str, args: dict[str, Any], ctx: Context) -> Any:
    return ["This is a mock response from the sandbox MCP proxy for tool: " + name + " with args: " + str(args)]


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
        return list(chain.from_iterable(_convert_to_content(item) for item in result))  # type: ignore[reportUnknownVariableType]

    if not isinstance(result, str):
        result = pydantic_core.to_json(result, fallback=str, indent=2).decode()

    return [TextContent(type="text", text=result)]


async def my_call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Call a tool by name with arguments."""
    print(f"Calling tool: {name} with arguments: {arguments}")
    context = server.get_context()

    if name == "onemcp":
        result = await suggest(prompt=arguments.get("prompt", ""), files=arguments.get("files", []), ctx=context)
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
            description="This my new tool.",
            inputSchema={
                "properties": {
                    "prompt": {"title": "Prompt", "type": "string"},
                    "files": {"items": {"type": "string"}, "title": "Files", "type": "array"},
                },
                "required": ["prompt", "files"],
                "title": "suggestArguments",
                "type": "object",
            },
            annotations=None,
        )
    ] + dynamic_tools  # type: ignore[return-value


if __name__ == "__main__":
    server._mcp_server.list_tools()(my_list_tools)
    server._mcp_server.call_tool()(my_call_tool)
    server.run(transport="streamable-http")






@server.tool()
async def orchestrate(query: str, ctx: Context) -> list[base.Message]:
    """Evaluates and dynamically orchestrates tools for a given user query."""
    prompt = f"Analyze the query '{query}' and determine the appropriate tools to invoke."

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=150,
    )

    if result.content.type == "text":
        return [base.Message(role="user", content=result.content.text)]
    return [base.Message(role="user", content=str(result.content))]


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