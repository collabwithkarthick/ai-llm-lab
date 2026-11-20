"""A small MCP server with SQLite-backed tools and an informational resource."""

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("MCP-Basic")
DB_PATH = Path(
    os.environ.get("MCP_BASIC_DB_PATH", Path(__file__).with_name("demo.sqlite3"))
).expanduser()


def initialize_database() -> None:
    """Create the notes table and add a welcome note once."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH, timeout=5)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO notes (title, content)
                SELECT ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM notes WHERE title = ?
                )
                """,
                (
                    "Welcome to MCP-Basic",
                    "This note is stored in SQLite and can be read through MCP.",
                    "Welcome to MCP-Basic",
                ),
            )


@mcp.tool()
def add_numbers(first: float, second: float) -> float:
    """Add two numbers and return their sum."""
    return first + second


@mcp.tool()
def count_words(text: str) -> int:
    """Count whitespace-separated words in the supplied text."""
    return len(text.split())


@mcp.tool()
def list_notes() -> list[dict[str, object]]:
    """Return all notes stored in the SQLite database."""
    with closing(sqlite3.connect(DB_PATH, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, title, content, created_at FROM notes ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


@mcp.tool()
def add_note(title: str, content: str) -> dict[str, int | str]:
    """Save a note to SQLite and return its ID and timestamp."""
    with closing(sqlite3.connect(DB_PATH, timeout=5)) as connection:
        with connection:
            cursor = connection.execute(
                "INSERT INTO notes (title, content) VALUES (?, ?)",
                (title, content),
            )
            note_id = cursor.lastrowid
            row = connection.execute(
                "SELECT created_at FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
    return {"id": note_id, "created_at": row[0]}


@mcp.resource("mcp-basic://server-info")
def server_info() -> str:
    """Describe the tools and resource exposed by this server."""
    return (
        "MCP-Basic demo server. Tools: add_numbers adds two numbers; "
        "count_words counts whitespace-separated words; list_notes reads notes "
        "from SQLite; add_note writes a note to SQLite. "
        "Resource: mcp-basic://server-info."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MCP-Basic server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport to use (default: stdio).",
    )
    args = parser.parse_args()

    initialize_database()
    mcp.run(transport=args.transport)
