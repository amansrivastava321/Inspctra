"""
trajectory_engine.py - Reasoning trajectory lifecycle management.

Store schema: trajectory_id, scope_id, problem_signature, reasoning_steps,
evidence_checked, hypotheses, action_taken, outcome, reusable_for,
success_count, failure_count, utility_score.

Stores: problem_signature + action_taken + outcome. NOT raw chain-of-thought.
No model internals. No raw prompts. No PII.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from qa_ai.memory_kernel.memory_privacy import redact_json, redact_text

logger = logging.getLogger(__name__)

_STRIP_TAGS = ["<thinking>", "</thinking>", "<thought>", "</thought>",
               "<scratchpad>", "</scratchpad>"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_thinking_tags(text: str) -> str:
    for tag in _STRIP_TAGS:
        text = text.replace(tag, "")
    return text.strip()


def _safe_text(text: str, max_chars: int = 500) -> str:
    text = _strip_thinking_tags(text)
    return redact_text(text[:max_chars])


def create_trajectory(
    store,
    scope_id: str,
    run_id: str,
    problem_signature: str,
    action_taken: str,
    outcome: str,
    reasoning_steps: Optional[List[str]] = None,
    evidence_checked: Optional[List[str]] = None,
    hypotheses: Optional[List[str]] = None,
    reusable_for: Optional[List[str]] = None,
    utility_score: float = 0.5,
    trajectory_id: Optional[str] = None,
) -> Optional[str]:
    """
    Create a new reasoning trajectory.

    problem_signature: compact fingerprint of the problem (not raw prompt).
    action_taken: what was done (not raw prompt).
    outcome: result — NOT raw chain-of-thought.
    reasoning_steps: list of short safe strings (no raw content).
    Returns trajectory_id or None.
    """
    tid = trajectory_id or str(uuid.uuid4())
    now = _now_iso()

    safe_steps = [_safe_text(s, 200) for s in (reasoning_steps or [])[:20]]
    safe_evidence = [_safe_text(e, 200) for e in (evidence_checked or [])[:20]]
    safe_hypo = [_safe_text(h, 200) for h in (hypotheses or [])[:10]]
    safe_reusable = (reusable_for or [])[:20]

    try:
        store.store_trajectory({
            "trajectory_id": tid,
            "scope_id": scope_id,
            "problem_signature": _safe_text(problem_signature, 300),
            "reasoning_steps": safe_steps,
            "evidence_checked": safe_evidence,
            "hypotheses": safe_hypo,
            "action_taken": _safe_text(action_taken, 300),
            "outcome": _safe_text(outcome, 500),
            "reusable_for": safe_reusable,
            "success_count": 0,
            "failure_count": 0,
            "utility_score": min(1.0, max(0.0, float(utility_score))),
            "created_at": now,
            "updated_at": now,
        })
        return tid
    except Exception as exc:
        logger.warning("create_trajectory error: %s", exc)
        return None


def update_trajectory_outcome(
    store,
    trajectory_id: str,
    outcome: str,
    success: Optional[bool] = None,
    utility_score: Optional[float] = None,
) -> bool:
    """Update trajectory after run completes."""
    return store.update_trajectory(
        trajectory_id=trajectory_id,
        outcome=_safe_text(outcome),
        utility_score=utility_score,
        success_count_delta=1 if success is True else 0,
        failure_count_delta=1 if success is False else 0,
    )


def get_trajectory(store, trajectory_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve single trajectory by ID."""
    return store.get_trajectory(trajectory_id=trajectory_id)


def list_trajectories(
    store,
    scope_id: str,
    limit: int = 50,
    min_utility: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """List trajectories for scope."""
    rows = store.list_trajectories(scope_id=scope_id, limit=limit)
    if min_utility is not None:
        rows = [r for r in rows if float(r.get("utility_score", 0)) >= min_utility]
    return rows


def find_similar_trajectories(
    store,
    scope_id: str,
    problem_signature: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Find trajectories similar to problem_signature.
    Uses semantic hash fallback (no embedding model required).
    """
    from qa_ai.memory_kernel.fingerprint_engine import semantic_hash

    query_hash = semantic_hash(problem_signature)
    all_trajs = store.list_trajectories(scope_id=scope_id, limit=500)

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for t in all_trajs:
        t_hash = semantic_hash(str(t.get("problem_signature", "")))
        sim = _hex_similarity(query_hash, t_hash)
        scored.append((sim, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:top_k]]


def _hex_similarity(a: str, b: str) -> float:
    """Fraction of matching hex chars."""
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return sum(ca == cb for ca, cb in zip(a[:n], b[:n])) / n


def summarize_trajectories(
    trajectories: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate trajectory stats."""
    if not trajectories:
        return {"count": 0}

    success_counts: List[int] = []
    failure_counts: List[int] = []
    utility_scores: List[float] = []

    for t in trajectories:
        success_counts.append(int(t.get("success_count", 0)))
        failure_counts.append(int(t.get("failure_count", 0)))
        utility_scores.append(float(t.get("utility_score", 0)))

    total_runs = sum(success_counts) + sum(failure_counts)
    total_success = sum(success_counts)

    return {
        "count": len(trajectories),
        "total_runs": total_runs,
        "success_rate": round(total_success / total_runs * 100, 1) if total_runs > 0 else 0.0,
        "avg_utility_score": round(sum(utility_scores) / len(utility_scores), 3),
        "max_utility_score": round(max(utility_scores), 3),
    }
