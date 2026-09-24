"""
test_plan_schema.py - Pydantic models for test plans.
Defines the contract for test_plan.json produced by the Test Planner Agent.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class TestType(str, Enum):
    SMOKE = "smoke"
    FUNCTIONAL = "functional"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    NEGATIVE = "negative"
    EDGE_CASE = "edge_case"
    REGRESSION = "regression"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestCase(BaseModel):
    """A single test case within a test plan."""

    id: str = ""
    title: str = ""
    type: TestType = TestType.FUNCTIONAL
    priority: Priority = Priority.P1
    risk: RiskLevel = RiskLevel.MEDIUM
    target: Dict[str, Optional[str]] = Field(default_factory=dict)
    preconditions: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    expected_result: str = ""
    reasoning: str = ""
    tags: List[str] = Field(default_factory=list)


class TestPlanMetadata(BaseModel):
    generated_at: str = ""
    plan_version: str = ""
    generated_by: str = ""
    model: Optional[str] = None


class TestPlanSummary(BaseModel):
    total_tests: int = 0
    by_suite: Dict[str, int] = Field(default_factory=dict)
    by_priority: Dict[str, int] = Field(default_factory=dict)


class TestSuites(BaseModel):
    smoke: List[TestCase] = Field(default_factory=list)
    functional: List[TestCase] = Field(default_factory=list)
    security: List[TestCase] = Field(default_factory=list)
    performance: List[TestCase] = Field(default_factory=list)
    accessibility: List[TestCase] = Field(default_factory=list)
    negative: List[TestCase] = Field(default_factory=list)
    edge_case: List[TestCase] = Field(default_factory=list)
    regression: List[TestCase] = Field(default_factory=list)


class TestPlan(BaseModel):
    """Complete test plan produced by the Test Planner Agent."""

    metadata: TestPlanMetadata = Field(default_factory=TestPlanMetadata)
    summary: TestPlanSummary = Field(default_factory=TestPlanSummary)
    test_suites: TestSuites = Field(default_factory=TestSuites)

    @property
    def all_tests(self) -> List[TestCase]:
        """Flatten all test suites into a single list."""
        result: List[TestCase] = []
        for suite in [
            self.test_suites.smoke,
            self.test_suites.functional,
            self.test_suites.security,
            self.test_suites.performance,
            self.test_suites.accessibility,
            self.test_suites.negative,
            self.test_suites.edge_case,
            self.test_suites.regression,
        ]:
            result.extend(suite)
        return result
