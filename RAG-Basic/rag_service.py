"""Answer questions about configured documents using Google's Gemini API."""

import argparse
import asyncio
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader


WORKSPACE_DIR = Path(__file__).resolve().parent
DEFAULT_DOCUMENT_DIR = WORKSPACE_DIR / "rag_service" / "files"
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_CHAT_MODEL = "gemini-3.5-flash"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2-preview"

# Read settings from the workspace .env file. Existing process environment
# variables take precedence, so credentials need not be written to this file.
load_dotenv(WORKSPACE_DIR / ".env")


class _HTTPSRedirectHandler(HTTPRedirectHandler):
    """Keep redirects on HTTPS so a document URL cannot downgrade to HTTP."""

    def redirect_request(self, request, response, code, message, headers, new_url):
        """Allow redirects only when the destination also uses HTTPS.

        This protects document downloads from silently switching to an
        unencrypted connection. Raises ValueError for any non-HTTPS redirect;
        otherwise, delegates redirect handling to urllib's standard handler.
        """
        if urlparse(new_url).scheme.lower() != "https":
            raise ValueError("Document URL redirects must remain on HTTPS.")
        return super().redirect_request(
            request, response, code, message, headers, new_url
        )


def _get_api_key() -> str:
    """Return the LLM API key configured in the process environment.

    The workspace .env file is loaded when this module starts. LLM_API_KEY is
    preferred; provider-specific names are accepted for backward compatibility.
    Raises RuntimeError if no key is set. The key is never stored in this source.
    """
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "LLM API key is missing. Set LLM_API_KEY in the workspace "
            ".env file or configure it in the process environment."
        )
    return api_key


def _get_document_url() -> str:
    """Read and validate the HTTPS URL used as the RAG knowledge source.

    The URL comes from RAG_DOCUMENT_URL in the environment or workspace .env.
    Only URLs with an HTTPS scheme and a host are accepted, and embedded
    username/password credentials are rejected. Returns the validated URL or
    raises RuntimeError when the setting is absent or invalid.
    """
    document_url = os.getenv("RAG_DOCUMENT_URL", "").strip()
    parsed_url = urlparse(document_url)
    if parsed_url.scheme.lower() != "https" or not parsed_url.netloc:
        raise RuntimeError(
            "RAG_DOCUMENT_URL must be an HTTPS URL to a plain-text document. "
            "Set it in the workspace .env file."
        )
    if parsed_url.username or parsed_url.password:
        raise RuntimeError("Do not include credentials in RAG_DOCUMENT_URL.")
    return document_url


def _load_documents() -> list[Document]:
    """Load every PDF in the configured local folder, or the configured text URL.

    RAG_DOCUMENT_DIR defaults to rag_service/files and is searched recursively
    for PDFs. Set it to an empty value to use RAG_DOCUMENT_URL instead. Each
    PDF page is returned as its own LangChain document with source/page
    metadata, while URL mode returns one document containing the UTF-8 text.
    """
    configured_directory = os.getenv(
        "RAG_DOCUMENT_DIR", str(DEFAULT_DOCUMENT_DIR)
    ).strip()
    if configured_directory:
        document_dir = Path(configured_directory)
        if not document_dir.is_absolute():
            document_dir = WORKSPACE_DIR / document_dir
        if not document_dir.is_dir():
            raise FileNotFoundError(
                f"PDF folder not found: {document_dir}. "
                "Set RAG_DOCUMENT_DIR to a folder containing PDF files."
            )

        pdf_paths = sorted(document_dir.rglob("*.pdf"))
        if not pdf_paths:
            raise FileNotFoundError(
                f"No PDF files were found in {document_dir}."
            )

        documents = []
        for pdf_path in pdf_paths:
            pdf = PdfReader(str(pdf_path))
            for page_number, page in enumerate(pdf.pages, start=1):
                documents.append(
                    Document(
                        page_content=page.extract_text() or "",
                        metadata={
                            "source": str(pdf_path),
                            "page": page_number,
                        },
                    )
                )
        if not documents:
            raise ValueError(f"No readable pages were found in {document_dir}.")
        return documents

    return [_load_document()]


def _load_document() -> Document:
    """Download the configured text source and wrap it as a LangChain document.

    The request uses a timeout, accepts only HTTPS redirects, and reads at most
    one byte beyond the configured size limit so oversized responses are
    detected without unbounded memory use. The response must be non-empty
    UTF-8 text. Returns a Document tagged with its source URL; network, size,
    and decoding failures are reported explicitly.
    """
    request = Request(
        _get_document_url(),
        headers={"User-Agent": "rag-service/1.0", "Accept": "text/plain"},
    )
    opener = build_opener(_HTTPSRedirectHandler)

    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            # Read one byte beyond the limit to detect oversized documents
            # without loading an unbounded response into memory.
            content = response.read(MAX_DOCUMENT_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise RuntimeError(
            f"Could not fetch the configured document: {error}"
        ) from error

    if len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError(
            f"The document exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MiB limit."
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("The document URL must return UTF-8 text.") from error

    if not text.strip():
        raise ValueError("The document URL returned an empty text document.")
    return Document(page_content=text, metadata={"source": _get_document_url()})


def setup_rag_system() -> BaseRetriever:
    """Build a retriever for finding evidence in the configured source.

    Loads the API key and source documents (PDF pages from RAG_DOCUMENT_DIR by
    default, or a text document from RAG_DOCUMENT_URL), splits them into
    overlapping 500-character chunks, and embeds those chunks with Gemini. It
    then builds an in-memory vector index and returns a similarity retriever
    configured to return up to five relevant chunks. The index is rebuilt
    whenever this function is called.
    """
    # Gemini embeddings turn document chunks into vectors for semantic search.
    api_key = _get_api_key()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    document_chunks = splitter.split_documents(_load_documents())
    if not document_chunks:
        raise ValueError("No searchable text chunks were created from the document.")

    # Keep both the vectors and their index in memory for this process.
    embeddings = GoogleGenerativeAIEmbeddings(
        model=os.getenv("GEMINI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        google_api_key=api_key,
    )
    vector_store = InMemoryVectorStore.from_documents(document_chunks, embeddings)
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5},
    )


def check_source() -> None:
    """Validate local PDF extraction and chunking without calling Gemini.

    Prints how many pages and text chunks were read, along with per-file page
    counts. This check confirms PDFs are readable without calling Gemini.
    """
    documents = _load_documents()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documents)

    pages_by_source: dict[str, int] = {}
    for document in documents:
        source = str(document.metadata.get("source", "Unknown source"))
        pages_by_source[source] = pages_by_source.get(source, 0) + 1

    print(f"Loaded {len(documents)} page(s) and created {len(chunks)} text chunk(s).")
    for source, page_count in pages_by_source.items():
        print(f"- {source}: {page_count} page(s)")


async def get_rag_response(query: str) -> str:
    """Generate an answer grounded in the configured document.

    Validates and trims the user's question, creates the retriever, and
    asynchronously retrieves relevant passages. It combines those passages
    with an instruction to answer only from the provided context, then sends
    that prompt to the configured Gemini chat model. Returns the generated answer;
    raises ValueError for a blank question and propagates setup or API errors.
    """
    query = query.strip()
    if not query:
        raise ValueError("The question must not be empty.")

    # Retrieve the five closest chunks, then provide only their text as evidence.
    retriever = setup_rag_system()
    retrieved_docs = await retriever.ainvoke(query)
    context = "\n".join(document.page_content for document in retrieved_docs)
    prompt = (
        "Use only the following information to answer the question. "
        "If the answer is not present, say you do not know.\n\n"
        f"Context:\n{context or '(No matching context found.)'}\n\n"
        f"Question: {query}\nAnswer:"
    )

    # The model is instructed to stay within the retrieved document context.
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_CHAT_MODEL", DEFAULT_CHAT_MODEL),
        api_key=_get_api_key(),
    )
    response = await llm.ainvoke(prompt)
    return response.text


def main() -> None:
    """Run the command-line interface for asking a question of the RAG source.

    Accepts a question through --query or prompts interactively when that
    option is omitted. The --check-source option checks document loading and
    chunking without making Gemini calls. Otherwise, invokes the asynchronous
    response function and prints the resulting answer.
    """
    parser = argparse.ArgumentParser(description="Ask a question of the RAG document.")
    parser.add_argument(
        "--query",
        help="Question to answer. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--check-source",
        action="store_true",
        help="Check PDF loading and chunking without calling Gemini.",
    )
    args = parser.parse_args()
    if args.check_source:
        check_source()
        return
    query = args.query if args.query is not None else input("Question: ")
    print(asyncio.run(get_rag_response(query)))


if __name__ == "__main__":
    main()
