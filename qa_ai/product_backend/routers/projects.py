"""
projects.py - CRUD /api/projects
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import Provenance, Project, ProjectCreate, ProjectUpdate
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=List[Project])
def list_projects(storage: ProductStorage = Depends(get_storage)) -> List[Project]:
    return [Project(**r) for r in storage.list_projects()]


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    storage: ProductStorage = Depends(get_storage),
) -> Project:
    rec = Project(
        name=body.name,
        description=body.description,
        tags=body.tags,
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_project(rec.model_dump())
    return rec


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str, storage: ProductStorage = Depends(get_storage)) -> Project:
    row = storage.get_project(project_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return Project(**row)


@router.patch("/projects/{project_id}", response_model=Project)
def update_project(
    project_id: str,
    body: ProjectUpdate,
    storage: ProductStorage = Depends(get_storage),
) -> Project:
    row = storage.get_project(project_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    updated = storage.update_project(project_id, body.model_dump(exclude_none=True))
    return Project(**(updated or row))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> None:
    if not storage.get_project(project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    app_count = storage.count_apps_for_project(project_id)
    pack_count = storage.count_packs_for_project(project_id)
    if app_count + pack_count > 0:
        parts = []
        if app_count:
            parts.append(f"{app_count} app{'s' if app_count != 1 else ''}")
        if pack_count:
            parts.append(f"{pack_count} pack{'s' if pack_count != 1 else ''}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete project: it has {' and '.join(parts)}. Delete them first.",
        )
    storage.delete_project(project_id)
