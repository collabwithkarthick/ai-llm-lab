# Setup and Run

This project requires Python 3.10 or later and a Gemini API key.

## 1. Open the project folder

Open PowerShell and change to the project directory:

```powershell
cd D:\assignments\ai-llm-lab\AI-Agent-Basic
```

Check that Python is installed:

```powershell
python --version
```

## 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can allow scripts for just the current
PowerShell session and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Configure the Gemini API key

Copy the example environment file and open the copy:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `GEMINI_API_KEY` to your own key, then save the file:

```text
GEMINI_API_KEY=your_api_key_here
```

Keep the real key private. Do not commit or share `.env`. The program also
accepts `GOOGLE_API_KEY` or `LLM_API_KEY` as environment variables. You can
optionally change `GEMINI_MODEL` in `.env`; by default it uses
`gemini-2.5-flash`.

## 5. Run the agent

For example, ask it to use the sample route notes, search for the conversion
factor, and calculate the distance in miles:

```powershell
python .\agent.py --task "Read data/route_notes.txt, find the kilometers-to-miles conversion factor, calculate the distance in miles, and round it to one decimal place."
```

The agent prints its steps and tool observations, then prints the final answer.
It can use only the `read_file`, `web_search`, and `calculate` tools. File reads
are restricted to the project's `data` directory.

Useful options:

```powershell
python .\agent.py --help
python .\agent.py --model gemini-2.5-flash --max-steps 8 --task "Your task here"
```

The agent allows eight reasoning/action steps by default. `--max-steps` changes
that limit.

## 6. Run the tests (optional)

The unit tests are offline and do not require a Gemini API key:

```powershell
python -m unittest -v
```

When finished, leave the virtual environment with:

```powershell
deactivate
```
