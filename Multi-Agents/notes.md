# Runtime Notes: LangGraph, FastEmbed, and Hugging Face

## What this error means

The reported error ends with:

```text
RuntimeError: LangGraph is required but not installed.
Original import error: DLL load failed while importing _uuid_utils:
An Application Control policy has blocked this file.
```

In this case, the message does **not** establish that LangGraph is absent.
Python reached the `langgraph.graph` import, but a native extension named
`_uuid_utils` could not load because Windows Application Control blocked its
file. Application Control is a Windows security policy; an administrator or
organization may need to approve the blocked component.

At the time of the traceback, the supervisor caught any exception importing
LangGraph, set `StateGraph` to `None`, and later raised a new `RuntimeError`
with the generic “not installed” wording. The appended “Original import
error” contained the more useful cause: the blocked DLL. The current version
no longer imports LangGraph; see the fix below.

## Fix applied in this project

The supervisor's workflow was a fixed sequence of three functions, so the
project no longer depends on LangGraph to run it. `SupervisorAgent.process()`
now calls `parse_intent`, `dispatch_workers`, and `aggregate_response`
directly, in that order. LangGraph was removed from `requirements.txt`; the
`uuid-utils` import that triggered the Application Control block is therefore
no longer needed for the demo. This does not disable or bypass Windows
Application Control.

If LangGraph is installed in an existing virtual environment, it may remain
there, but this project no longer imports or requires it. Reinstall the
requirements only if you want to synchronize the environment:

```powershell
python -m pip install -r requirements.txt
```

## Why LangGraph is used

The previous implementation used LangGraph's `StateGraph` to define and
execute the orchestration workflow:

1. `parse_intent` classifies the request.
2. `dispatch_workers` calls the HR and IT workflows.
3. `aggregate_response` combines their results.

That graph was more machinery than the current fixed, sequential flow needs.
The current implementation runs those steps directly and does not require
LangGraph.

## Why FastEmbed and a Hugging Face model are used

The HR agent needs to turn policy text and the employee's question into
numerical embeddings so it can find semantically relevant policy passages.
[`src/agents/hr_agent.py`](./src/agents/hr_agent.py) creates a FastEmbed
`TextEmbedding` instance for `BAAI/bge-small-en-v1.5`, configured to produce
384-dimensional vectors. It stores policy vectors in Qdrant and embeds each
query before searching that collection.

FastEmbed performs the embedding inference. The Hugging Face model is the
pre-trained model FastEmbed uses; the project does not directly call the
Hugging Face Transformers API or require a Hugging Face account or API key.
FastEmbed may need internet access to download the model the first time. Once
the model is available in its local cache, it generally does not need to be
downloaded again.

Qdrant stores and searches vectors; it does not create embeddings. This demo
does not use a generative LLM to write its response: the HR side retrieves
policy text, and the supervisor formats that context together with the IT
workflow result.

## Diagnosing the old Windows block

The following commands reproduce or inspect the original LangGraph import
problem. They are no longer required to run the updated demo:

```powershell
python --version
python -m pip show langgraph uuid-utils
python -c "import langgraph.graph"
```

The final command tests the import directly and may display the underlying
DLL-block message without the supervisor's fallback wording.

An Application Control block remains a device policy issue. Do not disable or
attempt to bypass that policy. Qdrant must still be running at
`http://localhost:6333` for HR policy initialization and search; that is a
separate requirement from the old LangGraph import failure.
