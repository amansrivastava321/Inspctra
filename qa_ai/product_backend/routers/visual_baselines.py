"""
visual_baselines.py - Router for managing visual regression baselines.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.artifact_index import ArtifactIndex

logger = logging.getLogger(__name__)
router = APIRouter(tags=["visual_baselines"])


class VisualBaselineRegisterRequest(BaseModel):
    app_id: str
    step_id: str
    baseline_name: str
    evidence_id: str


class VisualBaselineResponse(BaseModel):
    id: str
    app_id: str
    step_id: str
    name: str
    relative_path: str
    created_at: str
    updated_at: str


# ── dependency helpers ────────────────────────────────────────────────────────

def get_storage(request: Request) -> ProductStorage:
    return request.app.state.storage


def get_artifact_index(request: Request) -> ArtifactIndex:
    return request.app.state.artifact_index


# ── routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/baselines",
    response_model=VisualBaselineResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_baseline(
    req: VisualBaselineRegisterRequest,
    storage: ProductStorage = Depends(get_storage),
    artifact_index: ArtifactIndex = Depends(get_artifact_index),
) -> Dict[str, Any]:
    """
    Create or update a visual baseline from an existing screenshot evidence.
    """
    # 1. Fetch screenshot evidence
    ev = storage.get_evidence(req.evidence_id)
    if not ev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {req.evidence_id} not found."
        )

    if ev.get("type") != "screenshot" and ev.get("evidence_type") != "screenshot":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evidence must be of type 'screenshot'."
        )

    source_path = ev.get("relative_path") or ev.get("path")
    if not source_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evidence file path is missing."
        )

    # 2. Read source screenshot bytes
    try:
        source_abs_path = artifact_index._resolve_safe(source_path)
        screenshot_bytes = source_abs_path.read_bytes()
    except Exception as e:
        logger.error(f"Failed to read source screenshot file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read screenshot file: {e}"
        )

    # 3. Check for existing baseline and clear it
    existing = storage.get_visual_baseline_by_step(req.app_id, req.step_id)
    if existing:
        storage.delete_visual_baseline(existing["id"])

    # 4. Write baseline file
    baseline_id = str(uuid.uuid4())
    rel_path = f"baselines/{req.app_id}/{req.step_id}.png"
    try:
        artifact_index.write_file(rel_path, screenshot_bytes)
    except Exception as e:
        logger.error(f"Failed to write baseline file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not write baseline file: {e}"
        )

    # 5. Save metadata
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": baseline_id,
        "app_id": req.app_id,
        "step_id": req.step_id,
        "name": req.baseline_name,
        "relative_path": rel_path,
        "created_at": now,
        "updated_at": now,
    }
    try:
        storage.create_visual_baseline(record)
    except Exception as e:
        logger.error(f"Failed to save baseline metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save baseline metadata: {e}"
        )

    return record


@router.get("/baselines", response_model=List[VisualBaselineResponse])
def list_baselines(
    app_id: Optional[str] = None,
    storage: ProductStorage = Depends(get_storage),
) -> List[Dict[str, Any]]:
    """
    List all visual baselines, optionally filtered by app_id.
    """
    return storage.list_visual_baselines(app_id=app_id)


@router.get("/baselines/{baseline_id}/download")
def download_baseline(
    baseline_id: str,
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
) -> StreamingResponse:
    """
    Stream baseline image file content safely.
    """
    row = storage.get_visual_baseline(baseline_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found.")

    relative_path: str = row.get("relative_path", "")
    if not relative_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No file path stored.")

    try:
        stream = index.stream_file(relative_path)
    except ValueError as exc:
        logger.error("download_baseline: path traversal attempt blocked: %s", exc)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk.")

    mime = "image/png"
    filename = f"{row.get('name', 'baseline')}.png"

    return StreamingResponse(
        stream,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
