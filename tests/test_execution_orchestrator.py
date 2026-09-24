"""
test_execution_orchestrator.py - Tests for the ExecutionOrchestrator.
Validates runner selection, execution coordination, and finding generation.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from qa_ai.orchestration.execution_orchestrator import ExecutionOrchestrator
from qa_ai.schemas.execution_result_schema import (
    ExecutionResult,
    ExecutionMetadata,
    SuiteResult,
    TestResult,
    TestOutcome,
)
from qa_ai.runtime.execution_context import Platform
from qa_ai.runtime.artifact_store import ArtifactStore


class TestExecutionOrchestratorInit:
    def test_creates_with_artifact_store(self, artifact_store):
        orch = ExecutionOrchestrator(artifact_store)
        assert orch.store is artifact_store
        assert "api_runner" in orch._runners

    def test_register_custom_runner(self, artifact_store):
        orch = ExecutionOrchestrator(artifact_store)

        class CustomRunner:
            pass

        orch.register_runner("custom", CustomRunner)
        assert "custom" in orch._runners


class TestExecutionOrchestratorExecution:
    @patch("qa_ai.orchestration.execution_orchestrator.APIRunner")
    def test_execute_backend_platform(self, mock_api_runner_cls, artifact_store, sample_test_plan):
        mock_runner = MagicMock()
        mock_api_runner_cls.return_value = mock_runner
        mock_runner.run.return_value = ExecutionResult(
            metadata=ExecutionMetadata(runner="api_runner"),
            total_executed=3,
            passed=2,
            failed=1,
            skipped=0,
            errors=0,
            suites=[
                SuiteResult(
                    suite_name="functional",
                    total=3,
                    passed=2,
                    failed=1,
                    tests=[
                        TestResult(test_id="TEST-0001", outcome=TestOutcome.PASSED),
                        TestResult(test_id="TEST-0002", outcome=TestOutcome.PASSED),
                        TestResult(
                            test_id="TEST-0003",
                            outcome=TestOutcome.FAILED,
                            error_message="Expected 200, got 500",
                        ),
                    ],
                ),
            ],
        )

        orch = ExecutionOrchestrator(artifact_store)
        orch._runners = {"api_runner": mock_api_runner_cls}

        result = orch.execute(
            test_plan=sample_test_plan,
            platform=Platform.BACKEND,
            config={"base_url": "http://test:8000"},
        )

        assert result.total_executed == 3
        assert result.passed == 2
        assert result.failed == 1
        mock_runner.run.assert_called_once_with(sample_test_plan)

    @patch("qa_ai.orchestration.execution_orchestrator.APIRunner")
    def test_generates_findings_from_failures(self, mock_api_runner_cls, artifact_store, sample_test_plan):
        mock_runner = MagicMock()
        mock_api_runner_cls.return_value = mock_runner
        mock_runner.run.return_value = ExecutionResult(
            metadata=ExecutionMetadata(runner="api_runner"),
            total_executed=1,
            passed=0,
            failed=1,
            suites=[
                SuiteResult(
                    suite_name="functional",
                    total=1,
                    failed=1,
                    tests=[
                        TestResult(
                            test_id="TEST-0002",
                            test_title="GET /users returns 200",
                            test_type="functional",
                            outcome=TestOutcome.FAILED,
                            error_message="Expected 200, got 500",
                        ),
                    ],
                ),
            ],
        )

        orch = ExecutionOrchestrator(artifact_store)
        orch._runners = {"api_runner": mock_api_runner_cls}

        result = orch.execute(
            test_plan=sample_test_plan,
            platform=Platform.BACKEND,
        )

        assert result.failed == 1

        # Findings should be saved
        findings = artifact_store.load_artifact("findings")
        assert findings is not None
        assert len(findings["findings"]) >= 1
        assert findings["findings"][0]["title"] == "Test failed: GET /users returns 200"

    def test_execute_no_runners(self, artifact_store, sample_test_plan):
        orch = ExecutionOrchestrator(artifact_store)
        orch._runners = {}

        result = orch.execute(
            test_plan=sample_test_plan,
            platform=Platform.BACKEND,
        )

        assert result.total_executed == 0

    def test_saves_execution_results_artifact(self, artifact_store, sample_test_plan):
        mock_runner_cls = MagicMock()
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run.return_value = ExecutionResult(
            metadata=ExecutionMetadata(runner="api_runner"),
            total_executed=1,
            passed=1,
        )

        orch = ExecutionOrchestrator(artifact_store)
        orch._runners = {"api_runner": mock_runner_cls}

        orch.execute(test_plan=sample_test_plan, platform=Platform.BACKEND)

        saved = artifact_store.load_artifact("execution_results")
        assert saved is not None


class TestFindingGeneration:
    def test_infer_severity(self, artifact_store):
        orch = ExecutionOrchestrator(artifact_store)

        assert orch._infer_severity(
            {"priority": "P0", "risk": "critical"},
            MagicMock(),
        ).value == "critical"

        assert orch._infer_severity(
            {"priority": "P1", "risk": "medium"},
            MagicMock(),
        ).value == "high"

        assert orch._infer_severity(
            {"priority": "P2", "risk": "low"},
            MagicMock(),
        ).value == "medium"

    def test_infer_category(self, artifact_store):
        orch = ExecutionOrchestrator(artifact_store)

        assert orch._infer_category({"type": "security"}).value == "security"
        assert orch._infer_category({"type": "performance"}).value == "performance"
        assert orch._infer_category({"type": "functional"}).value == "bug"
        assert orch._infer_category({"type": "regression"}).value == "regression"


class TestRunnerSelection:
    def test_select_backend_runners(self, artifact_store):
        orch = ExecutionOrchestrator(artifact_store)
        runners = orch._select_runners(Platform.BACKEND, {"base_url": "http://test"})
        assert len(runners) >= 1
        assert runners[0][0] == "api_runner"

    def test_select_web_runners(self, artifact_store):
        orch = ExecutionOrchestrator(artifact_store)
        runners = orch._select_runners(Platform.WEB, {"base_url": "http://test"})
        # Should have at least one runner
        assert len(runners) >= 1

    def test_select_empty_for_unknown(self, artifact_store):
        orch = ExecutionOrchestrator(artifact_store)
        orch._runners = {}
        runners = orch._select_runners(Platform.WEB, {})
        assert len(runners) == 0
