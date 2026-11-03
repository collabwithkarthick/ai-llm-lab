"""Extract policy text from PDFs, embed each page, and store it in Qdrant."""

import os
import glob
from pypdf import PdfReader
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import VectorParams, Distance, PointStruct
from fastembed import TextEmbedding
from qdrant_config import get_qdrant_client
from document_access import groups_for_document

COLLECTION_NAME = "enterprise_policies"

def load_and_chunk_pdfs(data_dir: str):
    """Return one searchable text record for each non-empty PDF page.

    Keeping page-level records makes it possible to show users the PDF and page
    that supplied a retrieved result.
    """
    # Search subfolders too, so PDFs in data/documents/ are found automatically.
    pdf_files = glob.glob(os.path.join(data_dir, "**", "*.pdf"), recursive=True)
    chunks = []
    
    print(f"Found {len(pdf_files)} PDF file(s) in '{data_dir}'...")
    
    for file_path in pdf_files:
        file_name = os.path.basename(file_path)
        allowed_groups = groups_for_document(file_name)
        reader = PdfReader(file_path)
        
        # PDF pages are numbered for people starting at 1, not Python's 0.
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                # Store text chunk along with source metadata
                chunks.append({
                    "doc_id": f"{file_name}_p{page_num}",
                    "file_name": file_name,
                    "page": page_num,
                    "content": text.strip(),
                    "allowed_groups": list(allowed_groups),
                })
    return chunks

def ingest_pdfs():
    """Build embeddings for the PDF pages and replace the Qdrant collection."""
    client = get_qdrant_client()
    embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # 1. Extract chunks from PDFs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.abspath(os.path.join(script_dir, "..", "data"))
    chunks = load_and_chunk_pdfs(data_dir)
    if not chunks:
        print("No valid PDF content found in 'data/' folder!")
        return

    # 2. Convert each page's text into a numeric vector for semantic search.
    print("Generating vector embeddings...")
    texts = [c["content"] for c in chunks]
    embeddings = list(embed_model.passage_embed(texts))

    # 3. Rebuild the collection so its vector size and contents match this run.
    # This also means old indexed documents are replaced when PDFs change.
    vector_size = len(embeddings[0])
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    except Exception as exc:
        # Qdrant can return a 500 if the previous collection directory exists.
        # Recover the collection using recreate_collection when the storage path is stale.
        error_text = str(exc)
        if COLLECTION_NAME in error_text and ("create directory" in error_text or "File exists" in error_text):
            print(f"Warning: stale collection storage exists for '{COLLECTION_NAME}', retrying with recreate_collection...")
            client.recreate_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            raise

    # 4. Pair each vector with its source metadata and save all records to Qdrant.
    points = [
        PointStruct(
            id=idx,
            vector=embedding.tolist(),
            payload=chunk
        )
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"Successfully ingested {len(points)} page chunk(s) from PDFs into Qdrant!")

if __name__ == "__main__":
    ingest_pdfs()