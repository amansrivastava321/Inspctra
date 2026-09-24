"""
evidence_collector.py - Automated evidence capture during test runs.
Collects screenshots, API responses, logs, and console output.
All evidence is artifact-backed via the ArtifactStore.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import json
import logging
import traceback

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


@dataclass
class EvidenceItem:
    """A single piece of evidence captured during a test run."""
    evidence_id: str
    evidence_type: str          # "api_response", "screenshot", "log", "console", "trace"
    filename: str
    test_id: Optional[str] = None
    test_title: Optional[str] = None
    description: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None


class EvidenceCollector:
    """
    Captures and stores evidence during test execution.

    Evidence types:
    - api_response: Full HTTP request/response pairs
    - screenshot: Browser screenshots (PNG)
    - log: Test execution logs
    - console: Browser console output
    - network: Network traffic traces
    - error: Error details with stack traces

    All evidence is stored via ArtifactStore and indexed by the EvidenceRegistry.
    """

    def __init__(self, artifact_store: ArtifactStore, run_id: str = ""):
        self.store = artifact_store
        self.run_id = run_id
        self._items: List[EvidenceItem] = []
        self._counter = 0

    def capture_api_response(
        self,
        test_id: str,
        test_title: str,
        method: str,
        url: str,
        request_headers: Optional[Dict] = None,
        request_body: Optional[Any] = None,
        response_status: int = 0,
        response_headers: Optional[Dict] = None,
        response_body: Optional[Any] = None,
        duration_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> EvidenceItem:
        """Capture a full API request/response as evidence."""
        self._counter += 1
        evidence_id = f"ev-{self.run_id}-{self._counter:04d}"

        data = {
            "evidence_id": evidence_id,
            "test_id": test_id,
            "test_title": test_title,
            "request": {
                "method": method,
                "url": url,
                "headers": request_headers or {},
                "body": request_body,
            },
            "response": {
                "status": response_status,
                "headers": response_headers or {},
                "body": response_body,
            },
            "duration_ms": duration_ms,
            "error": error,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        filename = f"{test_id}_{method}_{url.replace('/', '_').replace(':', '')}.json"
        self.store.save_evidence_json("api_responses", filename, data)

        item = EvidenceItem(
            evidence_id=evidence_id,
            evidence_type="api_response",
            filename=filename,
            test_id=test_id,
            test_title=test_title,
            description=f"{method} {url} -> {response_status}",
            path=f"evidence/api_responses/{filename}",
            metadata={"status": response_status, "duration_ms": duration_ms},
        )
        self._items.append(item)
        return item

    def capture_screenshot(
        self,
        test_id: str,
        test_title: str,
        image_bytes: bytes,
        description: str = "",
    ) -> EvidenceItem:
        """Capture a browser screenshot as evidence."""
        self._counter += 1
        evidence_id = f"ev-{self.run_id}-{self._counter:04d}"

        filename = f"{test_id}_{self._counter:04d}.png"
        self.store.save_evidence("screenshots", filename, image_bytes)

        item = EvidenceItem(
            evidence_id=evidence_id,
            evidence_type="screenshot",
            filename=filename,
            test_id=test_id,
            test_title=test_title,
            description=description or f"Screenshot for {test_id}",
            path=f"evidence/screenshots/{filename}",
            metadata={"size_bytes": len(image_bytes)},
        )
        self._items.append(item)
        return item

    def capture_log(
        self,
        test_id: str,
        test_title: str,
        log_content: str,
        description: str = "",
    ) -> EvidenceItem:
        """Capture test execution log output."""
        self._counter += 1
        evidence_id = f"ev-{self.run_id}-{self._counter:04d}"

        filename = f"{test_id}_{self._counter:04d}.log"
        self.store.save_evidence("logs", filename, log_content.encode("utf-8"))

        item = EvidenceItem(
            evidence_id=evidence_id,
            evidence_type="log",
            filename=filename,
            test_id=test_id,
            test_title=test_title,
            description=description or f"Log for {test_id}",
            path=f"evidence/logs/{filename}",
        )
        self._items.append(item)
        return item

    def capture_console(
        self,
        test_id: str,
        messages: List[Dict[str, str]],
    ) -> EvidenceItem:
        """Capture browser console messages."""
        self._counter += 1
        evidence_id = f"ev-{self.run_id}-{self._counter:04d}"

        filename = f"{test_id}_console.json"
        self.store.save_evidence_json("console", filename, {
            "test_id": test_id,
            "messages": messages,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        })

        item = EvidenceItem(
            evidence_id=evidence_id,
            evidence_type="console",
            filename=filename,
            test_id=test_id,
            description=f"{len(messages)} console messages for {test_id}",
            path=f"evidence/console/{filename}",
            metadata={"message_count": len(messages)},
        )
        self._items.append(item)
        return item

    def capture_error(
        self,
        test_id: str,
        test_title: str,
        error: Exception,
        context: str = "",
    ) -> EvidenceItem:
        """Capture error details with stack trace."""
        self._counter += 1
        evidence_id = f"ev-{self.run_id}-{self._counter:04d}"

        data = {
            "test_id": test_id,
            "test_title": test_title,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": traceback.format_exc(),
            "context": context,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        filename = f"{test_id}_error.json"
        self.store.save_evidence_json("errors", filename, data)

        item = EvidenceItem(
            evidence_id=evidence_id,
            evidence_type="error",
            filename=filename,
            test_id=test_id,
            test_title=test_title,
            description=f"{type(error).__name__}: {str(error)[:100]}",
            path=f"evidence/errors/{filename}",
        )
        self._items.append(item)
        return item

    def get_all(self) -> List[EvidenceItem]:
        """Return all captured evidence items."""
        return list(self._items)

    def get_for_test(self, test_id: str) -> List[EvidenceItem]:
        """Return evidence items for a specific test."""
        return [e for e in self._items if e.test_id == test_id]

    def save_index(self) -> None:
        """Save the evidence index as an artifact."""
        index = {
            "run_id": self.run_id,
            "total_items": len(self._items),
            "items": [
                {
                    "evidence_id": e.evidence_id,
                    "evidence_type": e.evidence_type,
                    "filename": e.filename,
                    "test_id": e.test_id,
                    "test_title": e.test_title,
                    "description": e.description,
                    "path": e.path,
                    "timestamp": e.timestamp,
                }
                for e in self._items
            ],
            "by_type": self._count_by_type(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.save_artifact("evidence_index", index, agent="EvidenceCollector")

    def _count_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in self._items:
            counts[item.evidence_type] = counts.get(item.evidence_type, 0) + 1
        return counts
