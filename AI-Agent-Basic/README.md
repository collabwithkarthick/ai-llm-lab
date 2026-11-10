# Agent-Basic

A small, from-scratch ReAct agent in Python. It uses Gemini to choose a
**Thought → Action → Observation** step, executes only one of three allowlisted
tools, and feeds the observation back to Gemini before the next step.

Requires Python 3.10 or later.

## Tools

- `web_search`: searches the public web and returns up to five results.
- `calculate`: evaluates basic arithmetic and `round()` without using `eval`.
- `read_file`: reads UTF-8 text files only from `data/`, with a 64 KiB limit.

The loop is bounded to eight steps by default. Gemini and search requests retry
transient failures at most three times with exponential backoff. Tool errors
are returned to the agent as observations; invalid model responses can be
corrected in a subsequent step.

## Setup

From `D:\assignments\Agent-Basic`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in `.env`. Keep the real key private and out of version
control. Alternatively, set `GEMINI_API_KEY`, `GOOGLE_API_KEY`, or `LLM_API_KEY`
in the process environment.

## Run a multi-step task

```powershell
python .\agent.py --task "Read data/route_notes.txt, search the web for the number of miles in one kilometer, calculate the route distance in miles rounded to one decimal place, and explain the result."
```

The program prints each step's thought, action, and observation, followed by the
final answer. The route notes and search results are treated as untrusted data,
and the agent cannot use tools beyond the three listed above.

## Tests

Run the offline tests without an API key or network access:

```powershell
python -m unittest -v
```
