"""Run a document-grounded Researcher, Writer, and Reviewer workflow."""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import rag_service
from langchain_core.retrievers import BaseRetriever
from langchain_google_genai import ChatGoogleGenerativeAI


@dataclass(frozen=True)
class WorkflowResult:
    """Content and source references produced by the three-agent workflow."""

    research_notes: str
    draft: str
    review: str
    sources: tuple[str, ...]


class Researcher:
    """Collect relevant document passages and turn them into grounded notes."""

    def __init__(
        self, llm: ChatGoogleGenerativeAI, retriever: BaseRetriever
    ) -> None:
        self.llm = llm
        self.retriever = retriever

    async def research(self, topic: str) -> tuple[str, tuple[str, ...]]:
        documents = await self.retriever.ainvoke(topic)
        if not documents:
            return (
                "No relevant passages were found in the configured documents.",
                (),
            )

        evidence = []
        sources = []
        for document in documents:
            source = str(document.metadata.get("source", "Unknown source"))
            page = document.metadata.get("page")
            source_reference = f"{source}, page {page}" if page else source
            sources.append(source_reference)
            evidence.append(
                f"[Source: {source_reference}]\n{document.page_content}"
            )

        prompt = (
            "You are the Researcher agent. Gather the facts relevant to the "
            "topic using only the supplied evidence. Do not invent details. "
            "Keep source references with the facts they support, and identify "
            "when the evidence does not answer part of the topic.\n\n"
            f"Topic: {topic}\n\nEvidence:\n"
            + "\n\n".join(evidence)
        )
        response = await self.llm.ainvoke(prompt)
        return response.text, tuple(dict.fromkeys(sources))


class Writer:
    """Draft clear content using only the Researcher's notes."""

    def __init__(self, llm: ChatGoogleGenerativeAI) -> None:
        self.llm = llm

    async def write(self, topic: str, research_notes: str) -> str:
        prompt = (
            "You are the Writer agent. Draft clear, well-organized content "
            "about the requested topic using only the research notes. Preserve "
            "their source references and do not add unsupported facts. If the "
            "notes say the evidence is insufficient, make that limitation clear.\n\n"
            f"Topic: {topic}\n\nResearch notes:\n{research_notes}"
        )
        response = await self.llm.ainvoke(prompt)
        return response.text


class Reviewer:
    """Give actionable feedback on accuracy, evidence, and clarity."""

    def __init__(self, llm: ChatGoogleGenerativeAI) -> None:
        self.llm = llm

    async def review(
        self, topic: str, research_notes: str, draft: str
    ) -> str:
        prompt = (
            "You are the Reviewer agent. Review the draft against the research "
            "notes. Check factual support, source references, completeness, and "
            "clarity. Return concise, actionable feedback, noting any unsupported "
            "claims or missing caveats. Do not rewrite the draft.\n\n"
            f"Topic: {topic}\n\nResearch notes:\n{research_notes}\n\n"
            f"Draft:\n{draft}"
        )
        response = await self.llm.ainvoke(prompt)
        return response.text


class ThreeAgentSystem:
    """Run the Researcher, Writer, and Reviewer sequentially."""

    def __init__(
        self, llm: ChatGoogleGenerativeAI, retriever: BaseRetriever
    ) -> None:
        self.researcher = Researcher(llm, retriever)
        self.writer = Writer(llm)
        self.reviewer = Reviewer(llm)

    async def run(self, topic: str) -> WorkflowResult:
        topic = topic.strip()
        if not topic:
            raise ValueError("The topic must not be empty.")

        research_notes, sources = await self.researcher.research(topic)
        draft = await self.writer.write(topic, research_notes)
        review = await self.reviewer.review(topic, research_notes, draft)
        return WorkflowResult(research_notes, draft, review, sources)


def create_system() -> ThreeAgentSystem:
    """Create the Gemini model and the retriever for the configured documents."""
    llm = ChatGoogleGenerativeAI(
        model=os.getenv(
            "GEMINI_CHAT_MODEL", rag_service.DEFAULT_CHAT_MODEL
        ),
        api_key=rag_service._get_api_key(),
    )
    return ThreeAgentSystem(llm, rag_service.setup_rag_system())


async def run_workflow(topic: str) -> WorkflowResult:
    """Create the agents and run the complete workflow."""
    return await create_system().run(topic)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research, draft, and review content from configured documents."
    )
    parser.add_argument("topic", help="Topic to research and write about.")
    args = parser.parse_args()

    result = asyncio.run(run_workflow(args.topic))
    print("=== Researcher: notes ===")
    print(result.research_notes)
    print("\n=== Writer: draft ===")
    print(result.draft)
    print("\n=== Reviewer: feedback ===")
    print(result.review)
    if result.sources:
        print("\n=== Sources ===")
        for source in result.sources:
            print(f"- {source}")


if __name__ == "__main__":
    main()
