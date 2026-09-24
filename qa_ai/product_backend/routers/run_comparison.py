"""Explicit, read-only persisted run comparison API."""
from fastapi import APIRouter, Depends, HTTPException, Query

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import RunComparisonResponse
from qa_ai.product_backend.run_comparison import RunComparisonError, build_run_comparison
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["run-comparison"])


@router.get("/runs/{run_id}/compare", response_model=RunComparisonResponse)
def compare_runs(run_id: str, baseline_run_id: str = Query(min_length=1, max_length=512),
                 storage: ProductStorage = Depends(get_storage)) -> RunComparisonResponse:
    try:
        return build_run_comparison(storage, run_id, baseline_run_id)
    except RunComparisonError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except Exception:
        # Never disclose exception text, SQL, persisted payloads or credentials.
        raise HTTPException(status_code=500, detail="Run comparison unavailable.") from None
