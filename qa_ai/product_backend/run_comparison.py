"""Read-only pair comparison of persisted observations, never definitions."""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from qa_ai.product_backend import models as m
from qa_ai.product_backend.run_history import _failure_signature
from qa_ai.product_backend.storage import ProductStorage


CONFIG_WARNING = "Execution configuration continuity between these runs cannot be fully verified."
TERMINAL = {"completed", "failed", "cancelled"}
# Deliberately fail closed for sensitive free text. Structured displays are
# omitted rather than recursively exposing unknown historical payload schemas.
SENSITIVE = re.compile(
    r"authorization|cookie|bearer|passw(?:or)?d|api[\s_-]?key|private[\s_-]?key|"
    r"token|secret|credential|-----BEGIN|://[^\s/]+@|\b(?:sk|pk|rk)-[\w-]{12,}|"
    r"\bgh[pousr]_[\w]+|\bAKIA[0-9A-Z]{16}|eyJ[\w-]+\.[\w-]+\.[\w-]+", re.I,
)


class RunComparisonError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float, bool)):
        return "[Structured value omitted]"
    text = str(value)
    return "[REDACTED]" if SENSITIVE.search(text) else text[:2048]


def _provenance(value: Any) -> tuple[m.Provenance, str]:
    try:
        return m.Provenance(value), "stored"
    except (ValueError, TypeError):
        return m.Provenance.UNAVAILABLE, "unavailable"


def _observation(run: dict, evidence: list) -> m.RunComparisonObservation:
    provenance, basis = _provenance(run.get("provenance"))
    if basis == "unavailable" and run.get("provenance") in (None, "") and evidence:
        # Legacy loader would infer REAL from evidence. Disclose basis but never
        # replace the persisted missing value with an execution claim.
        basis = "inferred"
    return m.RunComparisonObservation(
        run_id=run["id"], status=_text(run.get("status")) or "",
        execution_mode=_text(run.get("execution_mode")), provenance=provenance,
        provenance_basis=basis,
        **{key: _text(run.get(key)) for key in ("created_at", "started_at", "completed_at", "error", "retest_of")},
    )


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _chronology(b: dict, c: dict) -> m.RunComparisonChronology:
    for key in ("completed_at", "started_at", "created_at"):
        bt, ct = _timestamp(b.get(key)), _timestamp(c.get(key))
        if bt is not None and ct is not None:
            return m.RunComparisonChronology(
                state="forward" if bt < ct else "reverse" if bt > ct else "same_time",
                basis=key, baseline_time=bt.isoformat(), comparison_time=ct.isoformat(),
            )
    return m.RunComparisonChronology()


def _steps(run: dict, omissions: list[str]) -> list[dict]:
    reason = None
    try:
        raw = json.loads(run.get("step_results") or "null")
        if not isinstance(raw, list) or any(not isinstance(s, dict) for s in raw):
            reason = "invalid_step_results"
        elif len(raw) > 500:
            reason = "step_limit_exceeded"
    except (ValueError, TypeError, RecursionError):
        raw, reason = None, "invalid_step_results"
    if (run.get("result_bytes") or 0) > 2_097_152:
        reason = "result_bytes_limit_exceeded"
    if reason:
        omissions.append(f"{run['id']}:{reason}")
        return []
    return raw


def _identity(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() and len(value) <= 512 else None


def _group(steps: list[dict]) -> tuple[dict, list]:
    groups, missing = defaultdict(list), []
    for s in steps:
        sid = _identity(s.get("step_id"))
        (groups[sid] if sid is not None else missing).append(s)
    return groups, missing


def _outcome(step: dict) -> str:
    status = step.get("status")
    return "passed" if status == "passed" else "failed" if status in ("failed", "error") else "inconclusive"


def _action(s: dict) -> str | None:
    value = s.get("action_type") or s.get("action")
    return value if isinstance(value, str) and value else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) and value >= 0 else None
    except OverflowError:
        return None


def _request_compatible(b: dict, c: dict) -> bool:
    # Current API results omit query/body/header configuration. A bare URL is
    # not the fully resolved request identity; those runs must withhold deltas.
    if not (_action(b) in (m.SUPPORTED_API_ACTIONS - m.SUPPORTED_WEB_ACTIONS)
            and _action(b) == _action(c)
            and all(isinstance(b.get(k), str) and b[k].strip() and b[k] == c.get(k)
                    for k in ("method", "url"))):
        return False
    required = ("headers", "query_params", "body_json")
    if any(k not in s for s in (b, c) for k in required):
        return False
    if any(not isinstance(s[k], dict) for s in (b, c) for k in ("headers", "query_params")):
        return False
    # Equality on an explicit request-field allowlist, not arbitrary metadata
    # diffing. Alternate persisted fields must not contradict each other either.
    keys = (*required, "body", "headers_json", "query_params_json")
    try:
        serialized = [json.dumps({k: s[k] for k in keys if k in s}, sort_keys=True, allow_nan=False) for s in (b, c)]
    except (ValueError, TypeError, RecursionError):
        return False
    if any(re.search(r"redact|omitt|truncat", value, re.I) for value in serialized):
        return False
    return serialized[0] == serialized[1]


def _metrics(b: dict, c: dict) -> list[m.RunComparisonMetric]:
    metrics = []
    for key in ("duration_ms", "response_time_ms", "status_code"):
        bv, cv = _number(b.get(key)), _number(c.get(key))
        reason = "missing_or_invalid_value" if bv is None or cv is None else None
        if key == "status_code":
            bv = bv if bv is not None and bv.is_integer() and 100 <= bv <= 599 else None
            cv = cv if cv is not None and cv.is_integer() and 100 <= cv <= 599 else None
            reason = "missing_or_invalid_value" if bv is None or cv is None else None
        if key == "response_time_ms" and not _request_compatible(b, c):
            reason = "request_identity_unavailable"
        delta = cv - bv if reason is None and key != "status_code" else None
        if delta is not None and not math.isfinite(delta):
            delta, reason = None, "nonfinite_delta"
        metrics.append(m.RunComparisonMetric(key=key, unit="http_status" if key == "status_code" else "ms",
                       baseline_value=bv, comparison_value=cv, delta=delta, reason=reason))
    return metrics


def _signature(sid: str, b: dict, c: dict) -> m.RunComparisonFailureSignature:
    signatures = []
    for s in (b, c):
        if _outcome(s) != "failed":
            return m.RunComparisonFailureSignature(reason="both_failures_required")
        # Guard the effective inputs selected by history_v1, including its
        # truthy error_code fallback. Whitespace must not create empty identity.
        fields = [s.get("error_code") or s.get("code"), s.get("error"), s.get("failure_reason"), s.get("notes")]
        texts = [re.sub(r"\s+", " ", v).strip().casefold() for v in fields if isinstance(v, str)]
        if not any(texts):
            return m.RunComparisonFailureSignature(reason="insufficient_failure_identity")
        if any(len(v) > 512 for v in texts):
            return m.RunComparisonFailureSignature(reason="signature_input_truncated")
        safe = {k: s.get(k) if isinstance(s.get(k), str) else None
                for k in ("error_code", "code", "error", "failure_reason", "notes")}
        safe["status_code"] = _number(s.get("status_code"))
        signatures.append(_failure_signature(sid, safe)[0])
    return m.RunComparisonFailureSignature(state="same_signature" if signatures[0] == signatures[1] else "different_signature")


def _owned(evidence: list[dict], run_id: str, sid: str | None) -> list[dict]:
    if sid is None:
        return []
    return [e for e in evidence if e["run_id"] == run_id and e["step_id"] == sid]


def _row(sid: str | None, bs: list, cs: list, observations: list,
         snapshots: list, state: str) -> m.RunStepComparison:
    b, c = bs[0] if len(bs) == 1 else None, cs[0] if len(cs) == 1 else None
    cases = [{s[k] for k in ("case_id", "test_case_id") if isinstance(s.get(k), str) and s[k]}
             for s in (b or {}, c or {})]
    if len(bs) > 1 or len(cs) > 1 or any(len(x) > 1 for x in cases) or (all(cases) and cases[0] != cases[1]):
        state = "identity_conflict"
    r = m.RunStepComparison(step_id=sid, identity_state=state)
    owned = []
    for prefix, s, observation, snapshot in zip(("baseline", "comparison"), (b, c), observations, snapshots):
        ev = _owned(snapshot["evidence"], observation.run_id, sid) if s is not None else []
        owned.append(ev)
        if s is None:
            continue
        provenance, basis = _provenance(s.get("provenance"))
        setattr(r, f"{prefix}_status", _text(s.get("status")))
        setattr(r, f"{prefix}_provenance", provenance)
        setattr(r, f"{prefix}_citation", m.RunComparisonCitation(
            run_id=observation.run_id, step_id=sid, provenance=provenance,
            provenance_basis=basis, evidence_ids=sorted({e["id"] for e in ev}),
        ))
        setattr(r, f"{prefix}_display", m.RunComparisonDisplay(
            **{key: _text(s.get(key)) for key in m.RunComparisonDisplay.model_fields},
        ))
    complete = all(s["evidence_complete"] for s in snapshots) and state not in {"identity_conflict", "identity_unavailable"}
    r.evidence_comparison = m.RunComparisonEvidenceSummary(
        complete=complete, baseline_count=len(owned[0]) if complete else None,
        comparison_count=len(owned[1]) if complete else None,
        baseline_type_counts=dict(sorted(Counter(_text(e.get("type")) or "unknown" for e in owned[0]).items())) if complete else {},
        comparison_type_counts=dict(sorted(Counter(_text(e.get("type")) or "unknown" for e in owned[1]).items())) if complete else {},
    )
    # Unique owned same-type artifact on each side: stored byte-hash comparison
    # only. Multiple artifacts lack a durable role identity; never pair by order.
    if complete and state == "matched" and all(len(ev) == 1 for ev in owned):
        be, ce = owned[0][0], owned[1][0]
        if be.get("type") and be.get("type") == ce.get("type") and all(
            isinstance(e.get("sha256"), str) and re.fullmatch(r"[a-fA-F0-9]{64}", e["sha256"])
            for e in (be, ce)
        ):
            r.evidence_comparison.hash_comparison = "same_hash" if be["sha256"].lower() == ce["sha256"].lower() else "different_hash"
    if state != "matched":
        r.reason_codes.append(state)
        return r
    if any(o.execution_mode == "manual" for o in observations):
        r.comparison_state = "informational"
        r.reason_codes.append("manual_observation")
        return r
    if any(o.execution_mode != "automated" for o in observations):
        r.reason_codes.append("execution_mode_unavailable")
    if _action(b) and _action(c) and _action(b) != _action(c):
        r.reason_codes.append("action_mismatch")
    if any(o.provenance_basis != "stored" or o.provenance not in {m.Provenance.REAL_EXECUTION, m.Provenance.MIXED} for o in observations):
        r.reason_codes.append("run_provenance_not_admissible")
    if any(_provenance(s.get("provenance")) != (m.Provenance.REAL_EXECUTION, "stored") for s in (b, c)):
        r.reason_codes.append("step_provenance_not_admissible")
    if r.reason_codes:
        return r
    r.comparison_state = "factual"
    r.transition = f"{_outcome(b)}_to_{_outcome(c)}"
    r.metric_comparisons = _metrics(b, c)
    r.failure_signature_comparison = _signature(sid, b, c)
    return r


def build_run_comparison(storage: ProductStorage, run_id: str, baseline_run_id: str) -> m.RunComparisonResponse:
    if not baseline_run_id.strip() or run_id == baseline_run_id:
        raise RunComparisonError(422, "Select a different, non-empty baseline run ID.")
    snapshot = storage.load_run_comparison_snapshot(baseline_run_id, run_id)
    snapshots = [snapshot[baseline_run_id], snapshot[run_id]]
    runs = [s["run"] for s in snapshots]
    if any(r is None for r in runs):
        raise RunComparisonError(404, "Run not found.")
    if any(r["status"] not in TERMINAL for r in runs):
        raise RunComparisonError(409, "Comparison requires terminal runs.")
    for key in ("pack_id", "app_target_id"):
        if any(not isinstance(r[key], str) or not r[key].strip() for r in runs) or runs[0][key] != runs[1][key]:
            raise RunComparisonError(409, "Comparison requires the same non-empty pack and app target.")
    observations = [_observation(r, s["evidence"]) for r, s in zip(runs, snapshots)]
    chronology = _chronology(*runs)
    warnings = [CONFIG_WARNING]
    if chronology.state in {"reverse", "unavailable", "same_time"}:
        warnings.append(f"Comparison chronology: {chronology.state}. Direction remains baseline to comparison.")
    if chronology.basis == "created_at":
        warnings.append("Chronology uses record creation times, not verified execution ordering.")
    omissions: list[str] = []
    step_lists = [_steps(r, omissions) for r in runs]
    # Never infer one-sided results when either entire result set is unavailable.
    grouped = [_group(steps) for steps in step_lists] if not omissions else [({}, []), ({}, [])]
    for observation, s in zip(observations, snapshots):
        if not s["evidence_complete"]:
            omissions.append(f"{observation.run_id}:evidence_limit_exceeded")
    bg, bm = grouped[0]
    cg, cm = grouped[1]
    rows = [_row(sid, bg.get(sid, []), cg.get(sid, []), observations, snapshots,
                 "matched" if sid in bg and sid in cg else "baseline_only" if sid in bg else "comparison_only")
            for sid in sorted(bg.keys() | cg.keys())]
    rows.extend(_row(None, [s], [], observations, snapshots, "identity_unavailable") for s in bm)
    rows.extend(_row(None, [], [s], observations, snapshots, "identity_unavailable") for s in cm)
    counts = m.RunComparisonSummaryCounts()
    for r in rows:
        setattr(counts, r.identity_state, getattr(counts, r.identity_state) + 1)
        key = "inconclusive_transitions" if "inconclusive" in r.transition else r.transition
        setattr(counts, key, getattr(counts, key) + 1)
    factual = sum(r.comparison_state == "factual" for r in rows)
    compatibility = "compatible" if factual and factual == len(rows) else "partial" if factual else "informational" if any(o.execution_mode == "manual" for o in observations) else "unavailable"
    return m.RunComparisonResponse(
        baseline_run_id=baseline_run_id, comparison_run_id=run_id,
        scope=m.RunComparisonScope(pack_id=runs[0]["pack_id"], app_target_id=runs[0]["app_target_id"]),
        baseline=observations[0], comparison=observations[1], chronology=chronology,
        provenance_compatibility=compatibility,
        comparability=m.RunComparisonComparability(state="partial" if rows else "unavailable",
                      reason_codes=["configuration_continuity_unknown"]),
        comparability_warnings=warnings, coverage=m.RunComparisonCoverage(complete=not omissions, omissions=omissions),
        summary_counts=counts, step_comparisons=rows,
    )
