# Execution Steps: Ingest PDFs and Ask the RAG CLI

Run these commands in PowerShell from the RAG project folder. Complete
[setup_instructions.md](./setup_instructions.md) first. No web app is required.

LiteLLM requires two separate credentials in the local `.env` file:

- `GEMINI_API_KEY` is the key LiteLLM uses to call Gemini.
- `LLM_API_KEY` is a strong, independently generated secret used by the CLI
  and LiteLLM to authenticate requests to the local gateway.

Do not use the Gemini key as `LLM_API_KEY`, and never commit or share either
key. If you change either key, recreate the gateway so it picks up the new
values:

```powershell
docker compose -f podman-compose.yml up -d --force-recreate litellm
```

## 1. Confirm Qdrant and Gemini gateway are running

```powershell
docker compose -f qdrant-docker-compose.yml ps
docker compose -f podman-compose.yml ps
```

If either service is stopped, start it:

```powershell
docker compose -f qdrant-docker-compose.yml up -d
docker compose -f podman-compose.yml up -d litellm
```

Check Qdrant responds:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:6333/collections
```

## 2. Ingest the PDFs into Qdrant

Run:

```powershell
.\.venv\Scripts\python.exe src\ingest_pdf.py
```

The script finds PDFs recursively under `data\`, extracts non-empty pages,
creates embeddings, and writes them to the `enterprise_policies` collection.
Each page point also stores its `allowed_groups` metadata from
`src\document_access.py`.

**Ingestion replaces the `enterprise_policies` collection.** If the PDFs or
document access rules change, run ingestion again to rebuild the collection.
The first run may download the embedding model.

To check the indexed documents and test retrieval without asking Gemini:

```powershell
.\.venv\Scripts\python.exe src\inspect_qdrant.py "broadband expense claim"
```

## 3. Create sample CLI users

The demo has two access groups:

- `employees`: can retrieve the broadband reimbursement policy.
- `it`: can retrieve the laptop upgrade policy and IT/broadband SOP.

Run this sample PowerShell script from the project folder to create an
employee-only account and an IT account. Each command prompts for a password
without displaying it; use at least 12 characters. Run the script once; the
account manager rejects duplicate usernames.

```powershell
$python = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python environment not found. Complete setup_instructions.md first."
}

& $python src\manage_demo_users.py add employee_demo employees
if ($LASTEXITCODE -ne 0) { throw "Could not create employee_demo." }

& $python src\manage_demo_users.py add it_demo employees it
if ($LASTEXITCODE -ne 0) { throw "Could not create it_demo." }

& $python src\manage_demo_users.py list
if ($LASTEXITCODE -ne 0) { throw "Could not list demo users." }
```

Expected user/group listing:

```text
employee_demo: employees
it_demo: employees, it
```

The employee account can retrieve only the broadband reimbursement policy.
The IT account belongs to both groups and can retrieve all three sample
policies. Account group membership is saved locally in
`data\demo_users.json`; passwords are stored as salted hashes, never plaintext.

To create a single account later, substitute your username and one or more
valid groups (`employees` and/or `it`). For example, an IT-only user can be
created with:

```powershell
.\.venv\Scripts\python.exe src\manage_demo_users.py add it_only_demo it
```

List users or remove one when no longer needed:

```powershell
.\.venv\Scripts\python.exe src\manage_demo_users.py list
.\.venv\Scripts\python.exe src\manage_demo_users.py remove employee_demo
```

## 4. Start the terminal RAG chat

```powershell
.\.venv\Scripts\python.exe src\rag_chat.py
```

Sign in with one of the accounts you created. The password is entered without
being echoed. Ask a policy question, for example:

```text
What is the monthly broadband reimbursement cap?
```

The CLI embeds the question, asks Qdrant for the best-matching documents that
the signed-in user's groups are allowed to access, then sends only those
retrieved passages and the question to LiteLLM. LiteLLM calls the configured
Gemini model and the CLI prints the answer and source passages.

To leave the chat, type `exit` or `quit`.

## 5. Stop the services

Stop the gateway and Qdrant when finished:

```powershell
docker compose -f podman-compose.yml stop litellm
docker compose -f qdrant-docker-compose.yml stop qdrant
```

Stopping containers keeps the Qdrant volume and its indexed data. Do not add
`-v` to a Docker Compose `down` command unless you intentionally want to delete
the stored Qdrant data.

## Troubleshooting

- **`.venv\Scripts\python.exe` is not recognized:** Windows virtual
  environments use `Scripts`; Linux/WSL environments use `bin` and cannot be
  run from Windows PowerShell. Follow the virtual-environment steps in
  [setup_instructions.md](./setup_instructions.md) to create a Windows
  environment. The existing environment is renamed, not deleted.
- **Docker command not found:** restart PowerShell after installing Docker
  Desktop, and make sure Docker Desktop is running.
- **Qdrant connection refused:** check `docker compose -f
  qdrant-docker-compose.yml ps` and inspect logs with
  `docker compose -f qdrant-docker-compose.yml logs --tail 80 qdrant`.
- **LiteLLM cannot start due to a missing master key:** set a strong random
  `LLM_API_KEY` in `.env`, then recreate the gateway with
  `docker compose -f podman-compose.yml up -d --force-recreate litellm`.
  Also check that `.env` contains a valid `GEMINI_API_KEY`, then inspect
  `docker compose -f podman-compose.yml logs --tail 80 litellm`.
- **LiteLLM rejects a request parameter:** `config\litellm_config.yaml` sets
  `drop_params: true` so unsupported parameters are omitted. Recreate LiteLLM
  to load config changes:
  `docker compose -f podman-compose.yml up -d --force-recreate litellm`.
- **CLI reports an LLM gateway error:** confirm LiteLLM is running and `.env`
  has `LLM_GATEWAY_URL=http://127.0.0.1:4000` and
  `LLM_MODEL=helpdesk-llm`.
- **CLI says no demo accounts exist:** create an account using
  `src\manage_demo_users.py add`.
- **A PDF has no access rule:** add its filename and groups to
  `src\document_access.py`, then rerun ingestion.

## Demo security note

The local user registry and Qdrant group filter demonstrate authentication and
authorization in a CLI. They are not a production security boundary: anyone
with direct access to Qdrant can bypass the CLI filter. Keep services local
and use a production identity provider and secured database access for real
confidential documents.
