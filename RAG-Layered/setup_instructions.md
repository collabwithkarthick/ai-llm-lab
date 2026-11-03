# Setup Instructions: Docker, Qdrant, and Gemini

This guide is for a Windows user setting up the command-line RAG demo for the
first time. It starts Qdrant and the LiteLLM-to-Gemini gateway in Docker. The
Flask web app is not needed.

## What you will set up

- **Docker Desktop** runs Qdrant and LiteLLM in containers.
- **Qdrant** stores PDF embeddings and searchable document metadata.
- **Python** runs PDF ingestion and the terminal chat.
- **Gemini** generates answers from the passages retrieved from Qdrant.

## 1. Install Docker Desktop

1. Open the official [Docker Desktop for Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/).
2. Download and run the Docker Desktop installer.
3. If asked which backend to use, choose **WSL 2**.
4. If the installer asks to install or enable WSL 2, allow it and restart
   Windows if requested.
5. Launch Docker Desktop from the Start menu and wait until it reports that
   Docker is running.

Open a new PowerShell window and verify the installation:

```powershell
docker --version
docker compose version
```

Both commands should print version information. If `docker` is not recognized,
reopen PowerShell after installation. If Docker Desktop says its engine is
stopped, start Docker Desktop and wait for it to finish starting.

## 2. Open the project folder

In PowerShell, change to the RAG project folder. For example:

```powershell
cd "D:\assignments\llm-handson\case-study\enterprise-helpdesk\RAG"
```

Use the actual folder where you saved the project if it differs.

## 3. Start Qdrant by itself

Start only the Qdrant service:

```powershell
docker compose -f qdrant-docker-compose.yml up -d
```

The first run downloads the Qdrant image, so it may take a few minutes. Check
that the container is running:

```powershell
docker compose -f qdrant-docker-compose.yml ps
```

Check that the Qdrant API responds:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:6333/collections
```

An empty collection list is normal before ingestion. The compose file keeps
Qdrant's data in a Docker-managed volume and publishes its API on the Windows
machine's localhost.

## 4. Install Python and project dependencies

Install Python 3.12 for Windows from the [official Python downloads page](https://www.python.org/downloads/windows/).
During installation, enable **Add python.exe to PATH**. Open a new PowerShell
window after installation and verify:

```powershell
py -3.12 --version
```

From the project folder, create and activate a Windows virtual environment,
then install the project requirements:

```powershell
if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.12 -m venv .venv }
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `py` is not recognized, install Python 3.12 with the Python launcher, or
use `python -m venv .venv` after confirming `python --version` reports Python
3.12.
Activation is optional: you can skip `Activate.ps1` and run
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt` instead.
If PowerShell blocks the activation script, use that direct command; do not
change the execution policy just for activation.

The embedding model used by ingestion is downloaded the first time it runs.
That first ingestion therefore needs internet access.

## 5. Configure the Gemini key locally

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
Keep it private; do not paste it into source code, a README, or a chat message.

Create a local `.env` from the example if it does not already exist, then
open it:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Replace the placeholder values from `.env.example` with your own settings.

`LLM_API_KEY` is a local secret shared by the RAG CLI and LiteLLM for gateway
authentication. Generate a strong random value for it; do not use your Gemini
key for this setting. LiteLLM uses it as its master key.

Save and close Notepad. The `helpdesk-llm` model alias is configured to use
Gemini in `config\litellm_config.yaml`.

The `.env` file contains a secret. Do not commit or share it. The project
`.gitignore` excludes it from Git.

## 6. Start the Gemini gateway

In the same project folder, start only LiteLLM:

```powershell
docker compose -f podman-compose.yml up -d litellm
```

The command reads `GEMINI_API_KEY` and `LLM_API_KEY` from `.env` and passes
them to the gateway. `LLM_API_KEY` is required; Compose reports an error if it
is missing or empty.
Check the service and, if it is still starting, inspect its logs:

```powershell
docker compose -f podman-compose.yml ps
docker compose -f podman-compose.yml logs --tail 80 litellm
```

The gateway should be available at `http://127.0.0.1:4000`. The RAG CLI needs
both Qdrant and LiteLLM running to return generated answers.

Continue with [execution_steps.md](./execution_steps.md) to ingest documents,
create demo users, and ask questions from the terminal.
