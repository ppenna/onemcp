from abc import ABC, abstractmethod
from typing import Optional

import mcp.types as types


class ServerEntry:
    __slots__ = ("name", "url", "bootstrap_metadata", "tools")

    def __init__(self, name: str, url: str, bootstrap_metadata: dict[str, str]):
        self.name = name
        self.url = url
        self.bootstrap_metadata = bootstrap_metadata
        self.tools: list[types.Tool] = []


class ToolEntry:
    __slots__ = (
        "tool_name",
        "tool_description",
        "server_name",
        "server_url",
        "distance",
    )

    def __init__(
        self,
        tool_name: str,
        tool_description: str,
        server_name: str,
        server_url: str,
        distance: float,
    ):
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.server_name = server_name
        self.server_url = server_url
        self.distance = distance


class RegistryInterface(ABC):
    @abstractmethod
    def health_check(self) -> Optional[tuple[int, str]]:
        pass

    @abstractmethod
    def list_servers(self) -> list[ServerEntry]:
        pass

    @abstractmethod
    def find_tools(self, query: str, k: int = 5) -> list[ToolEntry]:
        pass

    @abstractmethod
    def register_server(self, server_data: ServerEntry) -> Optional[tuple[int, str]]:
        pass

    @abstractmethod
    def unregister_server(self, codebase_url: str) -> Optional[dict]:
        pass
