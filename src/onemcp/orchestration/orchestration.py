from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.prompts import base
from mcp.types import SamplingMessage, TextContent

from ..discovery.mock_registry import MockRegistry

server = FastMCP(
    name="OneMCP Orchestrator",
    description="Dynamic MCP Orchestrator for managing tools and resources",
)

# Initialize mock registry with some sample servers
mockRegistry = MockRegistry()
mockRegistry.register_server("weather-api", "https://github.com/weather/mcp-server")
mockRegistry.register_server("database-tools", "https://github.com/db/mcp-tools")
mockRegistry.register_server("file-manager", "https://github.com/files/mcp-manager")
mockRegistry.register_server("git-helper", "https://github.com/git/mcp-helper")
mockRegistry.register_server("web-scraper", "https://github.com/web/mcp-scraper")


@server.tool()
async def plan(query: str, ctx: Context) -> list[base.Message]:
    """Gives a detailed orchestration plan for the given query."""

    prompt = f"Create a detailed orchestration plan for the query: {query}"

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
        return [base.Message(role="user", content=result.content.text)]
    return [base.Message(role="user", content=str(result.content))]


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
async def install(query: str, ctx: Context) -> list[base.Message]:
    """Installs an MCP server."""
    try:
        # Simulate installation logic
        installation_result = f"Installing MCP server with query: {query}"
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
            base.Message(role="assistant", content="MCP server installation successful.")
        ]
    except Exception as e:
        return [base.Message(role="assistant", content=f"Installation failed: {str(e)}")]


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
        # Use the mockRegistry to find similar servers
        similar_servers = mockRegistry.find_similar_servers(query, k=5)

        if not similar_servers:
            return [base.Message(role="assistant", content=f"No servers found for query: {query}")]

        # Format the results
        results = []
        results.append(f"Found {len(similar_servers)} similar servers for query '{query}':\n")

        for i, (server_entry, similarity_score) in enumerate(similar_servers, 1):
            results.append(f"{i}. {server_entry.name} (similarity: {similarity_score:.2f})")
            results.append(f"   URL: {server_entry.url}")

        response_text = "\n".join(results)
        return [base.Message(role="assistant", content=response_text)]

    except Exception as e:
        return [base.Message(role="assistant", content=f"Search failed: {str(e)}")]


if __name__ == "__main__":
    server.run(transport="streamable-http")
