"""
memory_kernel - Universal Delta-Based Project Intelligence Memory Kernel.

Reusable across Inspectra, Anvil, Corpus, Nexus, FlowBook, Videomation.

No app-specific logic. No hardcoded project assumptions.
No cloud calls. No raw secrets stored. No raw prompts stored by default.
"""
from __future__ import annotations

from qa_ai.memory_kernel.memory_models import (
    ProjectMemoryScope,
    GoldenBaseline,
    RunDelta,
    EvidenceFingerprint,
    CompactSummary,
    FindingMemory,
    FixMemory,
    PatternMemory,
    ReasoningTrajectory,
    MemoryEmbedding,
    RetentionDecision,
    MemoryStats,
)
from qa_ai.memory_kernel.memory_store import MemoryStore, get_default_store
from qa_ai.memory_kernel.memory_api_service import MemoryAPIService

__all__ = [
    "ProjectMemoryScope",
    "GoldenBaseline",
    "RunDelta",
    "EvidenceFingerprint",
    "CompactSummary",
    "FindingMemory",
    "FixMemory",
    "PatternMemory",
    "ReasoningTrajectory",
    "MemoryEmbedding",
    "RetentionDecision",
    "MemoryStats",
    "MemoryStore",
    "get_default_store",
    "MemoryAPIService",
]
