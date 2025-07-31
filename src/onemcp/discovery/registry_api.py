from abc import ABC, abstractmethod
from typing import Optional


class ServerEntry:
    __slots__ = ("name", "url", "installation_instructions")

    def __init__(
        self, name: str, url: str, installation_instructions: Optional[str] = None
    ):
        self.name = name
        self.url = url
        self.installation_instructions = installation_instructions


class ToolEntry:
    __slots__ = ("tool_name", "tool_description", "server_name", "distance")

    def __init__(
        self, tool_name: str, tool_description: str, server_name: str, distance: float
    ):
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.server_name = server_name
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
