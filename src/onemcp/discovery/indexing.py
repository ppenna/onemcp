import json
import os
from typing import Any, Optional

import chromadb


class Indexing:
    """
    Class to handle indexing of MCP server tools into a ChromaDB collection.
    """

    def __init__(self) -> None:
        """
        Initialize the ChromaDB client and collection.
        """
        self.client: Optional[Any] = None
        self.collection: Optional[Any] = None

    def init_db_server(self, reset_collection: bool = False, db_name: str = "chroma_mcpservers_db") -> None:
        """
        Initialize the ChromaDB client and collection.

        Args:
            reset_collection: Whether to reset the collection (delete and recreate)
        """
        # chroma run --host localhost --port 8000
        #self.client = chromadb.HttpClient(host="localhost", port=8000)
        self.client = chromadb.PersistentClient(path=os.path.join(os.path.dirname(__file__),"servers", db_name))

        if reset_collection:
            try:
                if self.client:
                    self.client.delete_collection("all-my-documents")
            except Exception:
                pass  # Collection might not exist

        if self.client:
            self.collection = self.client.get_or_create_collection(
                "all-my-documents",
                # embedding_function=openai_ef,  # Uncomment if using OpenAI embeddings
                metadata={"description": "Collection of all tools from various servers"},
            )

    def add_tools_from_json(self, json_file: str) -> None:
        """
        Add tools from a JSON file to the ChromaDB collection.

        Args:
            json_file: Path to the JSON file containing server and tool information.
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call init_db_server() first.")

        with open(json_file) as f:
            data = json.load(f)
            server_summary = data["description"]  # Use LLM to summarize if needed
            print(f"Adding server: {server_summary}")
            for tool in data.get("tools", []):
                document_info = f"""
                    Tool Name: {tool["name"]}
                    Tool Description: {tool["description"]}
                    Context: {server_summary}
                """
                self.collection.add(
                    documents=[document_info],
                    metadatas=[
                        {
                            "source": data["codebase-url"],
                            "path-to-json": os.path.basename(json_file),
                            "tool-name": tool["name"],
                            "tool-description": tool["description"],
                        }
                    ],
                    ids=[f"{tool['name']}@{data['codebase-url']}"],
                )

    def find_similar_tools(self, user_query: str, k: int = 5) -> list[dict[str, str | float]]:
        """
        Find top K tools with names most similar to the query string.

        Args:
            user_query: Search string to compare against server names
            k: Maximum number of results to return (default 5)

        Returns:
            List of dictionaries containing tool information and similarity scores
            sorted by similarity score in descending order
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call init_db_server() first.")

        q_prompt = f"Description: {user_query}"
        results = self.collection.query(
            query_texts=[q_prompt],
            n_results=k,
        )
        query_result = []
        all_metadatas = results["metadatas"]
        all_distances = results.get("distances", [[]])

        if all_metadatas and all_metadatas[0]:
            for idx_, mdata in enumerate(all_metadatas[0]):
                distance = (
                    all_distances[0][idx_] if all_distances and len(all_distances) > 0 and idx_ < len(all_distances[0]) else 0.0
                )
                print("tool-name:", mdata["tool-name"], f"[score = {distance}]")
                query_result.append(
                    {
                        "tool-name": mdata["tool-name"],
                        "tool-description": mdata["tool-description"],
                        "server-url": mdata["source"],
                        "path-to-json": mdata["path-to-json"],
                        "distance": distance,
                    }
                )

        return query_result

    def get_server_json(self, codebase_url: str) -> dict[str, Any]:
        """
        Retrieve the JSON data for a specific server by its codebase URL.

        Args:
            codebase_url: The codebase URL of the server to retrieve

        Returns:
            Dictionary containing the server's JSON data
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call init_db_server() first.")

        try:
            all_results = self.collection.get(where={"source": codebase_url})
            print("All results:", all_results.keys())
            # get path-to-json key from the first document
            if not all_results or not all_results.get("metadatas"):
                return {}

            # Assuming the first document contains the full server JSON
            metadata = all_results["metadatas"][0] if all_results["metadatas"] else {}
            path_to_json = str(metadata.get("path-to-json", ""))
            print("loading server JSON from:", path_to_json)
            json_file = os.path.join(os.path.dirname(__file__),"servers", path_to_json)
            with open(json_file) as f:
                data: dict[str, Any] = json.load(f)

            return data

        except Exception as e:
            print(f"Error retrieving server JSON: {e}")
            return {}

    def remove_server_tools(self, codebase_url: str) -> int:
        """
        Remove all tools from a specific server from the ChromaDB collection.

        Args:
            codebase_url: The codebase URL of the server to remove

        Returns:
            Number of tools removed
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call init_db_server() first.")

        try:
            # Query for all tools from this server
            all_results = self.collection.get(where={"source": codebase_url})

            if not all_results or not all_results.get("ids"):
                return 0

            # Delete all tools from this server
            tool_ids = all_results["ids"]
            self.collection.delete(ids=tool_ids)

            print(f"Removed {len(tool_ids)} tools from server: {codebase_url}")
            return len(tool_ids)

        except Exception as e:
            print(f"Error removing server tools: {e}")
            raise


# iterates over all json files at 'servers' folder

"""
Json file example:
{
  "codebase-url": "https://github.com/guillochon/mlb-api-mcp",
  "description": "MLB API MCP Server - A comprehensive bridge between AI applications and MLB data sources, enabling seamless integration of baseball statistics, game information, player data, and more. Provides access to current standings, schedules, player stats (traditional and sabermetric like WAR, wOBA, wRC+), team information, live game data, highlights, and advanced Statcast analytics. Built with FastMCP and Python 3.10+.",
  "tools": [
    {
      "name": "get_mlb_standings",
      "description": "Get current MLB standings for a given season with flexible filtering by league (AL, NL, or both), season, and date."
    },
    {
      "name": "get_mlb_schedule",
      "description": "Get MLB game schedules for specific date ranges, sport ID, or teams with comprehensive filtering options."
    },
    {
      "name": "get_mlb_team_info",
      "description": "Get detailed information about a specific MLB team by ID or name, including metadata and roster information."
    }
    ]
}
"""

if __name__ == "__main__":
    indexing = Indexing()
    indexing.init_db_server()
    files_dir = os.path.join(os.path.dirname(__file__), "servers")
    #for file in os.listdir(files_dir):
    #    if file.endswith(".json"):
    #        indexing.add_tools_from_json(os.path.join(files_dir, file))

    results = indexing.find_similar_tools("Authenticate to Google task API", k=5)
    for res in results:
        print(
            f"Tool Name: {res['tool-name']}, Description: {res['tool-description']}, URL: {res['server-url']}"
        )
    print("\n\n\n")
    print(indexing.get_server_json("https://github.com/guillochon/mlb-api-mcp"))
