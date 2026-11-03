"""Check the Qdrant collection and run one command-line similarity search."""

import sys
from fastembed import TextEmbedding
from qdrant_config import get_qdrant_client

COLLECTION_NAME = "enterprise_policies"

def inspect_qdrant():
    """Print collection health and the three closest policy pages to a query."""
    client = get_qdrant_client()
    
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not client.collection_exists(COLLECTION_NAME):
        print(f"Error: Collection '{COLLECTION_NAME}' does not exist in Qdrant!")
        print("Please run 'python src/ingest_pdf.py' first to ingest documents.")
        sys.exit(1)
        
    collection_info = client.get_collection(COLLECTION_NAME)
    print(f"=== Qdrant Collection: '{COLLECTION_NAME}' ===")
    print(f"Status: {collection_info.status}")
    print(f"Points count: {collection_info.points_count}")
    print(f"Vectors config: {collection_info.config.params.vectors}")
    print("=============================================\n")
    
    # Use command-line words as the query, or a useful default if none were given.
    query_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "broadband expense claim"
    print(f"Testing RAG retrieval for query: '{query_text}'")
    
    # Encode the question with the same model used to encode PDF pages at ingest.
    embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    query_vector = list(embed_model.query_embed(query_text))[0]

    try:
        # Qdrant compares this vector with stored vectors and returns nearest hits.
        search_response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=3,
            with_payload=True,
        )
    except Exception as exc:
        print("Error running Qdrant query:")
        print(str(exc))
        raise

    search_results = getattr(search_response, 'points', None)
    if not search_results:
        print("No search results returned.")
        return

    print("\n--- Top 3 Retrieval Results ---")
    # Display rank, similarity score, source page, and a short text preview.
    for rank, hit in enumerate(search_results, start=1):
        payload = hit.payload or {}
        snippet = payload.get("content", "")
        if not isinstance(snippet, str):
            snippet = str(snippet)
        snippet = snippet[:300]
        print(f"\n[Rank {rank}] Score: {hit.score:.4f}")
        print(f"Document: {payload.get('file_name')} (Page {payload.get('page')})")
        print(f"Snippet:\n{snippet}...")
        print("-" * 40)

if __name__ == "__main__":
    inspect_qdrant()

