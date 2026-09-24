"""
execution_result_schema.py - Pydantic models for test execution results.
Defines the contract for execution_results.json produced by runners.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class TestOutcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"


class TestResult(BaseModel):
    """Result of executing a single test case."""

    test_id: str = ""
    test_title: str = ""
    test_type: str = ""
    outcome: TestOutcome = TestOutcome.SKIPPED
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None
    log_path: Optional[str] = None
    evidence_paths: List[str] = Field(default_factory=list)
    retry_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SuiteResult(BaseModel):
    """Results for a single test suite."""

    suite_name: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    tests: List[TestResult] = Field(default_factory=list)


class ExecutionMetadata(BaseModel):
    run_id: str = ""
    app_name: str = ""
    platform: str = ""
    environment: str = ""
    runner: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0


class ExecutionResult(BaseModel):
    """Complete result of executing a test plan."""

    metadata: ExecutionMetadata = Field(default_factory=ExecutionMetadata)
    total_executed: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    suites: List[SuiteResult] = Field(default_factory=list)
    environment_issues: List[str] = Field(default_factory=list)
    metadata_extra: Dict[str, Any] = Field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.total_executed == 0:
            return 0.0
        return self.passed / self.total_executed

    @property
    def has_failures(self) -> bool:
        return self.failed > 0 or self.errors > 0
