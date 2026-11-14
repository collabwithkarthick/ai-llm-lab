# Multi-Agent Helpdesk Demo Setup

This project runs a command-line helpdesk demo that coordinates an HR policy
retrieval agent and an IT support agent. The IT agent reads employee records
and creates support tickets in a local SQLite database. HR policies are stored
in Qdrant and searched using locally generated FastEmbed embeddings.

## Requirements

- Python 3.10 or later
- Docker Desktop (or another way to run Qdrant)
- Internet access the first time FastEmbed downloads its embedding model

No LLM API key is needed.

## 1. Open the project directory

Run the following commands from the `Multi-Agents` directory:

```powershell
cd D:\assignments\ai-llm-lab\Multi-Agents
```

## 2. Create and activate a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell prevents activation, allow scripts for the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Install Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Start the shared Qdrant service

The HR agent connects to Qdrant at `http://localhost:6333`. You can use the
Qdrant service already configured by
[`RAG-Layered`](../RAG-Layered/qdrant-docker-compose.yml), rather than running
a separate container. From this `Multi-Agents` directory, start it with:

```powershell
docker compose -f ..\RAG-Layered\qdrant-docker-compose.yml up -d qdrant
```

Check its status and verify the endpoint:

```powershell
docker compose -f ..\RAG-Layered\qdrant-docker-compose.yml ps
Invoke-RestMethod -Uri http://127.0.0.1:6333/collections
```

Both projects use the `enterprise_policies` collection and the same
384-dimensional `BAAI/bge-small-en-v1.5` embeddings, so the Multi-Agents HR
agent can search vectors created by RAG-Layered. However, RAG-Layered's
`src\ingest_pdf.py` deletes and rebuilds that collection when it ingests PDFs.
Multi-Agents does not apply RAG-Layered's `allowed_groups` access filter, so
do not use it to retrieve group-restricted documents unless you first add
equivalent access checks.

Only one Qdrant container can publish port `6333` at a time. Do not start the
old `multi-agents-qdrant` container alongside the RAG-Layered service.

## 5. Run the demo

With the virtual environment active and Qdrant running:

```powershell
python main.py
```

The first run initializes the SQLite database at `data/enterprise.db` and
ensures the Qdrant policy collection exists. Built-in demo policies are seeded
only when that collection is empty; if RAG-Layered has already populated the
shared collection, the HR agent searches those existing policy vectors.
FastEmbed may download its embedding model on first use. The program then
prints the helpdesk response and its orchestration logs.

## Demo behavior and data

- The sample request in `main.py` uses employee `1001` and requests a MacBook
  Pro for `$2200`.
- Each successful run creates a new support ticket; repeated runs can create
  duplicate tickets.
- SQLite initialization inserts the sample employees if they are not already
  present. Existing employees and tickets in `data/enterprise.db` are retained.
- The shared Qdrant data persists in the volume managed by RAG-Layered's
  Compose project. The stopped `multi-agents-qdrant` container has a separate
  volume; its data is not the same as the shared RAG-Layered collection.
- The agents and tools can also be imported from `src.agents` and `src.tools`.
  `main.py` runs the integrated demo; it does not start a web application or
  an MCP server.

To stop the shared Qdrant service when finished (this also stops it for
RAG-Layered):

```powershell
docker compose -f ..\RAG-Layered\qdrant-docker-compose.yml stop qdrant
```
