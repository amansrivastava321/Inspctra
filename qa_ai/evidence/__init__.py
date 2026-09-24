"""
qa_ai/evidence/__init__.py - Evidence package initialization.
"""

from qa_ai.evidence.evidence_collector import EvidenceCollector, EvidenceItem
from qa_ai.evidence.evidence_registry import EvidenceRegistry, EvidenceRecord

__all__ = [
    "EvidenceCollector",
    "EvidenceItem",
    "EvidenceRegistry",
    "EvidenceRecord",
]
