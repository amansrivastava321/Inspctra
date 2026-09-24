"""
evidence.py - Evidence file API + safe download

GET /api/evidence              — list (filter by run_id)
GET /api/evidence/{id}         — metadata
GET /api/evidence/{id}/download — stream file content (path-traversal safe)
"""
from __future__ import annotations

import json
import logging
import re
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from qa_ai.product_backend.artifact_index import ArtifactIndex, _guess_mime
from qa_ai.product_backend.dependencies import get_artifact_index, get_storage
from qa_ai.product_backend.models import EvidenceFile
from qa_ai.product_backend.storage import ProductStorage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["evidence"])


def _archive_segment(value: object, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "")).strip("_")
    return cleaned[:80] or fallback


def _evidence_extension(row: dict) -> str:
    suffix = Path(str(row.get("relative_path") or "")).suffix.lower()
    if suffix and re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
        return suffix
    mime = str(row.get("mime_type") or "")
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "text/html": ".html",
        "text/plain": ".txt",
        "application/json": ".json",
    }.get(mime, ".bin")


@router.get("/evidence", response_model=List[EvidenceFile])
def list_evidence(
    run_id: Optional[str] = Query(default=None),
    storage: ProductStorage = Depends(get_storage),
) -> List[EvidenceFile]:
    return [EvidenceFile(**r) for r in storage.list_evidence(run_id=run_id)]


@router.get("/evidence/{evidence_id}", response_model=EvidenceFile)
def get_evidence(
    evidence_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> EvidenceFile:
    row = storage.get_evidence(evidence_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    return EvidenceFile(**row)


@router.get("/evidence/{evidence_id}/download")
def download_evidence(
    evidence_id: str,
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
) -> StreamingResponse:
    """
    Stream evidence file content safely.

    Path traversal prevention: relative_path from DB is resolved via
    ArtifactIndex._resolve_safe(), which raises ValueError if the
    resolved path escapes the artifacts directory.
    """
    row = storage.get_evidence(evidence_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")

    relative_path: str = row.get("relative_path", "")
    if not relative_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No file path stored.")

    try:
        stream = index.stream_file(relative_path)
    except ValueError as exc:
        logger.error("download_evidence: path traversal attempt blocked: %s", exc)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk.")

    mime = row.get("mime_type") or _guess_mime(row.get("name", ""))
    filename = row.get("name", "evidence")

    return StreamingResponse(
        stream,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/runs/{run_id}/evidence.zip")
def download_run_evidence_zip(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
) -> StreamingResponse:
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    # Import locally to keep router modules independent during application setup.
    from qa_ai.product_backend.routers.live_runs import extract_run_steps

    steps = extract_run_steps(run.get("pack_id", ""), storage)
    step_info = {
        step.get("step_id"): (
            position,
            step.get("description") or f"Step {position}",
        )
        for position, step in enumerate(steps, start=1)
    }
    safe_run_id = _archive_segment(run_id, "run")
    root = f"run_{safe_run_id}"
    archive_file = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    included: List[dict] = []
    missing: List[dict] = []
    name_counts: dict[tuple[str, str], int] = {}

    with zipfile.ZipFile(archive_file, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in reversed(storage.list_evidence(run_id=run_id)):
            metadata = row.get("metadata_json") or {}
            default_index = int(metadata.get("step_index") or 0)
            step_index, step_name = step_info.get(
                row.get("step_id"),
                (default_index, f"Step {default_index}" if default_index else "Run"),
            )
            folder = (
                f"step_{step_index}_{_archive_segment(step_name, 'step')}"
                if step_index
                else "run_level"
            )
            evidence_type = _archive_segment(
                row.get("type") or row.get("evidence_type"), "artifact"
            )
            count_key = (folder, evidence_type)
            name_counts[count_key] = name_counts.get(count_key, 0) + 1
            suffix = "" if name_counts[count_key] == 1 else f"_{name_counts[count_key]}"
            archive_name = (
                f"{root}/{folder}/{evidence_type}{suffix}{_evidence_extension(row)}"
            )
            manifest_item = {
                "evidence_id": row.get("id"),
                "step_id": row.get("step_id"),
                "type": row.get("type") or row.get("evidence_type"),
                "archive_path": archive_name,
            }
            try:
                stream = index.stream_file(str(row.get("relative_path") or ""))
                with archive.open(archive_name, mode="w") as target:
                    for chunk in stream:
                        target.write(chunk)
                included.append(manifest_item)
            except (FileNotFoundError, ValueError) as exc:
                missing.append({**manifest_item, "reason": type(exc).__name__})

        manifest = {
            "run_id": run_id,
            "included_artifacts": included,
            "missing_artifacts": missing,
        }
        archive.writestr(
            f"{root}/manifest.json",
            json.dumps(manifest, indent=2, default=str).encode("utf-8"),
        )

    archive_file.seek(0)

    def stream_archive():
        try:
            while True:
                chunk = archive_file.read(65_536)
                if not chunk:
                    break
                yield chunk
        finally:
            archive_file.close()

    return StreamingResponse(
        stream_archive(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="run_{safe_run_id}_evidence.zip"',
            "X-Content-Type-Options": "nosniff",
        },
    )
