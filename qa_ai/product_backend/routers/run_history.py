"""Read-only deterministic historical run memory API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import RunHistoryResponse
from qa_ai.product_backend.run_history import RunHistoryRunNotFound, build_run_history
from qa_ai.product_backend.storage import ProductStorage


router = APIRouter(tags=["run-history"])


@router.get("/runs/{run_id}/history", response_model=RunHistoryResponse)
def get_run_history(
    run_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    storage: ProductStorage = Depends(get_storage),
) -> RunHistoryResponse:
    try:
        return build_run_history(storage, run_id, limit=limit)
    except RunHistoryRunNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        ) from None
