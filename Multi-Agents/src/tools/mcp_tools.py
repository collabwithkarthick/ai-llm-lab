from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - handled gracefully at runtime
    FastMCP = None
    FASTMCP_IMPORT_ERROR = exc
else:
    FASTMCP_IMPORT_ERROR = None

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "enterprise.db"


def _connect_db() -> sqlite3.Connection:
    """Create and configure a SQLite connection for the enterprise database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_sqlite() -> None:
    """Initialize the SQLite schema and bootstrap demo employee data."""
    logger.info("Initializing SQLite database at %s", DB_PATH)
    connection = _connect_db()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                emp_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                department TEXT NOT NULL,
                manager TEXT NOT NULL,
                email TEXT NOT NULL,
                tenure_years REAL NOT NULL,
                relocation_status TEXT NOT NULL,
                device_model TEXT NOT NULL,
                device_eligible INTEGER NOT NULL,
                cost_center TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id TEXT NOT NULL,
                item_requested TEXT NOT NULL,
                cost REAL NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                FOREIGN KEY(emp_id) REFERENCES employees(emp_id)
            );
            """
        )

        demo_employees = [
            (
                "1001",
                "Aisha",
                "Patel",
                "Engineering",
                "Priya Shah",
                "aisha.patel@example.com",
                3.5,
                "in_transit",
                "MacBook Pro 14",
                1,
                "ENG-102",
            ),
            (
                "1002",
                "Marcus",
                "Nguyen",
                "Finance",
                "Lena Alvarez",
                "marcus.nguyen@example.com",
                1.8,
                "none",
                "Dell Latitude 7440",
                0,
                "FIN-204",
            ),
            (
                "1003",
                "Rachel",
                "Kim",
                "Operations",
                "Chris Bell",
                "rachel.kim@example.com",
                5.2,
                "approved",
                "ThinkPad X1",
                1,
                "OPS-310",
            ),
        ]

        connection.executemany(
            """
            INSERT OR IGNORE INTO employees (
                emp_id, first_name, last_name, department, manager, email,
                tenure_years, relocation_status, device_model, device_eligible, cost_center
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            demo_employees,
        )
        connection.commit()
        logger.info("SQLite initialization completed successfully.")
    except sqlite3.Error as exc:  # pragma: no cover - runtime validation
        logger.exception("SQLite initialization failed: %s", exc)
        connection.rollback()
        raise
    finally:
        connection.close()


def get_employee_info(emp_id: str) -> dict[str, Any]:
    """Return the employee record for the given id."""
    if not emp_id or not emp_id.strip():
        raise ValueError("Employee id must be a non-empty string.")

    connection = _connect_db()
    try:
        row = connection.execute(
            "SELECT * FROM employees WHERE emp_id = ?",
            (emp_id.strip(),),
        ).fetchone()
        if row is None:
            raise LookupError(f"No employee record found for emp_id={emp_id!r}.")
        return dict(row)
    except sqlite3.Error as exc:
        logger.exception("Failed to fetch employee info for emp_id=%s", emp_id)
        raise RuntimeError(f"Database error while looking up employee {emp_id}.") from exc
    finally:
        connection.close()


def create_support_ticket(emp_id: str, item_requested: str, cost: float) -> dict[str, Any]:
    """Insert a new support ticket linked to the employee record."""
    if not emp_id or not emp_id.strip():
        raise ValueError("Employee id must be provided for ticket creation.")
    if not item_requested or not item_requested.strip():
        raise ValueError("Requested item cannot be empty.")
    if cost < 0:
        raise ValueError("Ticket cost cannot be negative.")

    employee = get_employee_info(emp_id)
    connection = _connect_db()
    try:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = connection.execute(
            """
            INSERT INTO support_tickets (emp_id, item_requested, cost, created_at, status)
            VALUES (?, ?, ?, ?, 'open')
            """,
            (employee["emp_id"], item_requested.strip(), float(cost), timestamp),
        )
        connection.commit()
        ticket_id = cursor.lastrowid
        return {
            "ticket_id": ticket_id,
            "emp_id": employee["emp_id"],
            "employee_name": f"{employee['first_name']} {employee['last_name']}",
            "item_requested": item_requested.strip(),
            "cost": float(cost),
            "created_at": timestamp,
            "status": "open",
        }
    except sqlite3.Error as exc:
        logger.exception(
            "Failed to create support ticket for emp_id=%s item=%s cost=%s",
            emp_id,
            item_requested,
            cost,
        )
        connection.rollback()
        raise RuntimeError(f"Database error while creating a ticket for {emp_id}.") from exc
    finally:
        connection.close()


class FastMCPServer:
    """Thin wrapper around a FastMCP server exposing enterprise support tools."""

    def __init__(self, name: str = "enterprise-helpdesk") -> None:
        if FastMCP is None:
            raise RuntimeError(
                "FastMCP is required but not installed. Install it via `pip install fastmcp`. "
                f"Original import error: {FASTMCP_IMPORT_ERROR}"
            )
        self.name = name
        self.server = FastMCP(name)

    def register_tools(self) -> Any:
        logger.info("Registering FastMCP tools for %s", self.name)
        self.server.tool()(get_employee_info)
        self.server.tool()(create_support_ticket)
        return self.server

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return self.server.run(*args, **kwargs)


mcp_server = FastMCPServer().register_tools()


__all__ = [
    "DB_PATH",
    "FastMCPServer",
    "create_support_ticket",
    "get_employee_info",
    "initialize_sqlite",
    "mcp_server",
]
