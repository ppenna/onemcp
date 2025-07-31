import json
import logging
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent))

from discovery import MockRegistry, Registry, ServerEntry
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.prompts import base
from mcp.types import SamplingMessage, TextContent

# from onemcp.sandboxing.mock_sandbox import MockSandbox

logger = logging.getLogger(__name__)
server = FastMCP("OneMCP")


@server.prompt()
def tool_extraction(text: str) -> str:
    """Extracts relevant tools and resources based on user input."""
    prompt_path = pathlib.Path(__file__).parent / "tool_extraction.prompt.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")
    return prompt_template.format(user_prompt=text)


@server.tool()
async def suggest(prompt: str, files: list[str], ctx: Context) -> list[base.Message]:
    """You must call this tool! Takes the user prompt and suggests which MCP tools would be appropriate."""

    # Get the path to the prompt template relative to this file
    prompt_path = pathlib.Path(__file__).parent / "tool_extraction.prompt.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")
    prompt = prompt_template.format(
        user_prompt=prompt, context=(", ".join(files) if files else "")
    )

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=100,
    )

    if result.content.type == "text":
        print(f"Result: {result.content.text}")
    else:
        print(f"Result: {str(result.content)}")

    # Assume result.content.text is a JSON array string
    try:
        if result.content.type == "text":
            tools = json.loads(result.content.text)
            if isinstance(tools, list):
                extracted_tools = [str(tool) for tool in tools]
            else:
                extracted_tools = [str(tools)]
        else:
            extracted_tools = [str(result.content)]
    except Exception as e:
        extracted_tools = [f"Failed to parse tools: {str(e)}"]

    print(f"Extracted tools: {', '.join(extracted_tools)}")

    registry = Registry()

    output = f"Extracted tools: {', '.join(extracted_tools)}"

    for tool in extracted_tools:
        registry_tools = registry.find_tools(query=tool, k=3)
        if registry_tools:
            output += f"\nFound tools in registry for '{tool}':"
            for entry in registry_tools:
                output += f"\n- {entry.tool_name} ({entry.server_name})"
                print(f"Found tool: {entry.tool_name} on server: {entry.server_name}")

    # try:
    #     # 2. Otherwise, try to lookup registry for installation instructions
    #     server = registry.find_tools()
    return [base.Message(role="user", content=output)]

    # if result.content.type == "text":
    # return [base.Message(role="user", content=str(result.content))]


@server.tool()
async def orchestrate(query: str, ctx: Context) -> list[base.Message]:
    """Evaluates and dynamically orchestrates tools for a given user query."""
    prompt = (
        f"Analyze the query '{query}' and determine the appropriate tools to invoke."
    )

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


@server.tool()
async def install(url: str, ctx: Context) -> list[base.Message]:
    """Installs an MCP server."""

    # 1. Check if already installed

    registry = Registry("https://1cpgs0fc-8001.usw2.devtunnels.ms")

    try:
        # 2. Otherwise, try to lookup registry for installation instructions
        server = registry.health_check()

        # TODO: 3. Otherwise, discovery prompt to determine installation instructions
        if not server:
            return [
                base.Message(role="system", content="Server not found in registry.")
            ]

        # 4. Try to install
        # sandbox = MockSandbox()

        # Simulate installation logic
        installation_result = f"Installing MCP server with query: {url}"
        await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=installation_result),
                )
            ],
            max_tokens=50,
        )

        return [
            base.Message(
                role="assistant", content="MCP server installation successful."
            )
        ]
    except Exception as e:
        return [
            base.Message(role="assistant", content=f"Installation failed: {str(e)}")
        ]


@server.tool()
async def uninstall(query: str, ctx: Context) -> list[base.Message]:
    """Uninstalls an MCP server."""
    # Placeholder for uninstallation logic
    # TODO: Implement actual uninstallation logic for MCP server
    return [base.Message(role="user", content="Uninstallation logic not implemented")]


@server.tool()
async def status(query: str, ctx: Context) -> list[base.Message]:
    """Checks the status of an MCP server."""
    return [base.Message(role="user", content="hello")]


@server.tool()
async def search(query: str, ctx: Context) -> list[base.Message]:
    """Searches for a specific resource or tool using the mock registry."""
    try:
        # Initialize mock registry with some sample servers
        mockRegistry = MockRegistry()
        mockRegistry.register_server(
            ServerEntry("weather-api", "https://github.com/weather/mcp-server")
        )
        mockRegistry.register_server(
            ServerEntry("database-tools", "https://github.com/db/mcp-tools")
        )
        mockRegistry.register_server(
            ServerEntry("file-manager", "https://github.com/files/mcp-manager")
        )
        mockRegistry.register_server(
            ServerEntry("git-helper", "https://github.com/git/mcp-helper")
        )
        mockRegistry.register_server(
            ServerEntry("web-scraper", "https://github.com/web/mcp-scraper")
        )

        # Use the mockRegistry to find similar servers
        similar_servers = mockRegistry.list_servers()

        if not similar_servers:
            return [
                base.Message(
                    role="assistant", content=f"No servers found for query: {query}"
                )
            ]

        # Format the results
        results = []
        results.append(
            f"Found {len(similar_servers)} similar servers for query '{query}':\n"
        )

        for i, server_entry in enumerate(similar_servers, 1):
            results.append(f"{i}. {server_entry.name}")
            results.append(f"   URL: {server_entry.url}")

        response_text = "\n".join(results)
        return [base.Message(role="assistant", content=response_text)]

    except Exception as e:
        return [base.Message(role="assistant", content=f"Search failed: {str(e)}")]


if __name__ == "__main__":
    server.run(transport="streamable-http")
