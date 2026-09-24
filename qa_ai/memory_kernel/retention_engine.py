"""
retention_engine.py - Plan and execute evidence retention/deletion decisions.

Uses utility_scorer to rank evidence.
Never deletes outside artifact_root.
Dry-run mode by default.
No shell. No subprocess. No eval.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qa_ai.memory_kernel.utility_scorer import score_evidence, UtilityWeights

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RetentionAction:
    record_type: str          # fingerprint | summary | finding | pattern | trajectory | delta
    record_id: str
    retention_class: str      # hot | warm | cold | delete_candidate
    utility_score: float
    action: str               # keep | compress | archive | delete
    reason: str


@dataclass
class RetentionPlan:
    total_records: int
    keep: List[RetentionAction] = field(default_factory=list)
    compress: List[RetentionAction] = field(default_factory=list)
    archive: List[RetentionAction] = field(default_factory=list)
    delete: List[RetentionAction] = field(default_factory=list)
    estimated_freed_records: int = 0

    def all_actions(self) -> List[RetentionAction]:
        return self.keep + self.compress + self.archive + self.delete


def _action_for_class(retention_class: str) -> str:
    return {
        "hot": "keep",
        "warm": "keep",
        "cold": "compress",
        "delete_candidate": "delete",
    }.get(retention_class, "keep")


def plan_retention(
    store,
    scope_id: str,
    weights: Optional[UtilityWeights] = None,
    max_delete_per_run: int = 500,
) -> RetentionPlan:
    """
    Score all evidence for a scope, build retention plan.
    Does NOT delete anything. Call execute_retention_plan to apply.
    """
    actions: List[RetentionAction] = []

    # Fingerprints (use store.list_fingerprints)
    rows = store.list_fingerprints(scope_id=scope_id, limit=5000)
    for row in rows:
        result = score_evidence(
            evidence_type=row.get("evidence_type", "unknown"),
            verdict=str(row.get("retention_class", "warm")),
            frequency=1,
            is_duplicate=bool(row.get("duplicate_of")),
            severity="medium",
            weights=weights,
        )
        action_str = _action_for_class(result.retention_class)
        actions.append(RetentionAction(
            record_type="fingerprint",
            record_id=row["fingerprint_id"],
            retention_class=result.retention_class,
            utility_score=result.utility_score,
            action=action_str,
            reason=f"utility={result.utility_score} class={result.retention_class}",
        ))

    # Summaries
    rows = store.query_high_utility_summaries(scope_id=scope_id, min_score=0.0, limit=5000)
    for row in rows:
        result = score_evidence(
            evidence_type=row.get("source_type", "summary"),
            verdict="pass",
            frequency=1,
            severity=row.get("severity", "medium"),
            weights=weights,
        )
        # Override with stored utility score if available
        stored_score = float(row.get("utility_score", result.utility_score / 100))
        score_100 = round(stored_score * 100, 1) if stored_score <= 1.0 else stored_score
        if score_100 >= 70:
            retention_class = "hot"
        elif score_100 >= 40:
            retention_class = "warm"
        elif score_100 >= 15:
            retention_class = "cold"
        else:
            retention_class = "delete_candidate"
        action_str = _action_for_class(retention_class)
        actions.append(RetentionAction(
            record_type="summary",
            record_id=row["summary_id"],
            retention_class=retention_class,
            utility_score=score_100,
            action=action_str,
            reason=f"utility={score_100} class={retention_class}",
        ))

    # Findings
    rows = store.list_findings(scope_id=scope_id, limit=5000)
    for row in rows:
        result = score_evidence(
            evidence_type="finding",
            verdict=row.get("status", "fail"),
            frequency=int(row.get("frequency", 1)),
            used_in_report=True,
            severity=row.get("severity", "medium"),
            weights=weights,
        )
        action_str = _action_for_class(result.retention_class)
        actions.append(RetentionAction(
            record_type="finding",
            record_id=row["finding_id"],
            retention_class=result.retention_class,
            utility_score=result.utility_score,
            action=action_str,
            reason=f"utility={result.utility_score} class={result.retention_class}",
        ))

    # Patterns
    rows = store.query_recent_patterns(scope_id=scope_id, limit=5000)
    for row in rows:
        result = score_evidence(
            evidence_type=row.get("pattern_type", "pattern"),
            verdict="fail" if float(row.get("confidence", float(row.get("impact_score", 0.5)))) > 0.7 else "unclear",
            frequency=int(row.get("frequency", 1)),
            used_in_report=True,
            severity="medium",
            weights=weights,
        )
        action_str = _action_for_class(result.retention_class)
        actions.append(RetentionAction(
            record_type="pattern",
            record_id=row["pattern_id"],
            retention_class=result.retention_class,
            utility_score=result.utility_score,
            action=action_str,
            reason=f"utility={result.utility_score} class={result.retention_class}",
        ))

    # Build plan
    plan = RetentionPlan(total_records=len(actions))
    for a in actions:
        if a.action == "keep":
            plan.keep.append(a)
        elif a.action == "compress":
            plan.compress.append(a)
        elif a.action == "archive":
            plan.archive.append(a)
        else:
            plan.delete.append(a)

    # Cap deletes per run
    if len(plan.delete) > max_delete_per_run:
        plan.delete.sort(key=lambda x: x.utility_score)
        excess = plan.delete[max_delete_per_run:]
        for a in excess:
            a.action = "compress"
            a.reason += " (capped)"
            plan.compress.append(a)
        plan.delete = plan.delete[:max_delete_per_run]

    plan.estimated_freed_records = len(plan.delete)
    return plan


def execute_retention_plan(
    store,
    plan: RetentionPlan,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Apply retention plan. dry_run=True by default.
    Returns execution report.
    """
    executed: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []
    now = _now_iso()

    for action in plan.delete:
        if dry_run:
            skipped.append(f"{action.record_type}:{action.record_id}")
            continue
        try:
            _delete_record(store, action.record_type, action.record_id)
            store.record_retention_decision({
                "decision_id": str(uuid.uuid4()),
                "source_type": action.record_type,
                "source_id": action.record_id,
                "action": "delete",
                "reason": action.reason,
                "utility_score": action.utility_score,
                "before_bytes": 0,
                "after_bytes": 0,
                "executed_at": now,
            })
            executed.append(f"{action.record_type}:{action.record_id}")
        except Exception as exc:
            errors.append(f"{action.record_type}:{action.record_id}: {exc}")
            logger.warning("retention delete error: %s", exc)

    return {
        "dry_run": dry_run,
        "plan_total": plan.total_records,
        "planned_deletes": len(plan.delete),
        "planned_compresses": len(plan.compress),
        "planned_keeps": len(plan.keep),
        "executed_deletes": len(executed),
        "skipped": len(skipped),
        "errors": len(errors),
        "error_list": errors[:20],
        "executed_at": now,
    }


def _delete_record(store, record_type: str, record_id: str) -> None:
    """Delete single record by type. Raises on failure."""
    if record_type == "fingerprint":
        store.delete_fingerprint(record_id)
    elif record_type == "summary":
        store.delete_summary(record_id)
    elif record_type == "finding":
        store.delete_finding(record_id)
    elif record_type == "pattern":
        store.delete_pattern(record_id)
    elif record_type == "trajectory":
        store.delete_trajectory(record_id)
    elif record_type == "delta":
        store.delete_run_delta(record_id)
    else:
        raise ValueError(f"Unknown record_type: {record_type!r}")


def run_retention_cycle(
    store,
    scope_id: str,
    dry_run: bool = True,
    weights: Optional[UtilityWeights] = None,
    max_delete_per_run: int = 500,
) -> Dict[str, Any]:
    """Full retention cycle: plan + execute. dry_run=True by default."""
    plan = plan_retention(
        store=store,
        scope_id=scope_id,
        weights=weights,
        max_delete_per_run=max_delete_per_run,
    )
    result = execute_retention_plan(store=store, plan=plan, dry_run=dry_run)
    result["plan"] = {
        "keep": len(plan.keep),
        "compress": len(plan.compress),
        "archive": len(plan.archive),
        "delete": len(plan.delete),
        "total": plan.total_records,
    }
    return result
