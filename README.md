# RAG Basic

`rag_service.py` loads PDF documents, retrieves relevant passages using
Gemini embeddings, and asks Gemini to answer questions using that context.
It runs from the command line; it does not start an HTTP server.

## Requirements

- Python 3.10 or later
- An LLM API key to use `rag_service.py` (the current provider is Gemini)

## Set up the Gemini service

Run these commands from the `RAG-Basic` project directory.

1. Create and activate a virtual environment:

   **Windows PowerShell**

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS/Linux**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Create your local environment file and add your LLM API key:

   **Windows PowerShell**

   ```powershell
   Copy-Item .env.example .env
   ```

   **macOS/Linux**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set `LLM_API_KEY`. The `.env` file is ignored by Git;
   never commit or share your key. For compatibility with existing
   configurations, the service also accepts `GEMINI_API_KEY` and
   `GOOGLE_API_KEY` if `LLM_API_KEY` is not set.

4. Check that the configured PDF source can be read and split into chunks
   without making Gemini API calls:

   ```bash
   python rag_service.py --check-source
   ```

5. Ask a question:

   ```bash
   python rag_service.py --query "What does the laptop policy say?"
   ```

   Or run `python rag_service.py` to enter a question interactively. Answering
   requires network access and makes Gemini embedding and chat API calls.

## Configure the knowledge source

The default value of `RAG_DOCUMENT_DIR` in `.env.example` points to
`rag_service/files`. The service searches that folder and its subfolders for
PDF files. Add PDFs there or change `RAG_DOCUMENT_DIR` to another local folder.
Documents in `rag_service/files/` are excluded from Git by default because
knowledge sources may contain private or licensed material. Only change the
ignore rule if you have confirmed the documents are appropriate to share with
everyone who can access the repository.

Alternatively, set `RAG_DOCUMENT_DIR=` (empty) and set `RAG_DOCUMENT_URL` to
an HTTPS URL that serves a non-empty UTF-8 text document. The service rejects
non-HTTPS URLs and limits downloaded documents to 5 MiB.

`GEMINI_CHAT_MODEL` and `GEMINI_EMBEDDING_MODEL` can optionally override the
model names in `.env.example`.
