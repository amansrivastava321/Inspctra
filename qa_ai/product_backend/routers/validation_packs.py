"""
validation_packs.py - CRUD + run trigger /api/validation-packs
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.dependencies import get_artifact_index, get_run_manager, get_storage
from qa_ai.product_backend.notifier import is_valid_webhook_url, mask_webhook_url
from qa_ai.product_backend.pack_steps import build_pack_steps
from qa_ai.product_backend.models import (
    LiveRunRecord,
    Provenance,
    StartRunRequest,
    ValidationPack,
    ValidationPackCreate,
    ValidationPackUpdate,
)
from qa_ai.product_backend.run_manager import DEFAULT_WATCH_SLOW_MO_MS, RunManager, RunOptions
from qa_ai.product_backend.scheduler import (
    MAX_INTERVAL_HOURS,
    MAX_INTERVAL_MINUTES,
    MIN_INTERVAL_MINUTES,
    is_valid_schedule,
    resolve_timezone,
)
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.routers.live_runs import extract_run_steps

router = APIRouter(tags=["validation-packs"])


def _validate_schedule_fields(fields: dict) -> None:
    """400 on a schedule, timezone or webhook URL the scheduler/notifier could not honour."""
    if "schedule" in fields and not is_valid_schedule(fields["schedule"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unknown schedule. Use none, hourly, daily, nightly, weekdays, "
                f"every_<N>m ({MIN_INTERVAL_MINUTES}-{MAX_INTERVAL_MINUTES}) or every_<N>h (1-{MAX_INTERVAL_HOURS})."
            ),
        )
    if "schedule_timezone" in fields and resolve_timezone(fields["schedule_timezone"]) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown timezone. Use an IANA name such as UTC, Europe/London or Asia/Kolkata.",
        )
    url = fields.get("notify_webhook_url")
    if url and not is_valid_webhook_url(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="notify_webhook_url must be an http(s) URL.",
        )


def _public_pack(row: dict) -> ValidationPack:
    """The pack as the API returns it: the webhook URL may carry a secret token, so only its origin is shown."""
    return ValidationPack(**{**row, "notify_webhook_url": mask_webhook_url(row.get("notify_webhook_url"))})


@router.get("/validation-packs", response_model=List[ValidationPack])
def list_packs(
    project_id: Optional[str] = Query(default=None),
    app_id: Optional[str] = Query(default=None),
    storage: ProductStorage = Depends(get_storage),
) -> List[ValidationPack]:
    return [
        _public_pack(r)
        for r in storage.list_validation_packs(project_id=project_id, app_id=app_id)
    ]


@router.post("/validation-packs", response_model=ValidationPack, status_code=status.HTTP_201_CREATED)
def create_pack(
    body: ValidationPackCreate,
    storage: ProductStorage = Depends(get_storage),
) -> ValidationPack:
    if storage.get_project(body.project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    # Validate app_id if provided
    if body.app_id:
        app_row = storage.get_app_target(body.app_id)
        if app_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"App target not found: {body.app_id!r}",
            )
        # Cross-project mismatch guard — app must belong to the same project
        if app_row.get("project_id") != body.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"App target {body.app_id!r} belongs to project "
                    f"{app_row.get('project_id')!r}, not {body.project_id!r}. "
                    "Pack and app must be in the same project."
                ),
            )

    rec = ValidationPack(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        steps=body.steps,
        app_id=body.app_id,
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_validation_pack(rec.model_dump())
    return rec


@router.get("/validation-packs/{pack_id}", response_model=ValidationPack)
def get_pack(pack_id: str, storage: ProductStorage = Depends(get_storage)) -> ValidationPack:
    row = storage.get_validation_pack(pack_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation pack not found.")
    return _public_pack(row)


def _get_scheduler(request: Request):
    """Return the PackScheduler from app.state, or None if not wired (tests)."""
    return getattr(request.app.state, "scheduler", None)


@router.patch("/validation-packs/{pack_id}", response_model=ValidationPack)
def update_pack(
    pack_id: str,
    body: ValidationPackUpdate,
    request: Request,
    storage: ProductStorage = Depends(get_storage),
) -> ValidationPack:
    row = storage.get_validation_pack(pack_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation pack not found.")
    fields = body.model_dump(exclude_none=True)
    _validate_schedule_fields(fields)

    # Validate app_id linkage on update — same guard as create_pack
    if "app_id" in fields and fields["app_id"] is not None:
        new_app_id = fields["app_id"]
        app_row = storage.get_app_target(new_app_id)
        if app_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"App target not found: {new_app_id!r}",
            )
        # Cross-project guard: app must belong to the same project as the pack
        pack_project_id = row.get("project_id")
        if app_row.get("project_id") != pack_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"App target {new_app_id!r} belongs to project "
                    f"{app_row.get('project_id')!r}, not {pack_project_id!r}. "
                    "Pack and app must be in the same project."
                ),
            )

    # Serialize steps to dicts if present
    if "steps" in fields and fields["steps"] is not None:
        fields["steps"] = [s.model_dump() if hasattr(s, "model_dump") else s for s in fields["steps"]]
    updated = storage.update_validation_pack(pack_id, fields)

    # Notify scheduler if schedule settings changed
    if {"schedule", "schedule_enabled", "schedule_timezone"} & fields.keys():
        sched = _get_scheduler(request)
        if sched is not None:
            result = updated or row
            sched.notify_schedule_changed(
                pack_id,
                schedule=result.get("schedule"),
                enabled=bool(result.get("schedule_enabled")),
                tz_name=result.get("schedule_timezone"),
            )
            # The scheduler has just stored next_run_at; re-read so the response carries it instead
            # of the value from before the change (which made a saved schedule look like it had no next run).
            updated = storage.get_validation_pack(pack_id) or updated

    return _public_pack(updated or row)


@router.delete("/validation-packs/{pack_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pack(
    pack_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> None:
    if not storage.delete_validation_pack(pack_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation pack not found.")


@router.post("/validation-packs/{pack_id}/run", response_model=LiveRunRecord, status_code=status.HTTP_202_ACCEPTED)
@router.post("/validation-packs/{pack_id}/runs", response_model=LiveRunRecord, status_code=status.HTTP_202_ACCEPTED)
def run_pack(
    pack_id: str,
    body: StartRunRequest,
    storage: ProductStorage = Depends(get_storage),
    run_manager: RunManager = Depends(get_run_manager),
    artifact_index: ArtifactIndex = Depends(get_artifact_index),
) -> LiveRunRecord:
    """
    Start a background run of this validation pack against an app target.

    Returns 202 Accepted with the LiveRunRecord immediately.
    Poll GET /api/runs/{run_id} or stream GET /api/runs/{run_id}/stream for updates.
    """
    pack_row = storage.get_validation_pack(pack_id)
    if pack_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation pack not found.")

    target_row = storage.get_app_target(body.app_target_id)
    if target_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App target not found.")

    execution_mode = body.execution_mode or "automated"
    if execution_mode not in ("manual", "automated"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid execution_mode. Must be manual or automated.")
    if execution_mode == "manual" and (body.watch or body.continuous or body.slow_mo_ms is not None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="watch, slow_mo_ms and continuous apply to automated runs only.",
        )

    run = LiveRunRecord(
        pack_id=pack_id,
        app_target_id=body.app_target_id,
        execution_mode=execution_mode,
        status="pending"
    )
    storage.create_run(run.model_dump())

    if execution_mode == "manual":
        # Manual work is honest while pending: every requested confirmation has
        # durable UNAVAILABLE evidence until a person supplies a verdict.
        steps = extract_run_steps(pack_id, storage)
        pending_results = []
        for step_index, step in enumerate(steps, start=1):
            step_id = step.get("step_id") or f"manual-step-{step_index}"
            evidence_id = str(uuid.uuid4())
            metadata = {
                "status": "pending",
                "requested_confirmation": step.get("description") or f"Step {step_index}",
                "step_index": step_index,
                "app_id": target_row.get("id"),
                "project_id": target_row.get("project_id"),
            }
            raw = json.dumps(metadata, indent=2).encode("utf-8")
            relative_path = f"runs/{run.id}/step_{step_index}_manual_confirmation.json"
            artifact_index.write_file(relative_path, raw)
            storage.create_evidence({
                "id": evidence_id,
                "run_id": run.id,
                "step_id": step_id,
                "type": "manual_confirmation",
                "name": f"Manual Confirmation Step {step_index}",
                "relative_path": relative_path,
                "mime_type": "application/json",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "metadata_json": metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "provenance": Provenance.UNAVAILABLE,
            })
            pending_results.append({
                "step": step_index,
                "step_id": step_id,
                "status": "pending",
                "description": step.get("description") or f"Step {step_index}",
                "evidence_ids": [evidence_id],
                "provenance": Provenance.UNAVAILABLE.value,
            })
        storage.replace_run_step_results(run.id, pending_results)
        storage.update_run_provenance(run.id, Provenance.UNAVAILABLE)

        # Do not start Playwright or RunManager. Return immediately.
        run_dict = run.model_dump()
        run_dict["app_name"] = target_row.get("name")
        run_dict["pack_name"] = pack_row.get("name")
        run_dict["steps"] = steps
        run_dict["step_results"] = pending_results
        run_dict["provenance"] = Provenance.UNAVAILABLE
        return LiveRunRecord(**run_dict)

    steps, step_case_ids = build_pack_steps(pack_row, storage.list_test_cases(pack_id))

    options = RunOptions(
        watch=body.watch,
        slow_mo_ms=DEFAULT_WATCH_SLOW_MO_MS if body.slow_mo_ms is None else body.slow_mo_ms,
        continuous=body.continuous,
        case_ids=tuple(step_case_ids),
    )
    try:
        run_manager.start_run(run.id, steps, target_row, options=options)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    run_dict = run.model_dump()
    run_dict["app_name"] = target_row.get("name")
    run_dict["pack_name"] = pack_row.get("name")
    run_dict["steps"] = steps
    return LiveRunRecord(**run_dict)
