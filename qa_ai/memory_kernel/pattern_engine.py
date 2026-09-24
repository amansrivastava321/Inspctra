"""
pattern_engine.py - Extract, merge, and detect failure patterns.

Pattern types: failure_cluster, flaky_test, timing_regression,
connector_gap, data_shape, api_error, ui_regression,
auth_failure, capability_gap.

No hardcoded app names. No raw evidence stored. No raw prompts.
Store schema: pattern_id, scope_id, pattern_type, canonical_template,
parameters, frequency, confidence, impact_score, first_seen, last_seen,
related_findings, related_fixes, active.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from qa_ai.memory_kernel.memory_privacy import redact_json, redact_text
from qa_ai.memory_kernel.fingerprint_engine import semantic_hash

logger = logging.getLogger(__name__)

PATTERN_TYPES = frozenset({
    "failure_cluster",
    "flaky_test",
    "timing_regression",
    "connector_gap",
    "data_shape",
    "api_error",
    "ui_regression",
    "auth_failure",
    "capability_gap",
    "generic",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_pattern_type(pt: str) -> str:
    pt = pt.lower().strip()
    return pt if pt in PATTERN_TYPES else "generic"


# ── Extraction from run delta ───────────────────────────────────────────────────

def extract_patterns_from_delta(
    delta: Dict[str, Any],
    scope_id: str,
    run_id: str,
    severity: str = "medium",
) -> List[Dict[str, Any]]:
    """
    Extract pattern candidates from a run delta dict (from delta_engine).
    Returns list of raw pattern dicts ready for merge_pattern().
    """
    patterns: List[Dict[str, Any]] = []
    now = _now_iso()

    new_failures = delta.get("new_failures", [])
    if new_failures:
        template = f"failure_cluster:{semantic_hash(' '.join(sorted(new_failures[:20])))}"
        patterns.append(_make_pattern(
            scope_id=scope_id,
            run_id=run_id,
            pattern_type="failure_cluster",
            canonical_template=template,
            title=f"New failures: {len(new_failures)} step(s)",
            description=redact_text(f"New failures: {new_failures[:10]}"),
            confidence=0.7,
            severity=severity,
            now=now,
        ))

    # Timing regressions
    timing = delta.get("timing_deltas", {})
    for reg in timing.get("regressions", []):
        key = str(reg.get("key", ""))
        template = f"timing_regression:{semantic_hash(key)}"
        patterns.append(_make_pattern(
            scope_id=scope_id,
            run_id=run_id,
            pattern_type="timing_regression",
            canonical_template=template,
            title=f"Timing regression: {key} ({reg.get('pct', 0):.0f}% slower)",
            description=f"Step {key!r} regressed {reg.get('pct', 0):.1f}% ({reg.get('baseline_ms', 0):.0f}ms → {reg.get('current_ms', 0):.0f}ms)",
            confidence=0.8,
            severity="low" if abs(float(reg.get("pct", 0))) < 50 else severity,
            now=now,
        ))

    # Connector gaps
    for change in delta.get("connector_deltas", []):
        if change.get("new_gaps"):
            cid = str(change.get("connector_id", ""))
            template = f"connector_gap:{semantic_hash(cid + str(sorted(change['new_gaps'])))}"
            patterns.append(_make_pattern(
                scope_id=scope_id,
                run_id=run_id,
                pattern_type="connector_gap",
                canonical_template=template,
                title=f"Connector gap: {cid}",
                description=f"New capability gaps: {change['new_gaps'][:5]}",
                confidence=0.9,
                severity=severity,
                now=now,
            ))

    # Verdict changed to fail
    if delta.get("verdict_change") and str(delta.get("verdict_change", "")).lower() == "fail":
        template = f"verdict_fail:{scope_id}"
        patterns.append(_make_pattern(
            scope_id=scope_id,
            run_id=run_id,
            pattern_type="failure_cluster",
            canonical_template=template,
            title="Run verdict changed to fail",
            description="Run verdict regressed to fail from previous pass",
            confidence=0.85,
            severity=severity,
            now=now,
        ))

    return patterns


def _make_pattern(
    scope_id: str,
    run_id: str,
    pattern_type: str,
    canonical_template: str,
    title: str,
    description: str,
    confidence: float,
    severity: str,
    now: str,
) -> Dict[str, Any]:
    return {
        "pattern_type": _normalize_pattern_type(pattern_type),
        "scope_id": scope_id,
        "canonical_template": canonical_template,
        "parameters": {
            "title": title[:200],
            "description": redact_text(description[:400]),
            "severity": severity,
            "run_ids": [run_id],
        },
        "frequency": 1,
        "confidence": round(confidence, 4),
        "impact_score": 0.5,
        "first_seen": now,
        "last_seen": now,
        "active": True,
    }


def extract_patterns_from_findings(
    findings: List[Dict[str, Any]],
    scope_id: str,
    min_occurrences: int = 2,
) -> List[Dict[str, Any]]:
    """Cluster findings by failure_type/canonical_failure_hash."""
    patterns: List[Dict[str, Any]] = []
    now = _now_iso()

    category_groups: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        cat = str(f.get("failure_type", f.get("canonical_failure_hash", "unknown")))
        category_groups.setdefault(cat, []).append(f)

    for cat, group in category_groups.items():
        if len(group) < min_occurrences:
            continue
        run_ids = list({str(f.get("run_id", "")) for f in group if f.get("run_id")})[:20]
        severity_counts = Counter(str(f.get("severity", "medium")).lower() for f in group)
        top_severity = severity_counts.most_common(1)[0][0]
        template = f"finding_cluster:{semantic_hash(cat + scope_id)}"
        patterns.append({
            "pattern_type": "failure_cluster",
            "scope_id": scope_id,
            "canonical_template": template,
            "parameters": {
                "title": f"Repeated finding: {cat} ({len(group)}x)",
                "description": redact_text(f"Category {cat!r} appeared {len(group)} times"),
                "severity": top_severity,
                "run_ids": run_ids,
            },
            "frequency": len(group),
            "confidence": round(min(0.95, 0.5 + 0.05 * len(group)), 4),
            "impact_score": 0.5,
            "first_seen": now,
            "last_seen": now,
            "active": True,
        })

    return patterns


# ── Flaky test detection ────────────────────────────────────────────────────────

def detect_flaky_patterns(
    run_verdicts: List[Tuple[str, str]],
    scope_id: str,
    min_flips: int = 2,
) -> List[Dict[str, Any]]:
    """
    Detect flaky steps from [(step_id, verdict)] across multiple runs.
    """
    step_history: Dict[str, List[str]] = {}
    for step_id, verdict in run_verdicts:
        step_history.setdefault(step_id, []).append(verdict.lower())

    patterns: List[Dict[str, Any]] = []
    now = _now_iso()

    for step_id, verdicts in step_history.items():
        flips = sum(1 for i in range(1, len(verdicts)) if verdicts[i] != verdicts[i - 1])
        if flips >= min_flips:
            template = f"flaky:{semantic_hash(step_id + scope_id)}"
            patterns.append({
                "pattern_type": "flaky_test",
                "scope_id": scope_id,
                "canonical_template": template,
                "parameters": {
                    "title": f"Flaky step: {step_id} ({flips} verdict flips)",
                    "description": f"Step {step_id!r} flipped verdict {flips} times in {len(verdicts)} runs",
                    "severity": "medium",
                    "run_ids": [],
                },
                "frequency": flips,
                "confidence": round(min(0.95, 0.5 + 0.05 * flips), 4),
                "impact_score": 0.5,
                "first_seen": now,
                "last_seen": now,
                "active": True,
            })

    return patterns


# ── Store integration ───────────────────────────────────────────────────────────

def merge_pattern(
    store,
    pattern: Dict[str, Any],
) -> str:
    """
    Upsert pattern: if canonical_template exists in scope, increment frequency.
    Returns pattern_id.
    """
    existing = store.get_pattern_by_template(
        canonical_template=pattern["canonical_template"],
        scope_id=pattern["scope_id"],
    )
    if existing:
        store.update_pattern(
            pattern_id=existing["pattern_id"],
            frequency_delta=int(pattern.get("frequency", 1)),
            impact_score=min(0.99, float(existing.get("impact_score", 0.5)) + 0.02),
        )
        return existing["pattern_id"]
    else:
        safe = redact_json(pattern)
        pattern_id = str(uuid.uuid4())
        now = _now_iso()
        store.store_pattern({
            "pattern_id": pattern_id,
            "scope_id": safe["scope_id"],
            "pattern_type": _normalize_pattern_type(safe.get("pattern_type", "generic")),
            "canonical_template": safe["canonical_template"],
            "parameters": safe.get("parameters", {}),
            "frequency": int(safe.get("frequency", 1)),
            "confidence": float(safe.get("confidence", 0.5)),
            "impact_score": float(safe.get("impact_score", 0.5)),
            "first_seen": safe.get("first_seen") or now,
            "last_seen": safe.get("last_seen") or now,
            "related_findings": [],
            "related_fixes": [],
            "active": True,
        })
        return pattern_id


def ingest_delta_patterns(
    store,
    scope_id: str,
    run_id: str,
    delta: Dict[str, Any],
    severity: str = "medium",
) -> List[str]:
    """Extract patterns from delta and merge into store. Returns list of pattern_ids."""
    candidates = extract_patterns_from_delta(delta, scope_id, run_id, severity)
    return [merge_pattern(store, p) for p in candidates]


def query_patterns(
    store,
    scope_id: str,
    pattern_type: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Query patterns for scope, optionally filtered."""
    patterns = store.query_recent_patterns(scope_id=scope_id, limit=limit)
    if pattern_type:
        patterns = [p for p in patterns if p.get("pattern_type") == pattern_type]
    if min_confidence > 0:
        patterns = [p for p in patterns if float(p.get("confidence", 0)) >= min_confidence]
    return patterns
