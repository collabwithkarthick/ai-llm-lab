"""Example Python MCP host that starts server.py over stdio and calls its tools."""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client


SERVER_PATH = Path(__file__).with_name("server.py")
DB_PATH = Path(
    os.environ.get("MCP_BASIC_DB_PATH", Path(__file__).with_name("demo.sqlite3"))
).expanduser()


async def run_demo(session: ClientSession) -> None:
    await session.initialize()
    tools = await session.list_tools()
    print("Connected to MCP-Basic. Available tools:")
    for tool in tools.tools:
        print(f"- {tool.name}: {tool.description}")

    sum_result = await session.call_tool(
        "add_numbers",
        {"first": 2, "second": 3},
    )
    print("\nadd_numbers(2, 3) result:")
    print(json.dumps(sum_result.model_dump(mode="json"), indent=2))

    notes = await session.call_tool("list_notes", {})
    print("\nExisting notes:")
    print(json.dumps(notes.model_dump(mode="json"), indent=2))

    saved = await session.call_tool(
        "add_note",
        {
            "title": "Created by the Python host",
            "content": "The host called an MCP tool; the server saved this in SQLite.",
        },
    )
    print("\nadd_note result:")
    print(json.dumps(saved.model_dump(mode="json"), indent=2))

    updated_notes = await session.call_tool("list_notes", {})
    print("\nNotes after add_note:")
    print(json.dumps(updated_notes.model_dump(mode="json"), indent=2))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Connect a Python host to MCP-Basic.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="Connect over stdio or Streamable HTTP (default: stdio).",
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/mcp",
        help="Streamable HTTP MCP endpoint (default: %(default)s).",
    )
    args = parser.parse_args()

    if args.transport == "http":
        async with streamablehttp_client(args.url) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await run_demo(session)
        return

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        env={**os.environ, "MCP_BASIC_DB_PATH": str(DB_PATH)},
    )
    async with stdio_client(server, errlog=sys.stderr) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await run_demo(session)


if __name__ == "__main__":
    asyncio.run(main())
