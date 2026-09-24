"""
evaluations.py - AI Evidence Evaluation Router.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import AIEvaluationNote, AIEvaluationRequest
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.ai.evidence_evaluator import AIEvidenceEvaluator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["evaluations"])


@router.post("/runs/{run_id}/evaluate-ai", response_model=AIEvaluationNote, status_code=status.HTTP_201_CREATED)
def evaluate_run_evidence(
    run_id: str,
    body: AIEvaluationRequest = AIEvaluationRequest(),
    storage: ProductStorage = Depends(get_storage),
) -> AIEvaluationNote:
    """
    Trigger AI evidence evaluation for a test run.
    Does not modify the run status or step verdicts.
    """
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )

    try:
        evaluator = AIEvidenceEvaluator(storage)
        note_dict = evaluator.evaluate_run(run_id, step_id=body.step_id)
        storage.create_ai_evaluation_note(note_dict)
        return AIEvaluationNote(**note_dict)
    except Exception as exc:
        logger.error("AI Evidence Evaluation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {exc}",
        )


@router.get("/runs/{run_id}/evaluation-ai", response_model=List[AIEvaluationNote])
def get_run_evaluations(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> List[AIEvaluationNote]:
    """Retrieve existing AI evaluation notes for a run."""
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )

    rows = storage.list_ai_evaluation_notes(run_id)
    return [AIEvaluationNote(**r) for r in rows]
