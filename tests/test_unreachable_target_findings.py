"""A target that could not be reached is an environment problem, not a finding about the app."""

from __future__ import annotations

from qa_ai.intelligence.finding_correlator import FindingCorrelator
from qa_ai.orchestration.execution_orchestrator import ExecutionOrchestrator
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.schemas.execution_result_schema import (
    ExecutionResult,
    SuiteResult,
    TestOutcome,
    TestResult,
    is_target_unreachable,
)


def _result(test_id: str, outcome: TestOutcome, error_type: str | None = None) -> TestResult:
    return TestResult(
        test_id=test_id,
        test_title=f"title {test_id}",
        test_type="security",
        outcome=outcome,
        error_message="boom",
        metadata={"error_type": error_type} if error_type else {},
    )


def test_predicate_only_matches_connection_errors() -> None:
    assert is_target_unreachable(TestOutcome.ERROR, {"error_type": "ConnectionError"})
    assert is_target_unreachable("error", {"error_type": "ConnectTimeout"})
    assert not is_target_unreachable(TestOutcome.ERROR, {"error_type": "KeyError"})
    assert not is_target_unreachable(TestOutcome.FAILED, {"error_type": "ConnectionError"})
    assert not is_target_unreachable(TestOutcome.ERROR, None)


def test_orchestrator_reports_unreachable_tests_as_environment_issue(tmp_path) -> None:
    result = ExecutionResult(suites=[SuiteResult(suite_name="security", tests=[
        _result("T1", TestOutcome.ERROR, "ConnectionError"),
        _result("T2", TestOutcome.ERROR, "ConnectionError"),
        _result("T3", TestOutcome.FAILED),
        _result("T4", TestOutcome.ERROR, "KeyError"),
    ])])

    findings = ExecutionOrchestrator(artifact_store=ArtifactStore(base_dir=str(tmp_path)))._generate_findings(result, {})

    assert sorted(f.test_case_id for f in findings.findings) == ["T3", "T4"]
    assert any("2 runtime test(s) could not run" in issue for issue in result.environment_issues)


def test_correlator_ignores_unreachable_tests(tmp_path) -> None:
    execution = ExecutionResult(suites=[SuiteResult(suite_name="security", tests=[
        _result("T1", TestOutcome.ERROR, "ConnectionError"),
        _result("T2", TestOutcome.FAILED),
    ])]).model_dump()

    findings = FindingCorrelator(artifact_store=ArtifactStore(base_dir=str(tmp_path)))._extract_from_execution(execution)

    assert [f.id for f in findings] == ["T2"]
