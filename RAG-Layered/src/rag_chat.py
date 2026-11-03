"""Interactive terminal chat that retrieves policy pages and asks the LLM."""

import json
import os
import sys
import urllib.error
import urllib.request
from typing import List

from fastembed import TextEmbedding
from qdrant_client.models import FieldCondition, Filter, MatchAny
from qdrant_config import get_qdrant_client
from demo_auth import DemoUser, login_interactively

COLLECTION_NAME = "enterprise_policies"
DEFAULT_TOP_K = 3
DEFAULT_SNIPPET_LENGTH = 500
DEFAULT_LLM_GATEWAY_URL = "http://127.0.0.1:4000"
DEFAULT_LLM_MODEL = "helpdesk-llm"


def get_env(name: str, default: str | None = None) -> str | None:
    """Read a setting from the environment, falling back to a default value."""
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def build_context(hits: List[object]) -> str:
    """Turn retrieved Qdrant records into readable source-labeled prompt text."""
    pieces = []
    for idx, hit in enumerate(hits, start=1):
        payload = getattr(hit, "payload", {}) or {}
        source = f"{payload.get('file_name', 'unknown')} page {payload.get('page', '?')}"
        content = payload.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        snippet = " ".join(content.split())[:DEFAULT_SNIPPET_LENGTH]
        pieces.append(f"SOURCE {idx}: {source}\n{snippet}")
    return "\n\n".join(pieces)


def query_qdrant(
    query: str, user: DemoUser, top_k: int = DEFAULT_TOP_K
) -> List[object]:
    """Return matching policy pages the authenticated user is allowed to see."""
    client = get_qdrant_client()
    embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    # Query embeddings represent the user's question in the same vector space
    # as the policy-page embeddings created by ingest_pdf.py.
    query_vector = list(embed_model.query_embed(query))[0]

    search_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="allowed_groups",
                    match=MatchAny(any=list(user.groups)),
                )
            ]
        ),
    )

    points = getattr(search_response, "points", None)
    return points or []


def build_prompt(query: str, hits: List[object]) -> str:
    """Give the model the retrieved evidence and ask it to answer from that only."""
    context = build_context(hits)
    return (
        "You are an enterprise helpdesk assistant. Use the policy text below to answer the user query. "
        "Cite source names when possible and answer only from the provided context. If the answer is not available, say so.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {query}\n\nANSWER:"
    )


def call_llm_gateway(prompt: str) -> str:
    """Send the prompt to LiteLLM's OpenAI-compatible chat-completions endpoint."""
    gateway_url = get_env("LLM_GATEWAY_URL", DEFAULT_LLM_GATEWAY_URL)
    model = get_env("LLM_MODEL", DEFAULT_LLM_MODEL)
    api_key = get_env("LLM_API_KEY")

    chat_url = gateway_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an enterprise helpdesk assistant."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 512,
        "temperature": 0.0,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        chat_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    # Convert network and HTTP failures into clear errors for the terminal user.
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_data = response.read().decode("utf-8")
            result = json.loads(response_data)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"LLM gateway request failed: {exc.code} {exc.reason} - {exc.read().decode('utf-8', errors='replace')}"
        )
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM gateway request failed: {exc.reason}")

    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected LLM response: {result}")

    choices = result.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices returned by LLM gateway: {result}")

    first_choice = choices[0]
    if isinstance(first_choice, dict):
        message = first_choice.get("message")
        if isinstance(message, dict):
            return message.get("content", "").strip()
        return first_choice.get("text", "").strip()

    return str(first_choice)


def print_retrieval(hits: List[object]) -> None:
    """Show which PDF pages informed the answer before printing the answer."""
    if not hits:
        print("No documents found for that query.")
        return

    print("\nRetrieved documents:\n")
    for idx, hit in enumerate(hits, start=1):
        payload = getattr(hit, "payload", {}) or {}
        title = payload.get("file_name", "unknown")
        page = payload.get("page", "?")
        content = payload.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        snippet = " ".join(content.split())[:DEFAULT_SNIPPET_LENGTH]
        print(f"[{idx}] {title} (page {page})")
        print(snippet)
        print("-" * 40)


def chat_loop(user: DemoUser) -> None:
    """Accept terminal questions for one authenticated user."""
    print("Enterprise Helpdesk RAG Chat")
    print(f"Signed in as {user.username} (groups: {', '.join(user.groups)})")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        query = input("\nYou: ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            print("Goodbye.")
            break

        # RAG order: retrieve matching context first, then generate an answer.
        hits = query_qdrant(query, user)
        print_retrieval(hits)
        if not hits:
            print("No matching documents are available to your account.")
            continue

        prompt = build_prompt(query, hits)
        try:
            answer = call_llm_gateway(prompt)
        except Exception as exc:
            print(f"\nLLM gateway error: {exc}")
            continue

        print("\nAssistant:\n")
        print(answer)


if __name__ == "__main__":
    try:
        print("Enterprise Helpdesk RAG Chat - demo sign-in")
        user = login_interactively()
        if user is None:
            print("Authentication failed. Exiting.")
            sys.exit(1)
        chat_loop(user)
    except KeyboardInterrupt:
        print("\nChat stopped.")
        sys.exit(0)
