# MCP-Basic integration walkthrough

This project can run over **stdio** or **Streamable HTTP**. Both transports
expose the same tools and resource and use the same SQLite-backed server code.
Choose the transport supported by the host you are connecting.

| Transport | How it runs | Endpoint/process | Typical use |
|---|---|---|---|
| stdio | The host starts the server as a child process. | No network endpoint. | Local desktop hosts such as VS Code or Claude Desktop, and local Python clients. |
| Streamable HTTP | Start the server separately; the host connects to it. | `http://127.0.0.1:8000/mcp` by default. | A separate Python host, MCP Inspector, or an HTTP-capable MCP host. |

Both examples use Python 3.13 and the dependencies in `requirements.txt`.
From the project directory in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## A. Connect over stdio

### Run the Python host example

```powershell
.\.venv\Scripts\python.exe .\host.py
```

The host starts `server.py`, completes the MCP handshake, lists tools, calls
`add_numbers` with `2` and `3`, then calls `list_notes` and `add_note` and
lists the notes again. The server process exits when the host disconnects. The
default SQLite file is `demo.sqlite3` beside the project files.

### Connect with VS Code

The workspace `.vscode\mcp.json` registers both MCP servers for VS Code's Chat
integration. The stdio entry explicitly starts the project's virtual
environment's Python interpreter; the HTTP entry connects to the separately
started server:

```json
{
  "servers": {
    "MCP-Basic": {
      "type": "stdio",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": ["${workspaceFolder}\\server.py"]
    },
    "MCP-Basic-HTTP": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

Open this folder as the VS Code workspace, install the dependencies above,
then open Chat and start **MCP-Basic** from the MCP servers list. VS Code
launches the server on demand. The MCP server entry belongs in `mcp.json`;
`settings.json` does not register or start MCP servers.

The project's `.vscode\settings.json` sets
`python.defaultInterpreterPath` to `.venv\Scripts\python.exe`. This gives the
VS Code Python extension a default interpreter for Python features such as
analysis, running, and debugging. It does not install dependencies, and it
does not override the explicit `command` in `mcp.json`. VS Code may retain a
previously selected interpreter, so select `.venv` with **Python: Select
Interpreter** if needed.

The included `.vscode\mcp.json` registers both **MCP-Basic** (stdio) and
**MCP-Basic-HTTP** (Streamable HTTP). Keep one `mcp.json`; VS Code reads the
workspace file at `.vscode\mcp.json`, so a second differently named JSON file
is not automatically loaded. Having both entries lets you test either
transport without renaming or replacing the config.

### Connect Claude Desktop

For a local stdio server, add a server entry to Claude Desktop's
`claude_desktop_config.json`, adjusting the absolute paths for your machine:

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

Preserve any existing entries, save the file, and restart Claude Desktop. Its
MCP tools interface should show `add_numbers`, `count_words`, `list_notes`,
and `add_note`. This is Claude Desktop's local stdio configuration; use a host
that supports Streamable HTTP for the HTTP example below.

### Inspect stdio tools

Run the Inspector with the server command. In PowerShell, use `npx.cmd` if
`npx` fails because script execution is disabled:

```powershell
npx.cmd -y @modelcontextprotocol/inspector .\.venv\Scripts\python.exe .\server.py
```

Open the Inspector URL printed in the terminal. Check **Tools** and invoke
`add_numbers` with `first` = `2` and `second` = `3`; the result should be `5`.
You can also invoke `add_note` then `list_notes`. Check **Resources** to read
`mcp-basic://server-info`.

## B. Connect over Streamable HTTP

### Start the HTTP server

In one PowerShell terminal, run:

```powershell
.\.venv\Scripts\python.exe .\server.py --transport streamable-http
```

The process stays running to serve requests. Its default MCP endpoint is
`http://127.0.0.1:8000/mcp`. Keep this terminal open while connected; stop the
server with **Ctrl+C**. The default bind address is loopback, so the example is
only reachable from the same computer.

### Connect the Python host

In a second terminal, run:

```powershell
.\.venv\Scripts\python.exe .\host.py --transport http
```

The host connects to `http://127.0.0.1:8000/mcp` and makes the same sample
tool calls as the stdio host. It calls `add_numbers` with `2` and `3`, then
reads and adds a note. In `host.py`, the specific tool invocation is:

```python
result = await session.call_tool("add_numbers", {"first": 2, "second": 3})
```

The demo prints the result (`5`), then also calls `list_notes` and `add_note`.
`add_note` modifies `demo.sqlite3`. To use a different endpoint:

```powershell
.\.venv\Scripts\python.exe .\host.py --transport http --url https://mcp.example.com/mcp
```

For this same-machine demo, the server and host both use `demo.sqlite3` by
default. To choose another database, set `MCP_BASIC_DB_PATH` in the **server
terminal before starting the server**; the server creates the directory and
schema on startup. A remote host only accesses the server's database through
MCP tools.

### Connect another HTTP-capable host

Use the MCP endpoint URL `http://127.0.0.1:8000/mcp` and choose
**Streamable HTTP** as its transport. In VS Code, first start the server in a
terminal using the command above, then open the MCP servers list and start
**MCP-Basic-HTTP**. The stdio entry remains available independently. The
corresponding HTTP entry in `.vscode\mcp.json` is:

```json
"MCP-Basic-HTTP": {
  "type": "http",
  "url": "http://127.0.0.1:8000/mcp"
}
```

To check the HTTP MCP connection and exercise its tools, keep the server
running in one terminal and run this in another:

```powershell
.\.venv\Scripts\python.exe .\host.py --transport http
```

The host initializes an MCP session, lists the available tools, calls
`add_numbers` with `2` and `3` (returning `5`), reads notes, then calls
`add_note` and lists notes again. This changes `demo.sqlite3`.

Alternatively, start the Inspector UI from another terminal:

```powershell
npx.cmd -y @modelcontextprotocol/inspector
```

In the UI, select **Streamable HTTP**, enter `http://127.0.0.1:8000/mcp`,
connect, open **Tools**, select `add_numbers`, enter `2` for `first` and `3`
for `second`, and run it. The result should be `5`. In PowerShell,
`npx.cmd` avoids the script-execution-policy error that can occur with `npx`.

## SQLite and deployment notes

`list_notes` reads rows from SQLite and `add_note` inserts them using
parameterized SQL. The database is local to the server process, not the
client. Both transports call the same tools and operate on the configured
database file.

This is a local demo, not a production deployment. The HTTP example has no
authentication or TLS and binds only to localhost. Do not expose it directly
to an untrusted network. A remote deployment needs appropriate authentication,
TLS, network controls, and a production process manager.
