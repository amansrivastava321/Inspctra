"""
dashboard.py - GET /api/dashboard

Returns aggregate product stats.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from qa_ai.product_backend.dashboard_summary import build_dashboard_summary
from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import DashboardSummary
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(storage: ProductStorage = Depends(get_storage)) -> DashboardSummary:
    """Return one persisted, provenance-labelled dashboard snapshot."""
    return build_dashboard_summary(storage)
