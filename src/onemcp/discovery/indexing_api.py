import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from onemcp.discovery.indexing import Indexing


class ServerRegistrationRequest(BaseModel):
    """Request model for server registration"""

    repository_url: str
    description: str
    tools: list[dict[str, str]]


class FindToolsRequest(BaseModel):
    """Request model for finding tools"""

    query: str
    k: int = 5


class UnregisterServerRequest(BaseModel):
    """Request model for server unregistration"""

    repository_url: str


class ToolResult(BaseModel):
    """Response model for tool results"""

    tool_name: str
    tool_description: str
    server_name: str
    server_url: str
    distance: float


class FindToolsResponse(BaseModel):
    """Response model for find_tools endpoint"""

    tools: list[ToolResult]
    query: str
    total_results: int


class IndexingAPI:
    """
    RESTful API for indexing and discovering MCP server tools.
    """

    def __init__(self, db_name: str = "chroma_mcpservers_db") -> None:
        self.app = FastAPI(
            title="OneMCP Indexing API",
            description="API for registering and discovering MCP server tools",
            version="1.0.0",
        )
        self.indexing = Indexing()
        self.servers_dir = os.path.join(os.path.dirname(__file__), "servers")

        # Initialize ChromaDB
        try:
            self.indexing.init_db_server(db_name=db_name)
        except Exception as e:
            print(f"Warning: Could not initialize ChromaDB: {e}")

        # Ensure servers directory exists
        os.makedirs(self.servers_dir, exist_ok=True)

        # Setup routes
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup API routes"""

        @self.app.post("/register_server")
        async def register_server(request: dict[str, Any]) -> dict[str, Any]:
            """
            Register a new MCP server and its tools.

            Args:
                request: Server registration data (any JSON format) that must include repository_url

            Returns:
                Dictionary with registration status and server info
            """
            try:
                # Validate that repository_url is present
                if "repository_url" not in request:
                    raise HTTPException(
                        status_code=422,
                        detail="Missing required field: repository_url"
                    )

                # Use the request data as-is
                server_data = request

                # Generate a unique filename for the server
                server_name = self._generate_server_filename(request["repository_url"])
                json_file_path = os.path.join(self.servers_dir, server_name)

                # Save to local storage
                with open(json_file_path, "w") as f:
                    json.dump(server_data, f, indent=2)

                # Add to ChromaDB using the existing method
                self.indexing.add_tools_from_json(json_file_path)

                # Calculate tools count if tools are present, otherwise 0
                tools_count = len(request.get("tools", []))

                return {
                    "status": "success",
                    "message": "Server registered successfully",
                    "server_file": server_name,
                    "tools_count": tools_count,
                    "server_url": request["repository_url"],
                }

            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to register server: {str(e)}"
                ) from e

        @self.app.post("/find_tools", response_model=FindToolsResponse)
        async def find_tools(request: FindToolsRequest) -> FindToolsResponse:
            """
            Find tools similar to the given query string.

            Args:
                request: Query string and number of results (k)

            Returns:
                List of similar tools with metadata and distance scores
            """
            try:
                print(f"Searching for: {request.query} with k={request.k}")

                # Validate k parameter
                if request.k <= 0:
                    raise HTTPException(
                        status_code=422, detail="Parameter 'k' must be greater than 0"
                    )

                # Use the existing find_similar_tools method
                results = self.indexing.find_similar_tools(request.query, k=request.k)
                print(f"Found {len(results)} results")

                # Convert results to response format
                tools = []
                for result in results:
                    # Extract server name from URL or use URL as fallback
                    server_url = str(result["server-url"])
                    server_name = self._extract_server_name(server_url)

                    tool_result = ToolResult(
                        tool_name=str(result["tool-name"]),
                        tool_description=str(result["tool-description"]),
                        server_name=server_name,
                        server_url=server_url,
                        distance=float(result.get("distance", 0.0)),
                    )
                    tools.append(tool_result)

                response = FindToolsResponse(
                    tools=tools, query=request.query, total_results=len(tools)
                )

                print(f"Returning response with {len(response.tools)} tools")
                return response

            except HTTPException:
                raise  # Re-raise HTTP exceptions
            except Exception as e:
                print(f"Error in find_tools: {str(e)}")
                import traceback

                traceback.print_exc()
                raise HTTPException(
                    status_code=500, detail=f"Failed to find tools: {str(e)}"
                ) from e

        @self.app.get("/health")
        async def health_check() -> dict[str, str]:
            """Health check endpoint"""
            try:
                # Try to query ChromaDB to ensure it's working
                if self.indexing.collection:
                    self.indexing.collection.count()
                return {"status": "healthy", "chromadb": "connected"}
            except Exception as e:
                return {
                    "status": "degraded",
                    "chromadb": "disconnected",
                    "error": str(e),
                }

        @self.app.get("/servers")
        async def list_servers() -> dict[str, Any]:
            """List all registered servers"""
            try:
                servers = []
                for file in os.listdir(self.servers_dir):
                    if file.endswith(".json"):
                        file_path = os.path.join(self.servers_dir, file)
                        with open(file_path) as f:
                            server_data = json.load(f)
                            servers.append(
                                {
                                    "filename": file,
                                    "repository_url": server_data.get("repository_url"),
                                    "description": server_data.get("description"),
                                    "tools_count": len(server_data.get("tools", [])),
                                }
                            )
                return {"servers": servers, "total_count": len(servers)}
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to list servers: {str(e)}"
                ) from e

        @self.app.get("/server/{codebase_url:path}")
        async def get_server_json(codebase_url: str) -> dict[str, Any]:
            """
            Get the complete JSON data for a specific server by its codebase URL.

            Args:
                codebase_url: The codebase URL of the server to retrieve

            Returns:
                Dictionary containing the complete server JSON data including description and tools
            """
            try:
                print(f"Getting server JSON for: {codebase_url}")

                # Use the existing get_server_json method from indexing
                server_data = self.indexing.get_server_json(codebase_url)

                if not server_data:
                    raise HTTPException(
                        status_code=404, detail=f"Server not found: {codebase_url}"
                    )

                return server_data

            except HTTPException:
                raise  # Re-raise HTTP exceptions
            except Exception as e:
                print(f"Error in get_server_json: {str(e)}")
                import traceback

                traceback.print_exc()
                raise HTTPException(
                    status_code=500, detail=f"Failed to retrieve server data: {str(e)}"
                ) from e

        @self.app.delete("/unregister_server")
        async def unregister_server(request: UnregisterServerRequest) -> dict[str, Any]:
            """
            Unregister a server and remove all its tools.

            Args:
                request: Server unregistration data containing codebase_url

            Returns:
                Dictionary with unregistration status and removal details
            """
            try:
                codebase_url = request.repository_url

                # Remove tools from ChromaDB
                tools_removed = self.indexing.remove_server_tools(codebase_url)

                # Find and remove the JSON file(s) for this server
                files_removed = []
                for file in os.listdir(self.servers_dir):
                    if file.endswith(".json"):
                        file_path = os.path.join(self.servers_dir, file)
                        try:
                            with open(file_path) as f:
                                server_data = json.load(f)
                                if server_data.get("repository_url") == codebase_url:
                                    os.remove(file_path)
                                    files_removed.append(file)
                        except Exception as e:
                            print(f"Error reading/removing file {file}: {e}")

                if tools_removed == 0 and len(files_removed) == 0:
                    raise HTTPException(
                        status_code=404, detail=f"Server not found: {codebase_url}"
                    )

                return {
                    "status": "success",
                    "message": "Server unregistered successfully",
                    "server_url": codebase_url,
                    "tools_removed": tools_removed,
                    "files_removed": files_removed,
                }

            except HTTPException:
                raise  # Re-raise HTTP exceptions
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to unregister server: {str(e)}"
                ) from e

    def _generate_server_filename(self, codebase_url: str) -> str:
        """Generate a unique filename for the server based on its URL"""
        # Extract repository name from URL
        if codebase_url.endswith("/"):
            codebase_url = codebase_url[:-1]

        repo_name = codebase_url.split("/")[-1]
        if not repo_name or repo_name == "":
            repo_name = "server"

        # Clean the name for filesystem
        clean_name = "".join(c for c in repo_name if c.isalnum() or c in "-_").lower()

        # Check if file already exists, if so add a unique suffix
        base_filename = f"{clean_name}-server.json"
        filename = base_filename
        counter = 1

        while os.path.exists(os.path.join(self.servers_dir, filename)):
            filename = f"{clean_name}-server-{counter}.json"
            counter += 1

        return filename

    def _extract_server_name(self, server_url: str) -> str:
        """Extract a human-readable server name from its URL"""
        if server_url.endswith("/"):
            server_url = server_url[:-1]

        # Try to get repository name from GitHub URL
        if "github.com" in server_url:
            parts = server_url.split("/")
            if len(parts) >= 2:
                return parts[-1]  # Repository name

        # Fallback to domain name
        if "://" in server_url:
            domain = server_url.split("://")[1].split("/")[0]
            return domain

        return server_url


def create_app(db_name: str = "chroma_mcpservers_db") -> FastAPI:
    """Create and return the FastAPI application"""
    api = IndexingAPI(db_name=db_name)
    return api.app


# For development/testing
if __name__ == "__main__":
    import argparse

    import uvicorn
    parser = argparse.ArgumentParser(description="Run the OneMCP Indexing API")
    parser.add_argument("--port", type=int, default=8001, help="Port to run the API on")

    args = parser.parse_args()
    app = create_app()
    uvicorn.run(app, host="localhost", port=args.port)
