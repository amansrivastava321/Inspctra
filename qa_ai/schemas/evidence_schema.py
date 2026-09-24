"""
evidence_schema.py - Strict contracts for evidence graph artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import BaseModel, Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class EvidenceGraphNode(BaseModel):
    node_id: str = ""
    node_type: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    links: List[str] = Field(default_factory=list)


class EvidenceGraphData(BaseModel):
    nodes: List[EvidenceGraphNode] = Field(default_factory=list)
    edges: List[Dict[str, str]] = Field(default_factory=list)


class EvidenceGraphArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "evidence_graph"

    graph: EvidenceGraphData = Field(default_factory=EvidenceGraphData)
    summary: Dict[str, Any] = Field(default_factory=dict)
