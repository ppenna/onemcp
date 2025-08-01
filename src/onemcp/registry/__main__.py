#!/usr/bin/env python3

import json

from src.onemcp.registry.server_registry import ServerRegistry, ServerRegistryError

# Test method for the server registry
# TODO: move to tests
if __name__ == "__main__":
    reg = ServerRegistry()

    print("1) Health:")
    try:
        print(json.dumps(reg.health(), indent=2))
    except ServerRegistryError as e:
        print("Health check failed:", e)
        raise SystemExit(1)

    test_server = {
        "codebase_url": "https://github.com/test/weather-api-mcp",
        "description": (
            "Weather API MCP Server - Provides access to current weather conditions, "
            "forecasts, and weather alerts for locations worldwide."
        ),
        "tools": [
            {
                "name": "get_current_weather",
                "description": "Current conditions for a location (temp, humidity, wind).",
            },
            {
                "name": "get_weather_forecast",
                "description": "7-day forecast for a location with highs/lows.",
            },
            {
                "name": "get_weather_alerts",
                "description": "Active weather alerts for a location or region.",
            },
        ],
    }

    print("\n2) Register server:")
    try:
        resp = reg.register_server(
            codebase_url=test_server["codebase_url"],
            description=test_server["description"],
            tools=test_server["tools"],
        )
        print(json.dumps(resp, indent=2))
    except ServerRegistryError as e:
        print("Register failed:", e)

    print("\n3) Find tools:")
    try:
        result = reg.find_tools(query="weather forecast temperature", k=3)
        print(json.dumps(result, indent=2))
    except ServerRegistryError as e:
        print("Find tools failed:", e)

    print("\n4) List servers:")
    try:
        servers = reg.list_servers()
        print(json.dumps(servers, indent=2))
    except ServerRegistryError as e:
        print("List servers failed:", e)

    print("\n5) Unregister (cleanup):")
    try:
        resp = reg.unregister_server(test_server["codebase_url"])
        print(json.dumps(resp, indent=2))
    except ServerRegistryError as e:
        print("Unregister failed:", e)

    print("\n6) Verify removal:")
    try:
        print("Exists?", reg.server_exists(test_server["codebase_url"]))
    except ServerRegistryError as e:
        print("Verify failed:", e)
