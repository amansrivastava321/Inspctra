"""
finding_schema.py - Pydantic models for QA findings.
Defines the contract for findings.json produced by analysis agents.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    CODE_QUALITY = "code_quality"
    REGRESSION = "regression"
    COMPLIANCE = "compliance"
    USABILITY = "usability"


class FindingStatus(str, Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    FIXED = "fixed"
    WONT_FIX = "wont_fix"
    DUPLICATE = "duplicate"
    FALSE_POSITIVE = "false_positive"


class EvidenceRef(BaseModel):
    """Reference to an evidence artifact supporting this finding."""

    evidence_type: str = ""
    filename: str = ""
    description: str = ""
    path: Optional[str] = None


class Finding(BaseModel):
    """A single QA finding — a bug, issue, or recommendation."""

    id: str = ""
    title: str = ""
    description: str = ""
    severity: FindingSeverity = FindingSeverity.MEDIUM
    category: FindingCategory = FindingCategory.BUG
    status: FindingStatus = FindingStatus.OPEN

    # Location
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    screen: Optional[str] = None
    api_endpoint: Optional[str] = None

    # Reproduction
    steps_to_reproduce: List[str] = Field(default_factory=list)
    expected_behavior: str = ""
    actual_behavior: str = ""

    # Evidence
    evidence: List[EvidenceRef] = Field(default_factory=list)

    # Attribution
    found_by_agent: str = ""
    found_at: str = ""
    test_case_id: Optional[str] = None

    # Remediation
    recommendation: str = ""
    estimated_effort: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    # Context
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FindingSet(BaseModel):
    """Collection of findings produced by one or more analysis agents."""

    findings: List[Finding] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def critical(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == FindingSeverity.CRITICAL]

    @property
    def high(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == FindingSeverity.HIGH]

    @property
    def medium(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == FindingSeverity.MEDIUM]

    @property
    def low(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == FindingSeverity.LOW]

    @property
    def open_count(self) -> int:
        return sum(1 for f in self.findings if f.status == FindingStatus.OPEN)
