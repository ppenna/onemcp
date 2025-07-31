import chromadb
import os
import json
import tqdm
# import llm_client

# import chromadb.utils.embedding_functions as embedding_functions
# openai_ef = embedding_functions.OpenAIEmbeddingFunction(
#        model_name="text-embedding-3-small"
#    )

# Example setup of the client to connect to your chroma server
# chroma run --host localhost --port 8000
client = chromadb.HttpClient(host="localhost", port=8000)

# collection = client.create_collection("all-my-documents")
client.delete_collection("all-my-documents")
collection = client.get_or_create_collection(
    "all-my-documents",
    # embedding_function=openai_ef,
    metadata={"description": "Collection of all tools from various servers"},
)


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

for file in os.listdir("servers"):
    if file.endswith(".json"):
        with open(
            os.path.join(os.path.join(os.path.dirname(__file__), "servers"), file), "r"
        ) as f:
            data = json.load(f)
            # Process the data as needed
            # add a collection for each tool inside the json file
            server_summary = data[
                "description"
            ]  # llm_client.summarize_description(data["description"])
            print(f"Adding server: {server_summary}")
            for tool in data.get("tools", []):
                document_info = f"""
                    Description of the tool: 
                    {tool["description"]}
                    
                    Context: 
                    {server_summary}
                """
                collection.add(
                    documents=[document_info],
                    metadatas=[
                        {
                            "source": data["codebase-url"],
                            "path-to-json": file,
                            "tool-name": tool["name"],
                            "tool-description": tool["description"],
                        }
                    ],
                    ids=[f"{tool['name']}@{data['codebase-url']}"],
                )

print("Searching for documents in the collection...")
user_query = "Authenticate to Google task API"

q_prompt = f"""
    Tool: {user_query}    
    """
results = collection.query(
    query_texts=[q_prompt],
    n_results=5,
    # where={"metadata_field": "is_equal_to_this"}, # optional filter
    # where_document={"$contains":"search_string"}  # optional filter
)
for idx_, mdata in enumerate(results["metadatas"][0]):
    print("\n=======")
    print("Distance:", results["distances"][0][idx_])
    print(mdata["tool-name"])
    print(mdata["tool-description"])
