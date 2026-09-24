"""Draft-only AI root-cause suggestion API."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from qa_ai.ai.root_cause_suggester import AIRootCauseSuggester
from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.dependencies import get_artifact_index, get_storage
from qa_ai.product_backend.models import (
    AIRootCauseRequest,
    AIRootCauseSuggestionBatch,
    Provenance,
)
from qa_ai.product_backend.storage import ProductStorage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["root-causes"])

_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "passed", "blocked", "error"}
)
_FAILURE_STEP_STATUSES = frozenset(
    {"failed", "failure", "error", "blocked", "inconclusive", "capability_gap"}
)
_ACTIVE_DETAIL = "Root cause suggestions not available — run is still in progress."
_NO_FAILURE_DETAIL = "Root cause suggestions not available — run has no failure signal."


def _find_step(run: dict, step_id: str) -> dict | None:
    return next(
        (
            step
            for step in run.get("step_results") or []
            if step.get("step_id") == step_id
        ),
        None,
    )


def _has_failure_signal(run: dict, step_id: str | None) -> bool:
    steps = run.get("step_results") or []
    if step_id is not None:
        steps = [step for step in steps if step.get("step_id") == step_id]
    failed_step = any(
        str(step.get("status") or "").casefold() in _FAILURE_STEP_STATUSES
        for step in steps
    )
    return bool(
        failed_step
        or run.get("error")
        or (step_id is None and str(run.get("status") or "").casefold() == "failed")
    )


@router.post(
    "/runs/{run_id}/root-cause-ai",
    response_model=AIRootCauseSuggestionBatch,
    status_code=status.HTTP_201_CREATED,
)
def create_root_cause_suggestions(
    run_id: str,
    body: AIRootCauseRequest = AIRootCauseRequest(),
    storage: ProductStorage = Depends(get_storage),
    artifact_index: ArtifactIndex = Depends(get_artifact_index),
) -> AIRootCauseSuggestionBatch:
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    run_status = str(run.get("status") or "").casefold()
    if run_status not in _TERMINAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_ACTIVE_DETAIL)

    if body.step_id is not None and _find_step(run, body.step_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found.")

    if not _has_failure_signal(run, body.step_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_NO_FAILURE_DETAIL)

    try:
        batch = AIRootCauseSuggester(storage, artifact_index).suggest(
            run_id, step_id=body.step_id
        )
        validated = AIRootCauseSuggestionBatch(**batch)
        storage.create_ai_root_cause_suggestions(validated.model_dump(mode="json"))
        return validated
    except Exception:
        # Deliberately omit exception text: provider and artifact errors may carry secrets.
        logger.error("Root cause suggestion generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Root cause suggestion generation failed.",
        ) from None


@router.get(
    "/runs/{run_id}/root-cause-ai",
    response_model=AIRootCauseSuggestionBatch,
)
def get_root_cause_suggestions(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> AIRootCauseSuggestionBatch:
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    batch = storage.get_latest_ai_root_cause_batch(run_id)
    if batch is not None:
        return AIRootCauseSuggestionBatch(**batch)
    return AIRootCauseSuggestionBatch(
        analysis_id="",
        run_id=run_id,
        status="inconclusive",
        authoritative=False,
        source_provenance=Provenance.UNAVAILABLE,
        generation_source="unavailable",
        generation_metadata={},
        missing_evidence=["No root cause suggestions have been generated."],
        suggestions=[],
        created_at=run.get("completed_at") or run.get("created_at"),
    )
