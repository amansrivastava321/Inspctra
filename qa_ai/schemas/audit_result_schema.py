"""
audit_result_schema.py - Pydantic models for audit results.
Defines the contracts for api_audit_results.json, database_audit_results.json,
and sync_audit_results.json produced by audit agents.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class AuditCheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class AuditSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AuditCheck(BaseModel):
    """A single audit check result."""

    check_id: str = ""
    title: str = ""
    description: str = ""
    status: AuditCheckStatus = AuditCheckStatus.SKIPPED
    severity: AuditSeverity = AuditSeverity.MEDIUM
    category: str = ""
    target: str = ""
    expected: str = ""
    actual: str = ""
    blocked_reason: Optional[str] = None
    recommendation: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditResultMetadata(BaseModel):
    audit_type: str = ""
    app_name: str = ""
    run_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    generated_by: str = ""


class AuditResult(BaseModel):
    """Complete result of an audit run."""

    metadata: AuditResultMetadata = Field(default_factory=AuditResultMetadata)
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    blocked: int = 0
    skipped: int = 0
    checks: List[AuditCheck] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        executed = self.total_checks - self.blocked - self.skipped
        if executed == 0:
            return 0.0
        return self.passed / executed

    @property
    def has_failures(self) -> bool:
        return self.failed > 0

    @property
    def critical_findings(self) -> List[AuditCheck]:
        return [
            c for c in self.checks
            if c.status == AuditCheckStatus.FAILED
            and c.severity == AuditSeverity.CRITICAL
        ]

    @property
    def high_findings(self) -> List[AuditCheck]:
        return [
            c for c in self.checks
            if c.status == AuditCheckStatus.FAILED
            and c.severity == AuditSeverity.HIGH
        ]
