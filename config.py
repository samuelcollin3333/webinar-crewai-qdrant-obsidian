import os
from dotenv import load_dotenv

# Load dotenv file
load_dotenv(".env")

# Embedder configuration
embedder_config = {
    "provider": "google",
    "config": {
        "api_key": os.environ.get("GEMINI_API_KEY"),
        "model": "models/text-embedding-004",
    },
}

# Qdrant configuration
qdrant_location = os.environ.get("QDRANT_LOCATION", "http://localhost:6333")
qdrant_api_key = os.environ.get("QDRANT_API_KEY") or None
qdrant_collection_name = "knowledge-base"

# Obsidian configuration
obsidian_vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")

#Notion configuration
notion_api_key = os.environ.get("NOTION_API_KEY")

# Add Notion database ID (formatted with hyphens)
notion_database_id = "18546dc7-ebc3-808d-ba04-c485aa46572b"

# AgentOps configuration
agentops_api_key = os.environ.get("AGENTOPS_API_KEY") or None
