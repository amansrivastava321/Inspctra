"""
function_coverage_tracker.py - Track every reachable UI function through the session.

Produces interactive_function_coverage.json artifact.
Status flow: DISCOVERED → ATTEMPTED → PASSED / FAILED / BLOCKED / SKIPPED / INCONCLUSIVE
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from qa_ai.interactive_runtime.schemas import (
    FunctionCoverageItem,
    FunctionStatus,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class FunctionCoverageTracker:
    """
    Track every discovered UI function and its test outcome.

    Items move through the status lifecycle:
    DISCOVERED → ATTEMPTED → PASSED | FAILED | BLOCKED | SKIPPED | INCONCLUSIVE
    """

    def __init__(self, output_dir: str = "artifacts"):
        self._output_dir = Path(output_dir)
        self._items: Dict[str, FunctionCoverageItem] = {}   # item_id → item
        self._label_index: Dict[str, str] = {}               # "screen::label" → item_id

    # ── registration ──────────────────────────────────────────────────────────

    def discover(self, item: FunctionCoverageItem) -> str:
        """Register a discovered function. Returns item_id."""
        self._items[item.item_id] = item
        self._label_index[self._key(item.screen, item.element_label)] = item.item_id
        return item.item_id

    def discover_many(self, items: List[FunctionCoverageItem]) -> None:
        for item in items:
            self.discover(item)

    # ── status updates ────────────────────────────────────────────────────────

    def mark_attempted(self, item_id: str, action: str = "") -> None:
        item = self._items.get(item_id)
        if item:
            item.status = FunctionStatus.ATTEMPTED
            item.action_attempted = action
            item.tested_at = datetime.now(timezone.utc).isoformat()

    def mark_by_verification(
        self,
        item_id: str,
        verification_status: VerificationStatus,
        actual_result: str = "",
        evidence_links: Optional[List[str]] = None,
        severity: Optional[str] = None,
    ) -> None:
        item = self._items.get(item_id)
        if not item:
            return
        item.actual_result = actual_result
        if evidence_links:
            item.evidence_links.extend(evidence_links)
        if severity:
            item.severity = severity
        item.tested_at = datetime.now(timezone.utc).isoformat()

        item.status = {
            VerificationStatus.PASSED: FunctionStatus.PASSED,
            VerificationStatus.FAILED: FunctionStatus.FAILED,
            VerificationStatus.INCONCLUSIVE: FunctionStatus.INCONCLUSIVE,
            VerificationStatus.BLOCKED: FunctionStatus.BLOCKED,
            VerificationStatus.SKIPPED: FunctionStatus.SKIPPED,
        }.get(verification_status, FunctionStatus.INCONCLUSIVE)

    def mark_blocked(self, item_id: str, reason: str = "") -> None:
        item = self._items.get(item_id)
        if item:
            item.status = FunctionStatus.BLOCKED
            item.notes = reason
            item.tested_at = datetime.now(timezone.utc).isoformat()

    def mark_skipped(self, item_id: str, reason: str = "") -> None:
        item = self._items.get(item_id)
        if item:
            item.status = FunctionStatus.SKIPPED
            item.notes = reason

    # ── lookup ────────────────────────────────────────────────────────────────

    def get(self, item_id: str) -> Optional[FunctionCoverageItem]:
        return self._items.get(item_id)

    def find_by_label(self, screen: str, label: str) -> Optional[FunctionCoverageItem]:
        item_id = self._label_index.get(self._key(screen, label))
        return self._items.get(item_id) if item_id else None

    def all_items(self) -> List[FunctionCoverageItem]:
        return list(self._items.values())

    # ── statistics ────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in self._items.values():
            counts[item.status.value] = counts.get(item.status.value, 0) + 1
        return counts

    @property
    def coverage_pct(self) -> float:
        total = len(self._items)
        if total == 0:
            return 0.0
        tested = sum(
            1 for i in self._items.values()
            if i.status not in (FunctionStatus.DISCOVERED,)
        )
        return tested / total * 100

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self) -> Path:
        """Write interactive_function_coverage.json to output_dir."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / "interactive_function_coverage.json"
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.summary(),
            "coverage_pct": round(self.coverage_pct, 1),
            "total": len(self._items),
            "items": [i.model_dump() for i in self._items.values()],
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("Coverage saved: %s (%d items)", path, len(self._items))
        return path

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _key(screen: str, label: str) -> str:
        return f"{screen}::{label}"
