#!/usr/bin/env python3
"""
Test script for the OneMCP Indexing API
"""

import json

import requests


def test_api():
    """Test the indexing API endpoints"""
    base_url = "http://localhost:8001"

    print("🔍 Testing OneMCP Indexing API")
    print("=" * 50)

    # Test health check
    print("\n1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("❌ API is not running. Start it with: python indexing_api.py")
        return

    # Test registering a new server
    print("\n2. Testing server registration...")
    test_server = {
        "codebase_url": "https://github.com/test/weather-api-mcp",
        "description": "Weather API MCP Server - Provides access to current weather conditions, forecasts, and weather alerts for locations worldwide. Features include temperature, humidity, precipitation, wind speed, and severe weather notifications.",
        "tools": [
            {
                "name": "get_current_weather",
                "description": "Get current weather conditions for a specific location including temperature, humidity, and wind speed.",
            },
            {
                "name": "get_weather_forecast",
                "description": "Get weather forecast for the next 7 days for a specific location with daily temperature highs and lows.",
            },
            {
                "name": "get_weather_alerts",
                "description": "Get active weather alerts and warnings for a specific location or region.",
            },
        ],
    }

    try:
        response = requests.post(f"{base_url}/register_server", json=test_server)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Error registering server: {e}")

    # Test finding tools
    print("\n3. Testing tool search...")
    search_request = {"query": "weather forecast temperature", "k": 3}

    try:
        response = requests.post(f"{base_url}/find_tools", json=search_request)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Query: {result['query']}")
        print(f"Total results: {result['total_results']}")
        print("\nFound tools:")
        for i, tool in enumerate(result["tools"], 1):
            print(f"  {i}. {tool['tool_name']}")
            print(f"     Description: {tool['tool_description']}")
            print(f"     Server: {tool['server_name']}")
            print(f"     Distance: {tool['distance']:.4f}")
            print()
    except Exception as e:
        print(f"❌ Error searching tools: {e}")

    # Test listing servers
    print("\n4. Testing server listing...")
    try:
        response = requests.get(f"{base_url}/servers")
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Total servers: {result['total_count']}")
        print("\nRegistered servers:")
        for i, server in enumerate(result["servers"], 1):
            print(f"  {i}. {server['filename']}")
            print(f"     URL: {server['codebase_url']}")
            print(f"     Tools: {server['tools_count']}")
            print()
    except Exception as e:
        print(f"❌ Error listing servers: {e}")

    # Test getting server JSON
    print("\n5. Testing get server JSON...")
    try:
        # URL encode the codebase URL for the path parameter
        import urllib.parse
        encoded_url = urllib.parse.quote(test_server["codebase_url"], safe='')
        response = requests.get(f"{base_url}/server/{encoded_url}")
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"Server URL: {result.get('codebase-url')}")
            print(f"Description: {result.get('description')[:100]}...")
            print(f"Tools count: {len(result.get('tools', []))}")
            print("\nTools in server:")
            for i, tool in enumerate(result.get('tools', []), 1):
                print(f"  {i}. {tool.get('name')}")
                print(f"     Description: {tool.get('description')[:80]}...")
                print()
            print("✅ Successfully retrieved server JSON")
        else:
            print(f"❌ Failed to get server JSON: {response.json()}")

    except Exception as e:
        print(f"❌ Error getting server JSON: {e}")

    # Test getting non-existent server JSON
    print("\n6. Testing get non-existent server JSON...")
    try:
        import urllib.parse
        non_existent_url = urllib.parse.quote("https://github.com/nonexistent/repo", safe='')
        response = requests.get(f"{base_url}/server/{non_existent_url}")
        print(f"Status: {response.status_code}")

        if response.status_code == 404:
            print("✅ Correctly returned 404 for non-existent server")
            print(f"Response: {response.json()}")
        else:
            print(f"⚠️  Expected 404, got {response.status_code}")

    except Exception as e:
        print(f"❌ Error testing non-existent server: {e}")

    # Test unregistering the server (cleanup)
    print("\n7. Testing server unregistration (cleanup)...")
    unregister_request = {"codebase_url": test_server["codebase_url"]}

    try:
        response = requests.delete(
            f"{base_url}/unregister_server", json=unregister_request
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        print("✅ Successfully cleaned up test server")
    except Exception as e:
        print(f"❌ Error unregistering server: {e}")

    # Verify server was removed
    print("\n8. Verifying server removal...")
    try:
        response = requests.get(f"{base_url}/servers")
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Total servers after cleanup: {result['total_count']}")

        # Check if test server still exists
        test_server_exists = any(
            server["codebase_url"] == test_server["codebase_url"]
            for server in result["servers"]
        )

        if test_server_exists:
            print("⚠️  Test server still exists after unregistration")
        else:
            print("✅ Test server successfully removed")

    except Exception as e:
        print(f"❌ Error verifying removal: {e}")


if __name__ == "__main__":
    test_api()
