from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except Exception as exc:  # pragma: no cover - handled at runtime
    QdrantClient = None
    QDRANT_IMPORT_ERROR = exc
else:
    QDRANT_IMPORT_ERROR = None

try:
    from fastembed import TextEmbedding
except Exception as exc:  # pragma: no cover - handled at runtime
    TextEmbedding = None
    FASTEMBED_IMPORT_ERROR = exc
else:
    FASTEMBED_IMPORT_ERROR = None


class HRPolicyAgent:
    """Retrieval-augmented worker that answers HR policy questions from Qdrant."""

    def __init__(
        self,
        qdrant_url: str | None = None,
        collection_name: str = "enterprise_policies",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        vector_size: int = 384,
    ) -> None:
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.vector_size = vector_size
        self.client: QdrantClient | None = None
        self.embedding_model_instance: Any | None = None
        self._initialize()

    def _initialize(self) -> None:
        if QdrantClient is None:
            raise RuntimeError(
                "Qdrant client is required but not installed. "
                f"Original import error: {QDRANT_IMPORT_ERROR}"
            )
        if TextEmbedding is None:
            raise RuntimeError(
                "FastEmbed is required but not installed. "
                f"Original import error: {FASTEMBED_IMPORT_ERROR}"
            )

        self.client = QdrantClient(url=self.qdrant_url)
        self.embedding_model_instance = TextEmbedding(model_name=self.embedding_model)
        self._ensure_collection()
        self._seed_policies_if_needed()

    def _ensure_collection(self) -> None:
        if self.client is None:
            raise RuntimeError("Qdrant client was not initialized.")

        collections = self.client.get_collections().collections
        names = {collection.name for collection in collections}
        if self.collection_name not in names:
            logger.info(
                "Creating Qdrant collection '%s' on %s",
                self.collection_name,
                self.qdrant_url,
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )

    def _seed_policies_if_needed(self) -> None:
        if self.client is None:
            raise RuntimeError("Qdrant client was not initialized.")

        stats = self.client.get_collection(collection_name=self.collection_name)
        points_count = getattr(stats, "points_count", 0)
        if points_count > 0:
            logger.info("Collection '%s' already has %s points.", self.collection_name, points_count)
            return

        policies = [
            {
                "title": "Employee tenure eligibility",
                "content": (
                    "Employees must complete at least 12 months of continuous service before they become "
                    "eligible for a standard device upgrade. New hires in their first year are eligible only "
                    "when a manager approves an exception and the department budget is confirmed."
                ),
                "tags": ["tenure", "device", "eligibility"],
            },
            {
                "title": "Relocation policy",
                "content": (
                    "Employees assigned to a relocation or international move may be eligible for a new device "
                    "if they are actively working in the target country and the relocation has been approved by "
                    "HR and the employee's manager. A relocation in progress still requires documentation and a "
                    "budget review."
                ),
                "tags": ["relocation", "device", "hr"],
            },
            {
                "title": "Device replacement cycle",
                "content": (
                    "Standard company laptops and workstations are replaced on a 24-month lifecycle. Exceptions "
                    "can be approved for damaged equipment or role changes, but an employee must meet the tenure "
                    "and approval requirements before a replacement is ordered."
                ),
                "tags": ["device", "upgrade", "assets"],
            },
        ]

        texts = [policy["content"] for policy in policies]
        embeddings = list(self.embedding_model_instance.embed(texts))
        points = [
            {
                "id": index + 1,
                "vector": embedding,
                "payload": {"title": policy["title"], "content": policy["content"], "tags": policy["tags"]},
            }
            for index, (policy, embedding) in enumerate(zip(policies, embeddings))
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info("Seeded %s policy documents into Qdrant.", len(points))

    def search_policy(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Search Qdrant for top matching HR policies using the configured embedding model."""
        if not query or not query.strip():
            raise ValueError("A policy search query is required.")
        if self.client is None or self.embedding_model_instance is None:
            raise RuntimeError("The HR policy agent is not initialized.")

        query_embedding = list(self.embedding_model_instance.embed([query.strip()]))[0]
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        ).points

        results: list[dict[str, Any]] = []
        for hit in response:
            payload = hit.payload or {}
            score = getattr(hit, "score", None)
            results.append(
                {
                    "score": float(score) if score is not None else 0.0,
                    "title": payload.get("title", "Untitled policy"),
                    "content": payload.get("content", "No content available."),
                    "tags": payload.get("tags", []),
                }
            )
        return results

    def build_policy_context(self, query: str, limit: int = 3) -> str:
        """Convert retrieved policy hits into a readable context string."""
        try:
            hits = self.search_policy(query, limit=limit)
        except Exception as exc:
            logger.exception("Policy search failed for query=%s", query)
            return f"Policy retrieval failed: {exc}"

        if not hits:
            return "No HR policy matches were found for the supplied query."

        sections: list[str] = []
        for index, hit in enumerate(hits, start=1):
            sections.append(
                f"Policy {index} [{hit['title']}] (score={hit['score']:.4f})\n"
                f"- Tags: {', '.join(hit['tags']) if hit['tags'] else 'N/A'}\n"
                f"- Relevant policy: {hit['content']}"
            )
        return "\n\n".join(sections)

    def run(self, user_query: str, limit: int = 3) -> dict[str, Any]:
        """Run the HR policy decision support flow."""
        logger.info("HRPolicyAgent processing query: %s", user_query)
        try:
            context = self.build_policy_context(user_query, limit=limit)
            return {
                "status": "success",
                "query": user_query,
                "context": context,
                "retrieved_policies": self.search_policy(user_query, limit=limit),
            }
        except Exception as exc:
            logger.exception("HR policy workflow failed for query=%s", user_query)
            return {
                "status": "error",
                "query": user_query,
                "error": str(exc),
                "context": "Unable to retrieve policy guidance due to a retrieval error.",
                "retrieved_policies": [],
            }


__all__ = ["HRPolicyAgent"]
