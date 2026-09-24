"""
app_map.py — Routes for app map generation and retrieval.

POST /api/apps/{app_id}/app-map/generate   — generate fingerprint-based app map
GET  /api/apps/{app_id}/app-map            — get stored app map (or 404)

Security:
- Never re-scans files without explicit user action.
- Never executes commands.
- Never stores raw source code.
- Discovery data already stored — only reads existing records.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from qa_ai.product_backend.app_map_models import AppMapDraft
from qa_ai.product_backend.app_map_service import generate_app_map_from_app_record
from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["app-map"])


@router.post(
    "/apps/{app_id}/app-map/generate",
    response_model=AppMapDraft,
    status_code=status.HTTP_201_CREATED,
)
def generate_app_map(
    app_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> AppMapDraft:
    """
    Generate a fingerprint-based app map for an app.

    Uses the app's stored discovery result if available.
    Does NOT re-scan files. Does NOT execute commands.
    Returns map_type='fingerprint_based_draft' — never claims deep analysis.
    """
    app = storage.get_app_target(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="App not found.")

    # Load discovery result if this app was created via discovery
    discovery = None
    if app.get("discovery_id"):
        discovery = storage.get_discovery_result(app["discovery_id"])

    app_map = generate_app_map_from_app_record(app=app, discovery=discovery)
    storage.save_app_map(app_map)
    return app_map


@router.get(
    "/apps/{app_id}/app-map",
    response_model=Optional[AppMapDraft],
)
def get_app_map(
    app_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> Optional[AppMapDraft]:
    """
    Return the stored app map for an app, or null if none exists.
    """
    app = storage.get_app_target(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="App not found.")

    return storage.get_app_map_for_app(app_id)
