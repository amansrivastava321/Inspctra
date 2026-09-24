"""
runtime_schema.py - Strict contracts for runtime and replay artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field, model_validator

from qa_ai.schemas.reporting_schema import ArtifactContract


class ExecutionTraceArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "execution_trace"

    events: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _legacy_trace_aliases(cls, raw: Any) -> Dict[str, Any]:
        data = raw if isinstance(raw, dict) else {}
        if "events" not in data and isinstance(data.get("trace"), list):
            data["events"] = data["trace"]
        return data


class NetworkTraceArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "network_trace"

    entries: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ReplayAnalysisArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "replay_analysis"

    comparison: Dict[str, Any] = Field(default_factory=dict)
    regression_detected: bool = False
