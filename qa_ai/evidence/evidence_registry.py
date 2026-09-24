"""
evidence_registry.py - Evidence indexing, search, and retrieval.
Provides fast lookup of evidence artifacts by test, type, or keyword.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import json
import logging

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


@dataclass
class EvidenceRecord:
    """Indexed record of an evidence artifact."""
    evidence_id: str
    evidence_type: str
    filename: str
    path: str
    test_id: Optional[str] = None
    test_title: Optional[str] = None
    description: str = ""
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvidenceRegistry:
    """
    Indexes and retrieves evidence artifacts.

    Provides:
    - Fast lookup by evidence_id, test_id, or evidence_type
    - Search by keyword in descriptions
    - Filtering and aggregation
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._records: List[EvidenceRecord] = []

    def load_index(self) -> bool:
        """Load evidence index from artifact store. Returns True if found."""
        index = self.store.load_artifact("evidence_registry")
        if not index or "records" not in index:
            return False

        self._records = []
        for item in index["records"]:
            self._records.append(EvidenceRecord(
                evidence_id=item.get("evidence_id", ""),
                evidence_type=item.get("evidence_type", ""),
                filename=item.get("filename", ""),
                path=item.get("path", ""),
                test_id=item.get("test_id"),
                test_title=item.get("test_title"),
                description=item.get("description", ""),
                timestamp=item.get("timestamp", ""),
            ))
        return True

    def register(
        self,
        evidence_id: str,
        evidence_type: str,
        filename: str,
        path: str,
        test_id: Optional[str] = None,
        test_title: Optional[str] = None,
        description: str = "",
        timestamp: str = "",
    ) -> EvidenceRecord:
        """Register a new evidence item in the index."""
        record = EvidenceRecord(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            filename=filename,
            path=path,
            test_id=test_id,
            test_title=test_title,
            description=description,
            timestamp=timestamp,
        )
        self._records.append(record)
        return record

    def get_by_id(self, evidence_id: str) -> Optional[EvidenceRecord]:
        """Look up evidence by its ID."""
        for r in self._records:
            if r.evidence_id == evidence_id:
                return r
        return None

    def get_by_test(self, test_id: str) -> List[EvidenceRecord]:
        """Get all evidence for a specific test case."""
        return [r for r in self._records if r.test_id == test_id]

    def get_by_type(self, evidence_type: str) -> List[EvidenceRecord]:
        """Get all evidence of a specific type."""
        return [r for r in self._records if r.evidence_type == evidence_type]

    def search(self, query: str) -> List[EvidenceRecord]:
        """Search evidence by keyword in description or test title."""
        query_lower = query.lower()
        return [
            r for r in self._records
            if query_lower in r.description.lower()
            or (r.test_title and query_lower in r.test_title.lower())
        ]

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all indexed evidence."""
        by_type: Dict[str, int] = {}
        by_test: Dict[str, int] = {}
        for r in self._records:
            by_type[r.evidence_type] = by_type.get(r.evidence_type, 0) + 1
            if r.test_id:
                by_test[r.test_id] = by_test.get(r.test_id, 0) + 1

        return {
            "total": len(self._records),
            "by_type": by_type,
            "by_test": by_test,
        }

    def all(self) -> List[EvidenceRecord]:
        """Return all indexed records."""
        return list(self._records)

    def save(self) -> None:
        """Persist the registry as an artifact."""
        data = {
            "total": len(self._records),
            "records": [
                {
                    "evidence_id": r.evidence_id,
                    "evidence_type": r.evidence_type,
                    "filename": r.filename,
                    "path": r.path,
                    "test_id": r.test_id,
                    "test_title": r.test_title,
                    "description": r.description,
                    "timestamp": r.timestamp,
                }
                for r in self._records
            ],
        }
        self.store.save_artifact("evidence_registry", data, agent="EvidenceRegistry")
