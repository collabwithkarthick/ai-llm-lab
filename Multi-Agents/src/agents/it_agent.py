from __future__ import annotations

import logging
import re
from typing import Any

from src.tools.mcp_tools import create_support_ticket, get_employee_info

logger = logging.getLogger(__name__)


class ITSupportAgent:
    """Worker agent that resolves employee records and raises support tickets via MCP tools."""

    def __init__(self, mcp_server: Any | None = None) -> None:
        self.mcp_server = mcp_server

    @staticmethod
    def extract_employee_id(user_input: str) -> str:
        patterns = [
            r"employee\s*(?:id|#)?\s*(\d+)",
            r"emp(?:loyee)?\s*(?:id)?\s*(\d+)",
            r"\b(\d{4,})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, user_input, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        raise ValueError("No employee identifier was found in the request.")

    @staticmethod
    def extract_requested_item(user_input: str) -> str:
        lower = user_input.lower()
        item_overrides = {
            "laptop": "new laptop",
            "macbook": "MacBook Pro",
            "monitor": "monitor",
            "keyboard": "keyboard",
            "headset": "headset",
        }
        for token, item in item_overrides.items():
            if token in lower:
                return item
        return "device upgrade"

    @staticmethod
    def extract_cost(user_input: str) -> float:
        match = re.search(r"\$(\d+(?:\.\d+)?)", user_input)
        if match:
            return float(match.group(1))
        return 0.0

    def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a tool either through the provided MCP server or directly against the local tool module."""
        logger.info("Calling MCP tool %s with args=%s", tool_name, kwargs)
        if self.mcp_server is not None:
            try:
                return self.mcp_server.call_tool(tool_name, **kwargs)
            except AttributeError:
                logger.warning("MCP server call_tool API not available; falling back to local tool functions.")

        if tool_name == "get_employee_info":
            return get_employee_info(**kwargs)
        if tool_name == "create_support_ticket":
            return create_support_ticket(**kwargs)
        raise ValueError(f"Unsupported MCP tool requested: {tool_name}")

    def get_employee(self, emp_id: str) -> dict[str, Any]:
        """Fetch employee details via the MCP-backed tool."""
        try:
            employee = self.call_tool("get_employee_info", emp_id=emp_id)
            logger.info("Retrieved employee record for %s", emp_id)
            return employee
        except Exception as exc:
            logger.exception("Employee lookup failed for emp_id=%s", emp_id)
            raise RuntimeError(f"Unable to load employee {emp_id}: {exc}") from exc

    def create_ticket(self, emp_id: str, item_requested: str, cost: float) -> dict[str, Any]:
        """Create a support ticket for an employee using the MCP-backed tool."""
        try:
            ticket = self.call_tool("create_support_ticket", emp_id=emp_id, item_requested=item_requested, cost=cost)
            logger.info("Ticket created for %s: %s", emp_id, ticket)
            return ticket
        except Exception as exc:
            logger.exception(
                "Ticket creation failed for emp_id=%s item=%s cost=%s",
                emp_id,
                item_requested,
                cost,
            )
            raise RuntimeError(f"Unable to create support ticket for {emp_id}: {exc}") from exc

    def run(self, user_input: str) -> dict[str, Any]:
        """Resolve the employee and create ticket actions in one pass."""
        logger.info("ITSupportAgent processing input: %s", user_input)
        try:
            emp_id = self.extract_employee_id(user_input)
            item_requested = self.extract_requested_item(user_input)
            cost = self.extract_cost(user_input)
            employee = self.get_employee(emp_id)
            ticket = self.create_ticket(emp_id, item_requested, cost)
            return {
                "status": "success",
                "employee": employee,
                "ticket": ticket,
                "summary": (
                    f"Employee {emp_id} ({employee['first_name']} {employee['last_name']}) is eligible for "
                    f"{item_requested} and a ticket was created with a cost of ${cost:.2f}."
                ),
            }
        except ValueError as exc:
            logger.warning("User input is missing required IT data: %s", exc)
            return {
                "status": "error",
                "error": str(exc),
                "summary": "Could not determine the employee id or requested item from the provided input.",
            }
        except Exception as exc:
            logger.exception("IT support workflow failed")
            return {
                "status": "error",
                "error": str(exc),
                "summary": "The IT workflow failed while checking employee status or creating a ticket.",
            }


__all__ = ["ITSupportAgent"]
