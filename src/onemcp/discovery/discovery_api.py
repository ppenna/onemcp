from abc import ABC, abstractmethod


class ServerEntry:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url


class RegistryInterface(ABC):
    @abstractmethod
    def register_server(self, name: str, url: str) -> None:
        pass

    @abstractmethod
    def get_server(self, name: str) -> ServerEntry:
        pass

    @abstractmethod
    def list_servers(self) -> list[ServerEntry]:
        pass

    @abstractmethod
    def find_similar_servers(
        self, query: str, k: int = 5
    ) -> list[tuple[ServerEntry, float]]:
        pass
