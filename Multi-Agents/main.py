from __future__ import annotations

import logging
from pathlib import Path

from src.agents.hr_agent import HRPolicyAgent
from src.agents.it_agent import ITSupportAgent
from src.agents.supervisor import SupervisorAgent
from src.tools.mcp_tools import initialize_sqlite

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger("enterprise_helpdesk_demo")


def ensure_project_ready() -> None:
    """Create the SQLite database and ensure the Qdrant policy collection is ready."""
    initialize_sqlite()
    # Intentionally create the HR agent so the collection is initialized on first run.
    HRPolicyAgent()


def run_demo() -> None:
    """Run a realistic end-to-end helpdesk scenario spanning HR policy and IT workflow."""
    logger.info("Starting enterprise helpdesk demo.")
    ensure_project_ready()

    hr_agent = HRPolicyAgent()
    it_agent = ITSupportAgent()
    supervisor = SupervisorAgent(hr_agent=hr_agent, it_agent=it_agent)

    employee_query = (
        "Employee 1001 has been with the company for 3.5 years, is currently in relocation status, "
        "and wants a new MacBook Pro. Check the policy for eligibility and if approved, create a ticket "
        "for $2200."
    )

    logger.info("User request: %s", employee_query)
    result = supervisor.process(employee_query)

    print("\n=== FINAL RESPONSE ===\n")
    print(result["final_response"])
    print("\n=== LOGS ===\n")
    for entry in result.get("logs", []):
        print(f"- {entry}")


if __name__ == "__main__":
    run_demo()
