"""
test_api_runner.py - Tests for the APIRunner.
Validates API test execution with mocked HTTP responses.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from qa_ai.runners.api_runner import APIRunner
from qa_ai.schemas.execution_result_schema import TestOutcome, ExecutionResult


class TestAPIRunnerInit:
    def test_properties(self):
        runner = APIRunner(config={"base_url": "http://test:8000"})
        assert runner.name == "api_runner"
        assert "backend" in runner.supported_platforms
        assert "web" in runner.supported_platforms

    def test_can_run(self):
        runner = APIRunner()
        assert runner.can_run("backend") is True
        assert runner.can_run("web") is True
        assert runner.can_run("android") is False


class TestAPIRunnerExecution:
    def _make_runner(self, tmp_dir):
        return APIRunner(config={
            "base_url": "http://localhost:8000",
            "artifact_dir": str(tmp_dir / "artifacts"),
            "run_id": "test-run",
        })

    def test_execute_empty_plan(self, tmp_dir):
        runner = self._make_runner(tmp_dir)
        runner.setup()
        try:
            result = runner.execute({"test_suites": {}})
            assert result.total_executed == 0
            assert result.passed == 0
        finally:
            runner.teardown()

    @patch("qa_ai.runners.api_runner.requests.Session")
    def test_execute_functional_test_passes(self, mock_session_cls, tmp_dir):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = [{"id": 1, "name": "Alice"}]
        mock_response.text = '[{"id": 1}]'
        mock_session.request.return_value = mock_response
        mock_session.headers = {}

        runner = self._make_runner(tmp_dir)
        runner._session = mock_session
        runner._evidence = MagicMock()

        test_plan = {
            "test_suites": {
                "functional": [
                    {
                        "id": "TEST-0001",
                        "title": "GET /users returns 200",
                        "type": "functional",
                        "target": {"api": "GET /users"},
                        "steps": ["Call GET /users"],
                        "expected_result": "200 OK",
                    },
                ],
            },
        }

        result = runner.execute(test_plan)

        assert result.total_executed == 1
        assert result.passed == 1
        assert result.failed == 0
        assert result.suites[0].tests[0].outcome == TestOutcome.PASSED

    @patch("qa_ai.runners.api_runner.requests.Session")
    def test_execute_negative_test_passes_on_400(self, mock_session_cls, tmp_dir):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"error": "bad request"}
        mock_response.text = '{"error": "bad request"}'
        mock_session.request.return_value = mock_response
        mock_session.headers = {}

        runner = self._make_runner(tmp_dir)
        runner._session = mock_session
        runner._evidence = MagicMock()

        test_plan = {
            "test_suites": {
                "negative": [
                    {
                        "id": "TEST-0010",
                        "title": "Invalid body: POST /users",
                        "type": "negative",
                        "target": {"api": "POST /users"},
                        "steps": ["Send malformed JSON"],
                        "expected_result": "400 Bad Request",
                    },
                ],
            },
        }

        result = runner.execute(test_plan)
        assert result.passed == 1

    @patch("qa_ai.runners.api_runner.requests.Session")
    def test_execute_skips_non_api_tests(self, mock_session_cls, tmp_dir):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.headers = {}

        runner = self._make_runner(tmp_dir)
        runner._session = mock_session
        runner._evidence = MagicMock()

        test_plan = {
            "test_suites": {
                "edge_case": [
                    {
                        "id": "TEST-0006",
                        "title": "Rapid double-click submit",
                        "type": "edge_case",
                        "steps": ["Click submit rapidly"],
                        "expected_result": "Only one submission",
                    },
                ],
            },
        }

        result = runner.execute(test_plan)
        assert result.skipped == 1
        assert result.suites[0].tests[0].outcome == TestOutcome.SKIPPED

    @patch("qa_ai.runners.api_runner.requests.Session")
    def test_execute_handles_network_error(self, mock_session_cls, tmp_dir):
        import requests as req

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.request.side_effect = req.ConnectionError("Connection refused")
        mock_session.headers = {}

        runner = self._make_runner(tmp_dir)
        runner._session = mock_session
        runner._evidence = MagicMock()

        test_plan = {
            "test_suites": {
                "functional": [
                    {
                        "id": "TEST-0001",
                        "title": "GET /users",
                        "type": "functional",
                        "target": {"api": "GET /users"},
                        "steps": ["Call GET /users"],
                        "expected_result": "200 OK",
                    },
                ],
            },
        }

        result = runner.execute(test_plan)
        assert result.errors == 1
        assert result.suites[0].tests[0].outcome == TestOutcome.ERROR


class TestAPIRunnerHelpers:
    def test_parse_api_target(self):
        runner = APIRunner()
        method, path = runner._parse_api_target("GET /users", "")
        assert method == "GET"
        assert path == "/users"

    def test_parse_api_target_from_title(self):
        runner = APIRunner()
        method, path = runner._parse_api_target("", "API: POST /users/{id}")
        assert method == "POST"

    def test_is_api_test(self):
        runner = APIRunner()
        assert runner._is_api_test("GET /users returns 200", []) is True
        assert runner._is_api_test("Rapid double-click", ["Click submit"]) is False

    def test_infer_expected_status(self):
        runner = APIRunner()
        assert runner._infer_expected_status("200 OK", "functional", "GET") == 200
        assert runner._infer_expected_status("400 Bad Request", "negative", "POST") == 400
        assert runner._infer_expected_status("401 Unauthorized", "security", "GET") == 401
