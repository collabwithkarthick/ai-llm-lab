from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from src.agents.hr_agent import HRPolicyAgent
from src.agents.it_agent import ITSupportAgent

logger = logging.getLogger(__name__)


class SupervisorState(TypedDict):
    user_input: str
    intent: str
    hr_context: str
    it_context: str
    final_response: str
    status: str
    logs: list[str]


class SupervisorAgent:
    """Supervisor orchestrator that coordinates the HR and IT worker agents."""

    def __init__(self, hr_agent: HRPolicyAgent, it_agent: ITSupportAgent) -> None:
        self.hr_agent = hr_agent
        self.it_agent = it_agent

    def _add_log(self, state: SupervisorState, message: str) -> None:
        state["logs"] = state.get("logs", []) + [message]

    def parse_intent(self, state: SupervisorState) -> SupervisorState:
        user_input = state["user_input"]
        lower = user_input.lower()
        if any(keyword in lower for keyword in ["policy", "tenure", "relocation", "eligible", "upgrade", "device"]):
            intent = "policy_review"
        elif any(keyword in lower for keyword in ["ticket", "support", "employee", "laptop", "device"]):
            intent = "employee_action"
        else:
            intent = "general_support"

        state["intent"] = intent
        self._add_log(state, f"Intent parsed as '{intent}' for request: {user_input[:80]}")
        logger.info("Supervisor parsed intent '%s' from input '%s'", intent, user_input)
        return state

    def run_hr_lookup(self, state: SupervisorState) -> SupervisorState:
        query = state["user_input"]
        self._add_log(state, "Dispatching HR policy lookup.")
        result = self.hr_agent.run(query)
        if result.get("status") == "success":
            state["hr_context"] = result["context"]
            self._add_log(state, "HR policy lookup completed successfully.")
        else:
            state["hr_context"] = result.get("context", "No policy guidance available.")
            self._add_log(state, f"HR policy lookup encountered an issue: {result.get('error', 'unknown error')}")
        logger.info("HR lookup result: %s", result.get("status"))
        return state

    def dispatch_workers(self, state: SupervisorState) -> SupervisorState:
        self._add_log(state, "Running both worker agents for the combined request.")

        if state["intent"] in {"policy_review", "employee_action", "general_support"}:
            self.run_hr_lookup(state)
        if state["intent"] in {"policy_review", "employee_action", "general_support"}:
            self.run_it_action(state)

        return state

    def run_it_action(self, state: SupervisorState) -> SupervisorState:
        user_input = state["user_input"]
        self._add_log(state, "Dispatching IT employee lookup and ticket action.")
        try:
            result = self.it_agent.run(user_input, hr_context=state.get("hr_context", ""))
            if result.get("status") in {"success", "partial_success"}:
                state["it_context"] = (
                    f"Employee record: {result['employee']}\n\n"
                    f"Ticket outcome: {result['ticket']}\n\n"
                    f"Summary: {result['summary']}"
                )
                if result.get("status") == "partial_success":
                    self._add_log(state, result.get("error", "Ticket created but LLM summary failed."))
                else:
                    self._add_log(state, "IT action completed successfully.")
            else:
                state["it_context"] = result.get("summary", "IT workflow did not produce a result.")
                self._add_log(state, f"IT workflow issue: {result.get('error', 'unknown error')}")
        except Exception as exc:
            state["it_context"] = f"IT workflow error: {exc}"
            self._add_log(state, f"IT workflow raised an exception: {exc}")
            logger.exception("IT action failed in supervisor orchestration")
        return state

    def aggregate_response(self, state: SupervisorState) -> SupervisorState:
        hr_context = state.get("hr_context", "No policy guidance available.")
        it_context = state.get("it_context", "No IT action output available.")

        final_response = (
            "# Enterprise Helpdesk Resolution\n\n"
            "## HR Policy Guidance\n"
            f"{hr_context}\n\n"
            "## IT Action Summary\n"
            f"{it_context}\n\n"
            "## Final Recommendation\n"
            "- Review the policy guidance above for eligibility and approval thresholds.\n"
            "- Confirm the employee's manager and relocation status before finalizing a device order.\n"
            "- If the request is approved, proceed with the support ticket and monitor status in the helpdesk system."
        )

        state["final_response"] = final_response
        state["status"] = "completed"
        self._add_log(state, "Aggregated worker responses into a unified final response.")
        logger.info("Supervisor final response assembled successfully.")
        return state

    def process(self, user_input: str) -> dict[str, Any]:
        initial_state: SupervisorState = {
            "user_input": user_input,
            "intent": "",
            "hr_context": "",
            "it_context": "",
            "final_response": "",
            "status": "pending",
            "logs": [],
        }
        logger.info("Supervisor starting orchestration for input: %s", user_input)
        state = self.parse_intent(initial_state)
        state = self.dispatch_workers(state)
        result = self.aggregate_response(state)
        logger.info("Supervisor orchestration completed with status=%s", result.get("status"))
        return result


__all__ = ["SupervisorAgent", "SupervisorState"]
