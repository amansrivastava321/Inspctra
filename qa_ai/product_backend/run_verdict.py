"""Deterministic run verdict derived from persisted step results.

No LLM and no network: the verdict is a pure function of step statuses, so the
live run record and the generated report can never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True)
class StepCounts:
    total: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    dry_run: int


def count_steps(step_results: Optional[Iterable[Dict[str, Any]]]) -> StepCounts:
    counts: Dict[str, int] = {}
    total = 0
    for result in step_results or []:
        total += 1
        status = str(result.get("status", "other"))
        counts[status] = counts.get(status, 0) + 1
    return StepCounts(
        total=total,
        passed=counts.get("passed", 0),
        failed=counts.get("failed", 0) + counts.get("error", 0) + counts.get("inconclusive", 0),
        blocked=counts.get("blocked", 0),
        skipped=counts.get("skipped", 0),
        dry_run=counts.get("dry_run_only", 0),
    )


def derive_verdict(counts: StepCounts) -> str:
    """Honest verdict for a set of step results (``pending`` when there are none)."""
    if counts.total == 0:
        return "pending"
    if counts.dry_run == counts.total:
        # Every step ran in dry-run mode: completed, but no real evidence collected.
        return "dry_run"
    if counts.failed > 0 or counts.blocked > 0:
        return "fail"
    if counts.passed + counts.skipped == counts.total:
        return "pass"
    return "unclear"


def verdict_for_run(row: Dict[str, Any]) -> Optional[str]:
    """Verdict to show on a run record, or ``None`` while the run is not finished."""
    status = row.get("status")
    if status not in TERMINAL_RUN_STATUSES:
        return None
    counts = count_steps(row.get("step_results"))
    if counts.total == 0:
        # A run that died before producing any step result still failed.
        return "fail" if status == "failed" else None
    return derive_verdict(counts)
