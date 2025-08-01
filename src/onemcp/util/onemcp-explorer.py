# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import sys
from typing import Any

import requests


def post_discover_request(
    repository_url: str, repository_readme: str, endpoint: str
) -> dict[str, Any]:
    """
    Constructs and sends a POST request to the sandbox API to discover an MCP server.
    """
    headers = {"Content-Type": "application/json", "X-OneMCP-Message-Type": "DISCOVER"}
    payload = {"repository_url": repository_url, "repository_readme": repository_readme}
    response = requests.post(endpoint, headers=headers, json=payload)
    print(f"POST {endpoint} with repository_url={repository_url}")
    print(f"Status code: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return {}

    try:
        resp_json = response.json()
    except Exception as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Raw response: {response.text}")
        return {}

    tools = resp_json.get("tools")
    setup_script = resp_json.get("setup_script")

    if not tools or not setup_script:
        print("Invalid response format. Expected 'tools' and 'setup_script'.")
        return {}

    print("Discovery successful!")
    print(f"Tools: {json.dumps(tools, indent=2)}")
    print(f"Setup Script: {setup_script}")

    # Create a JSON object with the discovered information
    discovered_info = {
        "repository_url": repository_url,
        "repository_readme": repository_readme,
        "tools": tools,
        "setup_script": setup_script,
    }

    return discovered_info


def parse_mcp_servers(json_path: str, output_path: str) -> None:
    with open(json_path, encoding="utf-8") as f:
        servers = json.load(f)
    for server in servers:
        name = server.get("name")
        description = server.get("description")
        repo_url = server.get("repository_url")
        language = server.get("language")
        if language != "Python":
            continue

        repo_readme = server.get("readme_content", "")
        if repo_readme == "":
            continue

        print(
            f"Name: {name}\nDescription: {description}\nRepository URL: {repo_url}\nLanguage: {language}\n"
        )

        response = post_discover_request(
            repository_url=repo_url,
            repository_readme=repo_readme,
            endpoint="http://localhost:8080/sandbox",
        )

        # Check if response is not empty
        if response:
            response["language"] = language
            response["description"] = description
            response["name"] = name

            # Append JSON object to file (in a new line).
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(response, ensure_ascii=False, indent=2))
                f.write("\n")
            print(f"Response appended to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python index.py <input file> <output file>")
        sys.exit(1)

    parse_mcp_servers(sys.argv[1], sys.argv[2])
