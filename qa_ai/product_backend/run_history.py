"""Deterministic, read-only historical facts for product runs.

ProductStorage is the sole factual source. This module performs exact-ID
aggregation only: no AI, fuzzy matching, memory-kernel reads, or writes.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

from qa_ai.product_backend.dashboard_summary import normalize_failure
from qa_ai.product_backend.models import (
    Provenance,
    RepeatedFailureSignature,
    RunHistoryCitation,
    RunHistoryFailureRate,
    RunHistoryItem,
    RunHistoryResponse,
    RunHistoryScope,
    RunStepHistory,
)
from qa_ai.product_backend.storage import ProductStorage


_FAILURE_STATES = frozenset({"failed", "failure", "error", "blocked"})
_INCONCLUSIVE_STATES = frozenset(
    {"inconclusive", "unclear", "skipped", "capability_gap", "dry_run", "dry-run"}
)
_PASS_STATES = frozenset({"passed", "pass", "completed", "success", "succeeded"})
_CONFIG_WARNING = (
    "Historical execution configuration was not snapshotted; configuration and "
    "base URL continuity cannot be verified."
)
_TEXT_LIMIT = 512


class RunHistoryRunNotFound(LookupError):
    """Raised when the requested current run does not exist."""


def _provenance(value: Any) -> Provenance:
    try:
        return Provenance(value or Provenance.UNAVAILABLE)
    except ValueError:
        return Provenance.UNAVAILABLE


def _status(value: Any) -> str:
    return str(value or "").strip().casefold()


def _normalized_text(value: Any) -> str:
    """Normalize only casing/whitespace and bound retained factual text."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip().casefold()[:_TEXT_LIMIT]


def _step_outcome(step: Mapping[str, Any]) -> str:
    state = _status(step.get("status") or step.get("verdict"))
    if state in _PASS_STATES:
        return "passed"
    if state in _FAILURE_STATES:
        return "failed"
    return "inconclusive"


def _run_level_outcome(run: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Return factual run outcome or a deterministic exclusion reason."""
    if str(run.get("execution_mode") or "automated").casefold() == "manual":
        return None, "manual_execution"

    provenance = _provenance(run.get("provenance"))
    if provenance == Provenance.DRY_RUN:
        return None, "dry_run"
    if provenance == Provenance.SIMULATED:
        return None, "simulated"
    if provenance == Provenance.DEMO_EXAMPLE:
        return None, "demo_example"
    if provenance == Provenance.UNAVAILABLE:
        return None, "unavailable_provenance"
    if provenance == Provenance.MIXED:
        return None, "mixed_run_level"
    if provenance != Provenance.REAL_EXECUTION:
        return None, "unavailable_provenance"

    run_status = _status(run.get("status"))
    if run_status == "cancelled":
        return None, "cancelled"

    steps = [
        step
        for step in (run.get("step_results") or [])
        if isinstance(step, Mapping)
        and _provenance(step.get("provenance")) == Provenance.REAL_EXECUTION
    ]
    outcomes = [_step_outcome(step) for step in steps]
    if run_status == "failed" or "failed" in outcomes:
        # A persisted REAL_EXECUTION run failure is factual even when failure
        # occurred before a step result could be recorded.
        return "failed", None
    if run_status != "completed":
        return None, "non_factual_terminal_status"
    if not steps:
        return None, "no_admissible_real_steps"
    if any(outcome == "inconclusive" for outcome in outcomes):
        return None, "inconclusive_run"
    return "passed", None


def _citation(
    run: Mapping[str, Any],
    *,
    step_id: str | None = None,
    evidence_ids: Iterable[str] = (),
) -> RunHistoryCitation:
    return RunHistoryCitation(
        run_id=str(run["id"]),
        step_id=step_id,
        completed_at=run.get("completed_at"),
        provenance=_provenance(run.get("provenance")),
        evidence_ids=list(evidence_ids),
    )


def _history_item(
    run: Mapping[str, Any],
    *,
    outcome: str | None,
    exclusion_reason: str | None,
) -> RunHistoryItem:
    included = outcome in {"passed", "failed"}
    return RunHistoryItem(
        run_id=str(run["id"]),
        status=str(run.get("status") or ""),
        outcome=outcome,
        execution_mode=str(run.get("execution_mode") or "automated"),
        provenance=_provenance(run.get("provenance")),
        started_at=run.get("started_at"),
        completed_at=run.get("completed_at"),
        created_at=str(run.get("created_at") or ""),
        included_in_failure_rate=included,
        exclusion_reason=exclusion_reason,
        citation=_citation(run),
    )


def _owned_evidence_ids(
    step: Mapping[str, Any],
    *,
    run_id: str,
    step_id: str | None,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    if step_id is None:
        return []
    owned: list[str] = []
    for raw_id in step.get("evidence_ids") or []:
        evidence_id = str(raw_id)
        evidence = evidence_by_id.get(evidence_id)
        if (
            evidence is not None
            and evidence.get("run_id") == run_id
            and evidence.get("step_id") == step_id
        ):
            owned.append(evidence_id)
    return sorted(set(owned))


def _failure_signature(
    step_id: str,
    step: Mapping[str, Any],
) -> tuple[str, dict[str, str]]:
    error_code = _normalized_text(step.get("error_code") or step.get("code"))
    error = _normalized_text(step.get("error"))
    failure_reason = _normalized_text(step.get("failure_reason"))
    notes = _normalized_text(step.get("notes"))
    status_code = step.get("status_code")
    if status_code is None and isinstance(step.get("response_summary"), Mapping):
        status_code = step["response_summary"].get("status_code")
    try:
        status_code = int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        status_code = None
    raw_message = " ".join(part for part in (error, failure_reason, notes) if part)
    category = normalize_failure(raw_message, status_code)
    fields = {
        "category": category,
        "error_code": error_code,
        "error": error,
        "failure_reason": failure_reason,
        "notes": notes,
    }
    canonical = json.dumps(
        {"step_id": step_id, **fields},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), fields


def build_run_history(
    storage: ProductStorage,
    run_id: str,
    *,
    limit: int = 20,
) -> RunHistoryResponse:
    """Build a deterministic history snapshot without mutating persisted state."""
    current = storage.get_run(run_id)
    if current is None:
        raise RunHistoryRunNotFound(run_id)

    runs = storage.list_comparable_runs(
        pack_id=str(current["pack_id"]),
        app_target_id=str(current["app_target_id"]),
        exclude_run_id=run_id,
        limit=limit,
    )

    exclusions: Counter[str] = Counter()
    recent_runs: list[RunHistoryItem] = []
    manual_observations: list[RunHistoryItem] = []
    considered: list[tuple[Mapping[str, Any], str, RunHistoryItem]] = []
    stable_steps: dict[str, list[tuple[str, RunHistoryCitation]]] = defaultdict(list)
    missing_steps: list[RunStepHistory] = []
    signatures: dict[str, dict[str, Any]] = {}

    for run in runs:
        outcome, exclusion_reason = _run_level_outcome(run)
        item = _history_item(run, outcome=outcome, exclusion_reason=exclusion_reason)
        recent_runs.append(item)
        if exclusion_reason:
            exclusions[exclusion_reason] += 1
        if exclusion_reason == "manual_execution":
            manual_observations.append(item)
        if outcome is not None:
            considered.append((run, outcome, item))

        if str(run.get("execution_mode") or "automated").casefold() == "manual":
            continue
        run_provenance = _provenance(run.get("provenance"))
        if run_provenance not in {Provenance.REAL_EXECUTION, Provenance.MIXED}:
            continue

        evidence_rows = storage.list_run_evidence_for_history(str(run["id"]))
        evidence_by_id = {str(row["id"]): row for row in evidence_rows}
        for step in run.get("step_results") or []:
            if not isinstance(step, Mapping):
                continue
            if _provenance(step.get("provenance")) != Provenance.REAL_EXECUTION:
                continue
            step_id_value = step.get("step_id")
            step_id = str(step_id_value).strip() if step_id_value is not None else ""
            step_id = step_id or None
            step_outcome = _step_outcome(step)
            owned_ids = _owned_evidence_ids(
                step,
                run_id=str(run["id"]),
                step_id=step_id,
                evidence_by_id=evidence_by_id,
            )
            citation = _citation(
                run,
                step_id=step_id,
                evidence_ids=owned_ids,
            )
            if step_id is None:
                missing_steps.append(RunStepHistory(
                    step_id=None,
                    passed=int(step_outcome == "passed"),
                    failed=int(step_outcome == "failed"),
                    inconclusive=int(step_outcome == "inconclusive"),
                    total=1,
                    citations=[citation],
                    insufficient_identity=True,
                ))
                continue

            stable_steps[step_id].append((step_outcome, citation))
            if step_outcome == "failed":
                signature, fields = _failure_signature(step_id, step)
                bucket = signatures.setdefault(
                    signature,
                    {
                        "step_id": step_id,
                        **fields,
                        "citations": [],
                    },
                )
                bucket["citations"].append(citation)

    step_history: list[RunStepHistory] = []
    for step_id in sorted(stable_steps):
        observations = stable_steps[step_id]
        outcomes = [outcome for outcome, _citation_item in observations]
        step_history.append(RunStepHistory(
            step_id=step_id,
            passed=outcomes.count("passed"),
            failed=outcomes.count("failed"),
            inconclusive=outcomes.count("inconclusive"),
            total=len(outcomes),
            citations=[citation for _outcome, citation in observations],
            insufficient_identity=False,
        ))
    step_history.extend(missing_steps)

    repeated = [
        RepeatedFailureSignature(
            signature=signature,
            occurrences=len(bucket["citations"]),
            **bucket,
        )
        for signature, bucket in sorted(signatures.items())
        if len(bucket["citations"]) >= 2
    ]

    failed = sum(1 for _run, outcome, _item in considered if outcome == "failed")
    total = len(considered)
    last_passed = next(
        (item for _run, outcome, item in considered if outcome == "passed"),
        None,
    )
    last_failed = next(
        (item for _run, outcome, item in considered if outcome == "failed"),
        None,
    )

    return RunHistoryResponse(
        run_id=run_id,
        scope=RunHistoryScope(
            pack_id=str(current["pack_id"]),
            app_target_id=str(current["app_target_id"]),
        ),
        considered_runs=total,
        excluded_runs=len(runs) - total,
        exclusions_by_reason=dict(sorted(exclusions.items())),
        insufficient_history=total < 2,
        comparability_warnings=[_CONFIG_WARNING] if runs else [],
        last_passed=last_passed,
        last_failed=last_failed,
        failure_rate=RunHistoryFailureRate(
            failed=failed,
            total=total,
            value=(failed / total) if total else 0.0,
            citations=[item.citation for _run, _outcome, item in considered],
        ),
        step_history=step_history,
        repeated_failure_signatures=repeated,
        recent_runs=recent_runs,
        manual_observations=manual_observations,
    )
