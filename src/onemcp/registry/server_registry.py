from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any

import requests

BASE_URL: str = "https://klqnxwmj-8001.usw2.devtunnels.ms"


class ServerRegistryError(Exception):
    """Raised when an API call fails or returns an unexpected response."""


@dataclass
class ServerRegistry:
    """
    Thin client to interact with the OneMCP Indexing backend.

    Methods:
        - health()
        - register_server(...)
        - find_tools(query, k=3)
        - list_servers()
        - unregister_server(codebase_url)
        - server_exists(codebase_url)
    """

    base_url: str = BASE_URL
    timeout: float = 1500.0

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url.rstrip("/") + path

    def _parse_json(self, resp: requests.Response) -> Any:
        try:
            return resp.json()
        except ValueError as e:
            raise ServerRegistryError(
                f"Expected JSON from {resp.request.method} {resp.request.url}, "
                f"got status {resp.status_code} and non-JSON body: {resp.text[:200]}"
            ) from e

    def _check_status(self, resp: requests.Response) -> None:
        if 200 <= resp.status_code < 300:
            return
        # Try to extract error JSON for better diagnostics
        body: dict[str, Any] | None = None
        try:
            body = resp.json()
        except Exception:
            pass
        detail = json.dumps(body, indent=2) if body else resp.text
        raise ServerRegistryError(
            f"HTTP {resp.status_code} for {resp.request.method} {resp.request.url}\n{detail}"
        )

    def _get_json(self, path: str) -> Any:
        try:
            resp = self._session.get(self._url(path), timeout=self.timeout)
        except requests.RequestException as e:
            raise ServerRegistryError(f"GET {path} failed: {e}") from e
        self._check_status(resp)
        return self._parse_json(resp)

    def _post_json(self, path: str, *, json: dict[str, Any]) -> Any:
        try:
            resp = self._session.post(self._url(path), json=json, timeout=self.timeout)
        except requests.RequestException as e:
            raise ServerRegistryError(f"POST {path} failed: {e}") from e
        self._check_status(resp)
        return self._parse_json(resp)

    def _delete_json(self, path: str, *, json: dict[str, Any]) -> Any:
        try:
            resp = self._session.delete(
                self._url(path), json=json, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise ServerRegistryError(f"DELETE {path} failed: {e}") from e
        self._check_status(resp)
        return self._parse_json(resp)

    def __post_init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    def health(self) -> Any:
        """GET /health -> dict"""
        return self._get_json("/health")

    def register_server(
        self,
        codebase_url: str,
        description: str,
        tools: list[dict[str, str]],
    ) -> Any:
        """
        POST /register_server with:
          {
            "codebase_url": "...",
            "description": "...",
            "tools": [{"name": "...", "description": "..."}, ...]
          }
        """
        payload = {
            "repository_url": codebase_url,
            "description": description,
            "tools": tools,
        }
        return self._post_json("/register_server", json=payload)

    def find_tools(self, query: str, k: int = 3) -> Any:
        """POST /find_tools -> dict(result); payload: {"query": str, "k": int}"""
        payload = {"query": query, "k": k}
        return self._post_json("/find_tools", json=payload)

    def list_servers(self) -> Any:
        """GET /servers -> dict(result)"""
        return self._get_json("/servers")

    def unregister_server(self, codebase_url: str) -> Any:
        """DELETE /unregister_server with {"codebase_url": "..."}"""
        payload = {"repository_url": codebase_url}
        return self._delete_json("/unregister_server", json=payload)

    def server_exists(self, repository_url: str) -> bool:
        """Convenience helper that checks whether a server is currently registered."""
        data = self.list_servers()
        servers = data.get("servers", [])
        return any(s.get("repository_url") == repository_url for s in servers)


# add main function for testing purposes
if __name__ == "__main__":
    # load the explored-mcp-server.json file and each server's tools
    registry = ServerRegistry()

    # load json file
    prompt_path = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / "assets"
        / "explored-mcp-server.json"
    )

    print(f"Loading server data from: {prompt_path}")

    # open json file and fix any json errors
    with open(prompt_path, encoding="utf-8") as f:
        # load as text first to ensure it's valid JSON
        json_text = f.read()
        json_text = re.sub("}\n{", "},\n{", json_text)
        json_text = "[" + json_text + "]"

        server_data = json.loads(json_text)

    # with open(prompt_path, encoding="utf-8") as f:
    #     server_data = json.load(f)

    server_list = registry.list_servers()

    # remove all for testing purposes
    for server in server_list["servers"]:
        print(f"Unregistering server: {server['repository_url']}")
        registry.unregister_server(server["repository_url"])

    # server_data is a json array, want to register each server
    for server in server_data:
        server["name"] = server.get(
            "name", server["bootstrap_metadata"]["repository_url"]
        )
        server["description"] = server.get(
            "description", server["bootstrap_metadata"]["repository_url"]
        )
        server["repository_url"] = server["bootstrap_metadata"]["repository_url"]
        print(f"Registering server: {server['repository_url']}")
        registry._post_json("/register_server", json=server)
