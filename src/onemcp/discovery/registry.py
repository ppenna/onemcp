from typing import Optional
from urllib.parse import quote

import mcp.types as types
import requests

from .registry_api import RegistryInterface, ServerEntry, ToolEntry


class Registry(RegistryInterface):
    """Class to test the OneMCP Indexing API endpoints via REST calls."""

    def __init__(
        self, base_url: str = "https://4k6k502m-8001.usw2.devtunnels.ms"
    ) -> None:
        self.base_url = base_url

    def health_check(self) -> Optional[tuple[int, str]]:
        try:
            response = requests.get(f"{self.base_url}/health")
            return response.status_code, response.json()
        except requests.exceptions.ConnectionError:
            print("Could not connect to the server.")
            return None

    def find_tools(self, query: str, k: int = 3) -> list[ToolEntry]:
        search_request = {"query": query, "k": k}
        try:
            response = requests.post(f"{self.base_url}/find_tools", json=search_request)
            result = response.json()

            tools = []
            for _, tool in enumerate(result["tools"], 1):
                entry = ToolEntry(
                    tool_name=tool["tool_name"],
                    tool_description=tool["tool_description"],
                    server_name=tool["server_name"],
                    distance=tool["distance"],
                )
                tools.append(entry)
            return tools
        except Exception as e:
            print(f"Error searching tools: {e}")
            return []

    def get_server(self, url: str) -> ServerEntry | None:
        try:
            response = requests.get(f"{self.base_url}/server/{quote(url, safe='')}")
            result = response.json()

            entry = ServerEntry(
                name=result.get("name", ""),
                url=result.get("repository_url", ""),
                installation_instructions=result.get("setup_script", ""),
            )
            for tool in result.get("tools", []):
                t = types.Tool(
                    name=tool.get("name", ""),
                    description=tool.get("description", ""),
                    inputSchema=tool.get("inputSchema", {}),
                    annotations=None,
                )
                entry.tools.append(t)

            return entry
        except Exception as e:
            print(f"Error getting server: {e}")
            return None

    def list_servers(self) -> list[ServerEntry]:
        try:
            response = requests.get(f"{self.base_url}/servers")
            result = response.json()

            servers = []
            for _, server in enumerate(result["servers"], 1):
                entry = ServerEntry(
                    name=server.get("filename", ""), url=server.get("codebase_url", "")
                )
                servers.append(entry)
            return servers
        except Exception as e:
            print(f"Error listing servers: {e}")
            return []

    def register_server(self, server_data: ServerEntry) -> Optional[tuple[int, str]]:
        try:
            response = requests.post(
                f"{self.base_url}/register_server", json=server_data
            )
            return response.status_code, response.json()
        except Exception as e:
            print(f"Error registering server: {e}")
            return None

    def unregister_server(self, codebase_url: str) -> Optional[dict]:
        try:
            response = requests.delete(
                f"{self.base_url}/unregister_server",
                json={"codebase_url": codebase_url},
            )
            return {"status_code": response.status_code, "response": response.json()}
        except Exception as e:
            print(f"Error unregistering server: {e}")
            return None


# main for testing purposes
if __name__ == "__main__":
    registry = Registry()
    print(registry.health_check())

    test = registry.list_servers()
    print(registry.get_server("https://github.com/guillochon/mlb-api-mcp"))
