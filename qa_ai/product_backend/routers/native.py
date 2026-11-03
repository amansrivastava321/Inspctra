"""
native.py - what desktop and mobile app testing needs, and the user's permission to do it.

GET    /api/native/{platform}/readiness                          what is installed / allowed, and the saved consent
POST   /api/native/{platform}/permissions/{requirement}/request   ask the OS (shows its prompt / opens its settings)
PUT    /api/native/{platform}/consent                             the user allows Inspectra to drive apps there
DELETE /api/native/{platform}/consent                             take that permission back

Inspectra never drives a desktop app, an emulator or a simulator until the user has allowed it here, and
scheduled (unattended) runs only do so when the user also allowed that.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from qa_ai.native_execution import CONSENT_SCOPES, NATIVE_PLATFORMS, PLATFORM_LABELS, NativeEngineError, engine_for
from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["native"])


class ConsentRequest(BaseModel):
    scopes: List[str] = Field(default_factory=list)
    unattended: bool = False  # also allow scheduled runs to do this while nobody is watching


def native_engine_factory(request: Request):
    """The engine factory (tests swap in fakes through app.state.native_engine_factory)."""
    return getattr(request.app.state, "native_engine_factory", None) or engine_for


def _platform(platform: str) -> str:
    if platform not in NATIVE_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown platform. Use one of: {', '.join(NATIVE_PLATFORMS)}.",
        )
    return platform


def consent_is_complete(consent: Any, platform: str) -> bool:
    if not consent:
        return False
    required = {s["id"] for s in CONSENT_SCOPES[platform]}
    return required.issubset(set(consent.get("scopes") or []))


def readiness_payload(platform: str, storage: ProductStorage, factory: Any) -> Dict[str, Any]:
    engine = factory(platform)
    try:
        requirements = [r.to_dict() for r in engine.requirements()]
    except NativeEngineError as exc:
        requirements = [{"id": "tools", "label": "Platform tools", "status": "missing", "how_to_fix": str(exc),
                         "can_request": False, "optional": False}]
    consent = storage.get_native_consent(platform)
    missing = [r for r in requirements if r["status"] == "missing" and not r["optional"]]
    allowed = consent_is_complete(consent, platform)
    return {
        "platform": platform,
        "label": PLATFORM_LABELS[platform],
        "requirements": requirements,
        "tools_ready": not missing,
        "consent": consent if allowed else None,
        "consent_scopes": CONSENT_SCOPES[platform],
        "ready": not missing and allowed,
    }


@router.get("/native/{platform}/readiness")
def readiness(
    platform: str,
    storage: ProductStorage = Depends(get_storage),
    factory: Any = Depends(native_engine_factory),
) -> Dict[str, Any]:
    return readiness_payload(_platform(platform), storage, factory)


@router.post("/native/{platform}/permissions/{requirement_id}/request")
def request_permission(
    platform: str,
    requirement_id: str,
    storage: ProductStorage = Depends(get_storage),
    factory: Any = Depends(native_engine_factory),
) -> Dict[str, Any]:
    engine = factory(_platform(platform))
    try:
        asked = engine.request(requirement_id)
    except NativeEngineError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not asked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspectra cannot ask for this one; follow the steps shown next to it.",
        )
    return {"requested": True, **readiness_payload(platform, storage, factory)}


@router.put("/native/{platform}/consent")
def give_consent(
    platform: str,
    body: ConsentRequest,
    storage: ProductStorage = Depends(get_storage),
) -> Dict[str, Any]:
    platform = _platform(platform)
    required = {s["id"] for s in CONSENT_SCOPES[platform]}
    unknown = set(body.scopes) - required
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown permission: {', '.join(sorted(unknown))}.")
    if not required.issubset(body.scopes):
        missing = sorted(required - set(body.scopes))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All of these are needed to test {PLATFORM_LABELS[platform]}s: {', '.join(missing)}.",
        )
    return storage.set_native_consent(platform, list(body.scopes), body.unattended)


@router.delete("/native/{platform}/consent", status_code=status.HTTP_204_NO_CONTENT)
def revoke_consent(platform: str, storage: ProductStorage = Depends(get_storage)) -> Response:
    storage.delete_native_consent(_platform(platform))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
