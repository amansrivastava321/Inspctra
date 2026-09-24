"""
model_routing_schema.py - Artifact contracts for model routing telemetry.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class ModelUsageLogArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "model_usage_log"

    entries: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ModelRoutingReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "model_routing_report"

    routing_mode: str = "specialist_cloud_first"
    components: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
