"""
apps.py - CRUD /api/apps  (AppTarget)
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import AppTarget, AppTargetCreate, AppTargetUpdate, Provenance
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["apps"])


@router.get("/apps", response_model=List[AppTarget])
def list_apps(
    project_id: Optional[str] = Query(default=None, description="Filter by project"),
    storage: ProductStorage = Depends(get_storage),
) -> List[AppTarget]:
    return [AppTarget(**r) for r in storage.list_app_targets(project_id=project_id)]


@router.post("/apps", response_model=AppTarget, status_code=status.HTTP_201_CREATED)
def create_app(
    body: AppTargetCreate,
    storage: ProductStorage = Depends(get_storage),
) -> AppTarget:
    # Ensure project exists
    if storage.get_project(body.project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    rec = AppTarget(
        project_id=body.project_id,
        name=body.name,
        app_type=body.app_type,
        base_url=body.base_url,
        description=body.description,
        tags=body.tags,
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_app_target(rec.model_dump())
    return rec


@router.get("/apps/{app_id}", response_model=AppTarget)
def get_app(app_id: str, storage: ProductStorage = Depends(get_storage)) -> AppTarget:
    row = storage.get_app_target(app_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App target not found.")
    return AppTarget(**row)


@router.patch("/apps/{app_id}", response_model=AppTarget)
def update_app(
    app_id: str,
    body: AppTargetUpdate,
    storage: ProductStorage = Depends(get_storage),
) -> AppTarget:
    row = storage.get_app_target(app_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App target not found.")
    updated = storage.update_app_target(app_id, body.model_dump(exclude_none=True))
    return AppTarget(**(updated or row))


@router.delete("/apps/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app(
    app_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> None:
    if not storage.delete_app_target(app_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App target not found.")
