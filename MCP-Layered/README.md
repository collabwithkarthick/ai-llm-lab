# MCP-Basic

A runnable MCP demo with a Python server, a Python host client, and a SQLite
database. It supports **stdio** (a host starts the server process) and
**Streamable HTTP** (the server runs separately at
`http://127.0.0.1:8000/mcp` by default). Both transports expose the same tools
and resource. See [integration_steps.md](./integration_steps.md) for the
complete setup and connection walkthrough.

The server exposes:

- Tools: `add_numbers`, `count_words`, `list_notes`, and `add_note`
- Resource: `mcp-basic://server-info`
- SQLite table: `notes` in `demo.sqlite3` (created and seeded on first start)

## Quick start: stdio Python host

From this project directory in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\host.py
```

`host.py` is a small MCP host application. It launches `server.py` using the
same Python interpreter, initializes an MCP client session, lists the tools,
calls `add_numbers` with `2` and `3`, reads notes, and calls `add_note`. Each
host run adds one note. The server uses `demo.sqlite3` beside the source files
by default.

To select another database file, set the same environment variable before
starting the host:

```powershell
$env:MCP_BASIC_DB_PATH = "$PWD\data\demo.sqlite3"
.\.venv\Scripts\python.exe .\host.py
```

The server creates the parent directory and table when it starts. To run over
HTTP instead, start the server in one terminal:

```powershell
.\.venv\Scripts\python.exe .\server.py --transport streamable-http
```

Then connect from another terminal. This initializes an MCP session, discovers
the server's tools, and invokes `add_numbers` with `2` and `3`:

```powershell
.\.venv\Scripts\python.exe .\host.py --transport http
```

The output includes the result (`5`). The demo also calls `add_note`, which
modifies `demo.sqlite3`.

See
[integration_steps.md](./integration_steps.md) for HTTP, VS Code, Claude
Desktop, and MCP Inspector instructions.

## MCP Inspector

MCP Inspector is an interactive developer tool for testing and debugging MCP
servers. It acts as a temporary MCP host: it connects to a server, performs
the MCP initialization and capability discovery, and provides a browser-based
interface for listing and invoking tools, reading resources, and (when
available) inspecting prompts. It is useful for checking that a server works
before configuring an application such as VS Code or Claude Desktop. It is
not the MCP server itself and does not replace a production host.

For stdio, the Inspector launches the server process using the command and
arguments you provide. For Streamable HTTP, it connects to an already-running
server at its MCP endpoint. Start either option from this project directory.
The commands require Node.js/npm. In PowerShell, use `npx.cmd` to avoid the
PowerShell script-execution-policy error from `npx.ps1`.

```powershell
npx.cmd -y @modelcontextprotocol/inspector .\.venv\Scripts\python.exe .\server.py
```

Open the Inspector URL it prints. For stdio, choose the **Tools** view and
invoke `add_numbers`, `count_words`, `list_notes`, or `add_note`; choose
**Resources** to read `mcp-basic://server-info`. Calling `add_note` changes
the server's SQLite database. Close the Inspector process from its terminal
when finished.

To inspect an HTTP server, start it first in another terminal:

```powershell
.\.venv\Scripts\python.exe .\server.py --transport streamable-http
```

Then start Inspector without a server command:

```powershell
npx.cmd -y @modelcontextprotocol/inspector
```

In the Inspector UI, choose **Streamable HTTP**, enter
`http://127.0.0.1:8000/mcp`, and connect. Open **Tools**, select
`add_numbers`, enter `2` for `first` and `3` for `second`, and run the tool;
the result should be `5`. Calling `add_note` writes to the server's SQLite
database. Inspector is a client UI and does not need an LLM to invoke a tool.

## VS Code configuration

Open this project folder in VS Code. `.vscode/mcp.json` registers the MCP
server and tells VS Code how to launch it; its `command` explicitly selects
`.venv\Scripts\python.exe`. `.vscode/settings.json` sets the Python extension's
default interpreter for editor, run, and debug features. It does not register
an MCP server or supersede the command in `mcp.json`. If VS Code already has a
different interpreter selected, use **Python: Select Interpreter** to choose
`.venv`.

Open **Chat**, open the MCP servers list, and start **MCP-Basic**. For an
already-running HTTP server, start **MCP-Basic-HTTP** instead. The included
`.vscode/mcp.json` registers both transports, so you do not need a second
config file or to rename the stdio config. Start the server separately with
`.\.venv\Scripts\python.exe .\server.py --transport streamable-http` before
starting the HTTP entry. See [integration_steps.md](./integration_steps.md)
for the full HTTP check.

## Claude Desktop (stdio)

First install the dependencies in the Python environment you want Claude to
use. In Claude Desktop, open **Settings → Developer → Edit Config** and add
the `MCP-Basic` entry under `mcpServers` in
`claude_desktop_config.json` (use escaped backslashes in Windows paths):

```json
{
  "mcpServers": {
    "MCP-Basic": {
      "command": "D:\\assignments\\MCP-Basic\\.venv\\Scripts\\python.exe",
      "args": ["D:\\assignments\\MCP-Basic\\server.py"]
    }
  }
}
```

Change both paths if this project is stored elsewhere. Preserve any other
servers already in the config, save it, and fully quit and restart Claude
Desktop. Open a chat and use its MCP tools menu to inspect or invoke the
`MCP-Basic` tools. The host starts the server automatically; there is no
separate server terminal to keep open.

## SQLite details

`list_notes` and `add_note` are MCP tools backed by Python's built-in `sqlite3`
module. `add_note` uses SQL placeholders for its values. The default database
is a local demo file, not a network database; do not put sensitive data in it.
To reset the demo, stop all connected hosts and remove `demo.sqlite3`; the
server recreates its schema and welcome note on its next start.
