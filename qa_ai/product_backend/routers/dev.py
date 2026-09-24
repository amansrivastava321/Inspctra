"""
dev.py - Dev/test-only cleanup utilities.

SECURITY: All endpoints require INSPECTRA_ENABLE_DEV_CLEANUP=true env var.
Never use in production without the env guard.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["dev"])

_ENV_KEY = "INSPECTRA_ENABLE_DEV_CLEANUP"


def _require_cleanup_enabled() -> None:
    if not os.environ.get(_ENV_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Dev cleanup disabled. Set {_ENV_KEY}=true to enable.",
        )


@router.delete("/dev/e2e-data", status_code=status.HTTP_200_OK)
def cleanup_e2e_data(
    confirm: bool = Query(default=False),
    storage: ProductStorage = Depends(get_storage),
) -> dict:
    """
    Delete all records with names starting 'E2E-'.
    Requires: INSPECTRA_ENABLE_DEV_CLEANUP=true + confirm=true.
    Never deletes records without the 'E2E-' name prefix.
    """
    _require_cleanup_enabled()
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pass confirm=true to proceed with E2E data cleanup.",
        )
    deleted = storage.delete_e2e_test_data()
    return {"deleted": deleted}
