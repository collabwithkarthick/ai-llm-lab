"""Offline tests for Agent-Basic tools and ReAct orchestration."""

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import httpx
from ddgs.exceptions import DDGSException

from agent import AgentError, FileReader, ReActAgent, SafeCalculator, ToolError, WebSearch


class FakeModel:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def action(thought: str, name: str, arguments: dict[str, object]) -> str:
    return json.dumps(
        {"thought": thought, "action": name, "action_input": arguments}
    )


class CalculatorTests(unittest.TestCase):
    def test_supports_arithmetic_and_rounding(self) -> None:
        calculator = SafeCalculator()
        self.assertEqual(calculator.calculate("round(62.5 * 0.621371, 1)"), 38.8)
        self.assertEqual(calculator.calculate("(10 + 2) / 3"), 4)

    def test_rejects_code_and_excessive_exponents(self) -> None:
        calculator = SafeCalculator()
        for expression in ("__import__('os').system('whoami')", "2**1000"):
            with self.subTest(expression=expression):
                with self.assertRaises(ToolError):
                    calculator.calculate(expression)


class ReActTests(unittest.TestCase):
    def test_performs_file_search_calculation_and_returns_final_answer(self) -> None:
        model = FakeModel(
            [
                action(
                    "I need the route distance before converting it.",
                    "read_file",
                    {"path": "data/route_notes.txt"},
                ),
                action(
                    "Now I need a miles-per-kilometer conversion factor.",
                    "web_search",
                    {"query": "kilometers to miles conversion factor"},
                ),
                action(
                    "The route is 62.5 km, and the search found 0.621371 miles per km.",
                    "calculate",
                    {"expression": "round(62.5 * 0.621371, 1)"},
                ),
                action(
                    "The calculation gives the rounded distance.",
                    "final",
                    {"answer": "62.5 km is approximately 38.8 miles."},
                ),
            ]
        )
        tools = {
            "read_file": lambda arguments: "The route is 62.5 kilometers.",
            "web_search": lambda arguments: [
                {"title": "Conversion", "snippet": "1 km = 0.621371 miles"}
            ],
            "calculate": lambda arguments: 38.8,
        }
        output = StringIO()
        with redirect_stdout(output):
            answer = ReActAgent(model, tools, sleep=lambda _: None).run(
                "Convert the route from kilometers to miles."
            )

        self.assertEqual(answer, "62.5 km is approximately 38.8 miles.")
        transcript = output.getvalue()
        self.assertIn("Action: read_file", transcript)
        self.assertIn("Action: web_search", transcript)
        self.assertIn("Action: calculate", transcript)
        self.assertIn("Observation: 38.8", transcript)
        self.assertEqual(len(model.prompts), 4)
        self.assertIn("0.621371 miles", model.prompts[2])

    def test_retries_transient_model_errors(self) -> None:
        model = FakeModel(
            [
                httpx.TimeoutException("temporary timeout"),
                action("The answer is ready.", "final", {"answer": "Done."}),
            ]
        )
        with redirect_stdout(StringIO()):
            answer = ReActAgent(
                model, {}, max_retries=2, sleep=lambda _: None
            ).run("Finish the task.")
        self.assertEqual(answer, "Done.")
        self.assertEqual(len(model.prompts), 2)

    def test_stops_after_the_step_limit(self) -> None:
        model = FakeModel(
            [action("Search for a result.", "web_search", {"query": "example"})]
        )
        with self.assertRaisesRegex(AgentError, "within 1 steps"):
            with redirect_stdout(StringIO()):
                ReActAgent(
                    model,
                    {"web_search": lambda _: []},
                    max_steps=1,
                    sleep=lambda _: None,
                ).run("Find an example.")


class ToolTests(unittest.TestCase):
    def test_file_reader_only_reads_from_data_directory(self) -> None:
        reader = FileReader()
        self.assertIn("62.5 kilometers", reader.read("data/route_notes.txt"))
        with self.assertRaisesRegex(ToolError, "only be read from the data directory"):
            reader.read("../../ai-llm-lab/RAG-Basic/.env")

    def test_web_search_retries_transient_search_errors(self) -> None:
        with (
            patch("agent.DDGS") as mock_ddgs,
            patch("agent.time.sleep") as mock_sleep,
        ):
            mock_ddgs.return_value.text.side_effect = [
                DDGSException("temporary failure"),
                [{"title": "Conversion", "href": "https://example.com", "body": "1 km"}],
            ]
            results = WebSearch().search("km to miles", max_results=1)

        self.assertEqual(results[0]["title"], "Conversion")
        self.assertEqual(mock_ddgs.return_value.text.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)


if __name__ == "__main__":
    unittest.main()
