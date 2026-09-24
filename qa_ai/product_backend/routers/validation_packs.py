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
from qa_ai.product_backend.models import (
    LiveRunRecord,
    Provenance,
    StartRunRequest,
    ValidationPack,
    ValidationPackCreate,
    ValidationPackUpdate,
)
from qa_ai.product_backend.run_manager import RunManager
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.routers.live_runs import extract_run_steps

router = APIRouter(tags=["validation-packs"])


@router.get("/validation-packs", response_model=List[ValidationPack])
def list_packs(
    project_id: Optional[str] = Query(default=None),
    app_id: Optional[str] = Query(default=None),
    storage: ProductStorage = Depends(get_storage),
) -> List[ValidationPack]:
    return [
        ValidationPack(**r)
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
    return ValidationPack(**row)


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
    if "schedule" in fields or "schedule_enabled" in fields:
        sched = _get_scheduler(request)
        if sched is not None:
            result = updated or row
            sched.notify_schedule_changed(
                pack_id,
                schedule=result.get("schedule"),
                enabled=bool(result.get("schedule_enabled")),
            )

    return ValidationPack(**(updated or row))


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

    cases = storage.list_test_cases(pack_id)
    enabled_cases = [c for c in cases if c.get("enabled")]

    if enabled_cases:
        steps = []
        for case in enabled_cases:
            test_steps = sorted(case.get("test_steps") or [], key=lambda s: s.get("step_order", 0))
            for t_step in test_steps:
                target_label = t_step.get("url") or t_step.get("target") or ""
                method = t_step.get("method")
                action_type = t_step.get("action_type")
                steps.append({
                    "step_id": t_step.get("step_id", ""),
                    "action_type": action_type,
                    "target": t_step.get("target"),
                    "value": t_step.get("value"),
                    "expected": t_step.get("expected"),
                    "input_value": t_step.get("value") or t_step.get("expected") or "",
                    "timeout_seconds": (t_step.get("timeout_ms") or 30000) / 1000,
                    "optional": bool(t_step.get("optional")),
                    "method": method,
                    "url": t_step.get("url"),
                    "headers": t_step.get("headers") or {},
                    "query_params": t_step.get("query_params") or {},
                    "body_json": t_step.get("body_json"),
                    "expected_status": t_step.get("expected_status"),
                    "expected_json_path": t_step.get("expected_json_path"),
                    "expected_value": t_step.get("expected_value"),
                    "budget_ms": t_step.get("budget_ms"),
                    "warn_ms": t_step.get("warn_ms"),
                    "metric_name": t_step.get("metric_name"),
                    "description": f"[{case.get('title') or 'Case'}] {method + ' ' if method else ''}{action_type} {target_label}".strip(),
                })
    else:
        steps = pack_row.get("steps") or []

    try:
        run_manager.start_run(run.id, steps, target_row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    run_dict = run.model_dump()
    run_dict["app_name"] = target_row.get("name")
    run_dict["pack_name"] = pack_row.get("name")
    run_dict["steps"] = steps
    return LiveRunRecord(**run_dict)
