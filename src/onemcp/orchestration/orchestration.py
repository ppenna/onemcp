from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.prompts import base
from mcp.types import SamplingMessage, TextContent

server = FastMCP(
    name="OneMCP Orchestrator",
    description="Dynamic MCP Orchestrator for managing tools and resources",
)

@server.tool()
async def plan(query: str, ctx: Context) -> list[base.Message]:
    """Gives a detailed orchestration plan for the given query."""

    prompt = f"Write a short poem about {query}"

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
    return [base.Message(role="user", content="hello")]


@server.tool()
async def install(query: str, ctx: Context) -> list[base.Message]:
    """Installs an MCP server."""
    return [base.Message(role="user", content="hello")]


@server.tool()
async def uninstall(query: str, ctx: Context) -> list[base.Message]:
    """Uninstalls an MCP server."""
    return [base.Message(role="user", content="hello")]


@server.tool()
async def status(query: str, ctx: Context) -> list[base.Message]:
    """Checks the status of an MCP server."""
    return [base.Message(role="user", content="hello")]


@server.tool()
async def search(query: str, ctx: Context) -> list[base.Message]:
    """Searches for a specific resource or tool."""
    return [base.Message(role="user", content="hello")]


if __name__ == "__main__":
    server.run(transport='streamable-http')
