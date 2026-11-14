# Three-agent workflow

This example runs three Gemini-backed roles in sequence:

1. **Researcher** retrieves relevant passages from the configured RAG documents
   and summarizes the evidence with source references.
2. **Writer** drafts content from those research notes.
3. **Reviewer** checks the draft against the notes and returns actionable
   feedback without rewriting it.

## Run

From the `RAG-Basic` project directory, set up the project as described in the
main [README](../README.md), including dependencies and `LLM_API_KEY` in `.env`.
Then run:

```powershell
python .\multi-agent\main.py "What does the laptop policy say?"
```

The workflow uses the same `RAG_DOCUMENT_DIR`, Gemini model settings, and API
key configuration as `rag_service.py`. It makes Gemini embedding and chat API
calls.
