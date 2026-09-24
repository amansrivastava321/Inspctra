"""
permissions.py - Permission approval workflow /api/permissions

GET  /api/permissions              — list (filter by run_id or status)
GET  /api/permissions/{id}         — get one
POST /api/permissions/{id}/approve — approve
POST /api/permissions/{id}/deny    — deny
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import PermissionDecision, PermissionRecord
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["permissions"])


@router.get("/permissions", response_model=List[PermissionRecord])
def list_permissions(
    run_id: Optional[str] = Query(default=None),
    perm_status: Optional[str] = Query(default=None, alias="status"),
    storage: ProductStorage = Depends(get_storage),
) -> List[PermissionRecord]:
    return [
        PermissionRecord(**r)
        for r in storage.list_permissions(run_id=run_id, status=perm_status)
    ]


@router.get("/permissions/{perm_id}", response_model=PermissionRecord)
def get_permission(
    perm_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> PermissionRecord:
    row = storage.get_permission(perm_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")
    return PermissionRecord(**row)


@router.post("/permissions/{perm_id}/approve", response_model=PermissionRecord)
def approve_permission(
    perm_id: str,
    body: PermissionDecision = Body(default=PermissionDecision(approved=True)),
    storage: ProductStorage = Depends(get_storage),
) -> PermissionRecord:
    row = storage.get_permission(perm_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")
    if row.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission already resolved: {row.get('status')}",
        )
    updated = storage.resolve_permission(perm_id, approved=True, reason=body.reason)
    return PermissionRecord(**(updated or row))


@router.post("/permissions/{perm_id}/deny", response_model=PermissionRecord)
def deny_permission(
    perm_id: str,
    body: PermissionDecision = Body(default=PermissionDecision(approved=False)),
    storage: ProductStorage = Depends(get_storage),
) -> PermissionRecord:
    row = storage.get_permission(perm_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")
    if row.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission already resolved: {row.get('status')}",
        )
    updated = storage.resolve_permission(perm_id, approved=False, reason=body.reason)
    return PermissionRecord(**(updated or row))


@router.post("/permissions/{perm_id}/approve-session", response_model=PermissionRecord)
def approve_permission_session(
    perm_id: str,
    body: PermissionDecision = Body(default=PermissionDecision(approved=True)),
    storage: ProductStorage = Depends(get_storage),
) -> PermissionRecord:
    """
    Approve permission for the remainder of the session.
    Stored identically to a one-time approve — the caller tracks session scope.
    """
    row = storage.get_permission(perm_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")
    if row.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission already resolved: {row.get('status')}",
        )
    updated = storage.resolve_permission(
        perm_id, approved=True,
        reason=(body.reason or "") + " [session]",
    )
    return PermissionRecord(**(updated or row))


@router.post("/permissions/{perm_id}/skip", response_model=PermissionRecord)
def skip_permission(
    perm_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> PermissionRecord:
    """
    Skip (dismiss) a pending permission without approving or denying.
    The run continues; the action that required permission is not executed.
    """
    row = storage.get_permission(perm_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")
    if row.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission already resolved: {row.get('status')}",
        )
    updated = storage.resolve_permission(perm_id, approved=False, reason="skipped")
    return PermissionRecord(**(updated or row))
