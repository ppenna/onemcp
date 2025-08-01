from difflib import SequenceMatcher
from typing import Optional

from .registry_api import RegistryInterface, ServerEntry, ToolEntry


class MockRegistry(RegistryInterface):
    def __init__(self) -> None:
        self._servers: dict[str, ServerEntry] = {}

    def health_check(self) -> Optional[tuple[int, str]]:
        # Simulate a health check
        return 200, "Mock registry is healthy"

    def get_server(self, name: str) -> ServerEntry:
        return self._servers[name]

    def list_servers(self) -> list[ServerEntry]:
        return list(self._servers.values())

    def find_tools(self, query: str, k: int = 5) -> list[ToolEntry]:
        def similarity(s1: str, s2: str) -> float:
            return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

        # Calculate similarity scores for all servers
        scored_servers = [
            (server, similarity(query, server.name))
            for server in self._servers.values()
        ]

        # Sort by similarity score in descending order and take top k
        servers = sorted(scored_servers, key=lambda x: x[1], reverse=True)[:k]
        # convert to list of ToolEntry
        return [
            ToolEntry(
                tool_name=server.name,
                tool_description="",
                server_name=server.name,
                server_url=server.url,
                distance=score,
            )
            for server, score in servers
            if score > 0.0
        ]

    def register_server(self, server_data: ServerEntry) -> None:
        self._servers[server_data.url] = server_data

    def unregister_server(self, codebase_url: str) -> Optional[dict]:
        for url, server in list(self._servers.items()):
            if url == codebase_url:
                del self._servers[url]
                return {
                    "status": "success",
                    "message": f"Server {server.name} unregistered.",
                }
        return {"status": "error", "message": "Server not found."}
