"""
test_schemas.py - Tests for Pydantic schema models.
Validates that schemas parse correctly, serialize/deserialize, and enforce contracts.
"""

import pytest
from pydantic import ValidationError

from qa_ai.schemas.app_map_schema import (
    AppMap,
    StackInfo,
    StackCapabilities,
    APIEndpoint,
    APIRisk,
    Screen,
    CriticalFlow,
    SecuritySurfaces,
    Testability,
)
from qa_ai.schemas.test_plan_schema import (
    TestPlan,
    TestCase,
    TestType,
    Priority,
    RiskLevel,
    TestPlanSummary,
    TestSuites,
)
from qa_ai.schemas.finding_schema import (
    Finding,
    FindingSet,
    FindingSeverity,
    FindingCategory,
    FindingStatus,
    EvidenceRef,
)
from qa_ai.schemas.execution_result_schema import (
    ExecutionResult,
    TestResult,
    SuiteResult,
    TestOutcome,
    ExecutionMetadata,
)


# ─── App Map Schema Tests ─────────────────────────────


class TestStackCapabilities:
    def test_defaults(self):
        cap = StackCapabilities()
        assert cap.has_auth is False
        assert cap.has_api is False
        assert cap.has_database is False

    def test_with_values(self):
        cap = StackCapabilities(has_auth=True, has_payments=True)
        assert cap.has_auth is True
        assert cap.has_payments is True


class TestStackInfo:
    def test_defaults(self):
        stack = StackInfo()
        assert stack.framework == "unknown"
        assert stack.language == "unknown"
        assert stack.confidence == 0.0

    def test_with_capabilities(self):
        stack = StackInfo(
            framework="fastapi",
            language="python",
            capabilities=StackCapabilities(has_auth=True),
        )
        assert stack.framework == "fastapi"
        assert stack.capabilities.has_auth is True


class TestAPIEndpoint:
    def test_minimal(self):
        ep = APIEndpoint(path="/users")
        assert ep.path == "/users"
        assert ep.method is None
        assert ep.risk is None

    def test_with_risk(self):
        ep = APIEndpoint(
            method="POST",
            path="/users",
            risk=APIRisk(risk_level="high", mutates_data=True),
        )
        assert ep.risk.risk_level == "high"
        assert ep.risk.mutates_data is True


class TestScreen:
    def test_defaults(self):
        s = Screen()
        assert s.name is None
        assert s.auth_required is None

    def test_with_values(self):
        s = Screen(name="Home", path="/", auth_required=False)
        assert s.name == "Home"
        assert s.auth_required is False


class TestAppMap:
    def test_empty(self):
        am = AppMap()
        assert am.metadata.app_name == ""
        assert am.screens == []
        assert am.api_endpoints == []

    def test_from_dict(self, sample_app_map):
        am = AppMap(**sample_app_map)
        assert am.metadata.app_name == "test-app"
        assert len(am.screens) == 2
        assert len(am.api_endpoints) == 2
        assert am.stack.framework == "fastapi"
        assert am.stack.capabilities.has_auth is True

    def test_round_trip(self, sample_app_map):
        am = AppMap(**sample_app_map)
        d = am.model_dump()
        am2 = AppMap(**d)
        assert am.metadata.app_name == am2.metadata.app_name
        assert len(am.screens) == len(am2.screens)

    def test_json_round_trip(self, sample_app_map):
        am = AppMap(**sample_app_map)
        j = am.model_dump_json()
        am2 = AppMap.model_validate_json(j)
        assert am.metadata.app_name == am2.metadata.app_name


# ─── Test Plan Schema Tests ───────────────────────────


class TestTestCase:
    def test_defaults(self):
        tc = TestCase()
        assert tc.type == TestType.FUNCTIONAL
        assert tc.priority == Priority.P1
        assert tc.risk == RiskLevel.MEDIUM

    def test_with_values(self):
        tc = TestCase(
            id="TEST-0001",
            title="Login works",
            type=TestType.SMOKE,
            priority=Priority.P0,
            risk=RiskLevel.CRITICAL,
        )
        assert tc.id == "TEST-0001"
        assert tc.type == TestType.SMOKE


class TestTestPlan:
    def test_empty(self):
        tp = TestPlan()
        assert tp.summary.total_tests == 0
        assert tp.all_tests == []

    def test_from_dict(self, sample_test_plan):
        tp = TestPlan(**sample_test_plan)
        assert tp.summary.total_tests == 3
        assert len(tp.all_tests) == 3
        assert tp.metadata.model == "test-model"

    def test_all_tests_property(self, sample_test_plan):
        tp = TestPlan(**sample_test_plan)
        ids = {t.id for t in tp.all_tests}
        assert ids == {"TEST-0001", "TEST-0002", "TEST-0003"}

    def test_round_trip(self, sample_test_plan):
        tp = TestPlan(**sample_test_plan)
        d = tp.model_dump()
        tp2 = TestPlan(**d)
        assert tp.summary.total_tests == tp2.summary.total_tests
        assert len(tp.all_tests) == len(tp2.all_tests)


# ─── Finding Schema Tests ─────────────────────────────


class TestFinding:
    def test_defaults(self):
        f = Finding()
        assert f.severity == FindingSeverity.MEDIUM
        assert f.category == FindingCategory.BUG
        assert f.status == FindingStatus.OPEN

    def test_with_values(self):
        f = Finding(
            id="F-0001",
            title="Auth bypass",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.SECURITY,
            found_by_agent="SecurityAgent",
        )
        assert f.id == "F-0001"
        assert f.severity == FindingSeverity.CRITICAL


class TestFindingSet:
    def test_empty(self):
        fs = FindingSet()
        assert fs.findings == []
        assert fs.critical == []
        assert fs.open_count == 0

    def test_with_findings(self):
        fs = FindingSet(
            findings=[
                Finding(severity=FindingSeverity.CRITICAL, status=FindingStatus.OPEN),
                Finding(severity=FindingSeverity.HIGH, status=FindingStatus.OPEN),
                Finding(severity=FindingSeverity.LOW, status=FindingStatus.FIXED),
            ]
        )
        assert len(fs.critical) == 1
        assert len(fs.high) == 1
        assert fs.open_count == 2


class TestEvidenceRef:
    def test_defaults(self):
        er = EvidenceRef()
        assert er.evidence_type == ""
        assert er.filename == ""


# ─── Execution Result Schema Tests ────────────────────


class TestTestResult:
    def test_defaults(self):
        tr = TestResult()
        assert tr.outcome == TestOutcome.SKIPPED
        assert tr.duration_seconds == 0.0

    def test_with_values(self):
        tr = TestResult(
            test_id="TEST-0001",
            outcome=TestOutcome.PASSED,
            duration_seconds=1.5,
        )
        assert tr.outcome == TestOutcome.PASSED


class TestSuiteResult:
    def test_defaults(self):
        sr = SuiteResult()
        assert sr.total == 0
        assert sr.passed == 0


class TestExecutionResult:
    def test_defaults(self):
        er = ExecutionResult()
        assert er.total_executed == 0
        assert er.pass_rate == 0.0
        assert er.has_failures is False

    def test_pass_rate(self):
        er = ExecutionResult(total_executed=10, passed=7, failed=3)
        assert er.pass_rate == 0.7
        assert er.has_failures is True

    def test_pass_rate_zero(self):
        er = ExecutionResult(total_executed=0)
        assert er.pass_rate == 0.0

    def test_round_trip(self):
        er = ExecutionResult(
            total_executed=5,
            passed=4,
            failed=1,
            suites=[
                SuiteResult(
                    suite_name="smoke",
                    total=5,
                    passed=4,
                    failed=1,
                ),
            ],
        )
        d = er.model_dump()
        er2 = ExecutionResult(**d)
        assert er.total_executed == er2.total_executed
        assert er.pass_rate == er2.pass_rate
