"""Create Qdrant clients using settings from the RAG folder's .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Load environment variables once when this module is imported. This allows the
# scripts to use the same Qdrant settings without each script parsing .env itself.
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def get_qdrant_client() -> QdrantClient:
    """Create a client using a full URL or a host/port pair."""
    qdrant_url = os.getenv("QDRANT_URL")
    if qdrant_url:
        # A URL is convenient when Qdrant is bound to a specific local address.
        return QdrantClient(url=qdrant_url, prefer_grpc=False)

    # Otherwise, use the separate host and port settings (with local defaults).
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)
