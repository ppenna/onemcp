from abc import ABC, abstractmethod
from typing import Union

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    response_code: str
    error_description: str


##
## Discover
##
class DiscoverRequest(BaseModel):
    repository_url: str


class Tool(BaseModel):
    name: str
    description: str


class BootstrapMetadata(BaseModel):
    version: str
    config: dict[str, str]


class DiscoverResponse(BaseModel):
    response_code: str
    overview: str
    tools: list[Tool]
    bootstrap_metadata: BootstrapMetadata


##
## Start
##
class StartRequest(BaseModel):
    bootstrap_metadata: BootstrapMetadata


class StartResponse(BaseModel):
    response_code: str
    sandbox_id: str
    endpoint: str


##
## Stop
##
class StopRequest(BaseModel):
    sandbox_id: str


class StopResponse(BaseModel):
    response_code: str


##
## Sandbox Interface
##
class SandboxInterface(ABC):
    @abstractmethod
    def discover(self, payload: DiscoverRequest) -> DiscoverResponse:
        pass

    @abstractmethod
    def start(self, payload: StartRequest) -> StartResponse:
        pass

    @abstractmethod
    def stop(self, payload: StopRequest) -> Union[StopResponse, ErrorResponse]:
        pass
