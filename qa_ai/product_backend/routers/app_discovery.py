"""
app_discovery.py — Routes for app source discovery.

POST /discovery/scan          — run discovery on a source input
GET  /discovery/{id}          — fetch a discovery result
POST /discovery/{id}/create-app — create AppTarget from confirmed discovery result
"""
from fastapi import APIRouter, Depends, HTTPException, status

from qa_ai.product_backend.app_discovery_service import run_discovery
from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.discovery_models import (
    AppCreateFromDiscoveryRequest,
    AppSourceInput,
    DiscoveryResult,
    DiscoveryStatus,
    SourceType,
)
from qa_ai.product_backend.models import AppTarget, Provenance
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["discovery"])


@router.post("/discovery/scan", response_model=DiscoveryResult, status_code=201)
def scan_source(
    body: AppSourceInput,
    storage: ProductStorage = Depends(get_storage),
) -> DiscoveryResult:
    """
    Run discovery scan on provided source input.
    Validates project exists, then runs safe fingerprint scan.
    No shell execution. No secret reads.

    Local folder scans require permission_to_scan=true — user must have
    explicitly checked the permission checkbox in the UI.
    """
    if not storage.get_project(body.project_id):
        raise HTTPException(status_code=404, detail="Project not found.")

    # Gate: local folder scan requires explicit user permission.
    if body.source_type == SourceType.local_folder and not body.permission_to_scan:
        raise HTTPException(
            status_code=422,
            detail=(
                "Local folder scan requires permission_to_scan=true. "
                "The user must check the permission checkbox before scanning."
            ),
        )

    result = run_discovery(body)
    storage.save_discovery_result(result)
    return result


@router.get("/discovery/{discovery_id}", response_model=DiscoveryResult)
def get_discovery(
    discovery_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> DiscoveryResult:
    result = storage.get_discovery_result(discovery_id)
    if not result:
        raise HTTPException(status_code=404, detail="Discovery result not found.")
    return result


@router.post("/discovery/{discovery_id}/create-app", response_model=AppTarget, status_code=201)
def create_app_from_discovery(
    discovery_id: str,
    body: AppCreateFromDiscoveryRequest,
    storage: ProductStorage = Depends(get_storage),
) -> AppTarget:
    """
    Create an AppTarget from a user-confirmed discovery result.
    User must have reviewed and confirmed all values.
    """
    if discovery_id != body.discovery_id:
        raise HTTPException(
            status_code=400,
            detail="discovery_id in path and body must match.",
        )

    result = storage.get_discovery_result(discovery_id)
    if not result:
        raise HTTPException(status_code=404, detail="Discovery result not found.")

    if result.status == DiscoveryStatus.failed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create app from failed discovery: {result.error_message}",
        )

    if not storage.get_project(result.project_id):
        raise HTTPException(status_code=404, detail="Project not found.")

    app = AppTarget(
        project_id=result.project_id,
        name=body.name,
        app_type=body.app_type,
        base_url=body.base_url,
        description=body.description,
        tags=body.tags,
        # Source / discovery fields
        source_type=result.source_type.value,
        source_path=result.local_path,
        source_url=result.url,
        launch_command=body.launch_command,
        working_directory=body.working_directory or result.local_path,
        discovery_id=discovery_id,
        detected_stack=",".join(
            s.value for s in (result.detected_stack or [])
        ) or None,
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_app_target(app.model_dump())
    return app
