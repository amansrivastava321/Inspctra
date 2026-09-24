"""
settings.py - Product settings CRUD /api/settings

GET   /api/settings        — list all settings (key-value)
GET   /api/settings/{key}  — get one setting
PATCH /api/settings/{key}  — set one setting value

Security:
- Key allowlist: only known setting keys can be written.
- Values are plain strings. No credential values stored here.
- Credential-pattern keys are rejected.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import ProductSetting, SettingUpdate
from qa_ai.product_backend.storage import ProductStorage

router = APIRouter(tags=["settings"])

# Allowlist of valid setting keys — prevents arbitrary key injection
_ALLOWED_SETTING_KEYS = frozenset({
    "artifacts_dir",
    "default_timeout_seconds",
    "run_concurrency_limit",
    "log_level",
    "dashboard_title",
    "enable_runtime_doctor",
    "auto_index_artifacts",
    "theme",
})

# Reject keys that sound like credentials
_CREDENTIAL_KEY_RE = re.compile(
    r"(?i)(password|token|secret|api_key|bearer|auth|credential|private_key)"
)


def _validate_key(key: str) -> None:
    if key not in _ALLOWED_SETTING_KEYS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown setting key: {key!r}. Allowed: {sorted(_ALLOWED_SETTING_KEYS)}",
        )
    if _CREDENTIAL_KEY_RE.search(key):
        raise HTTPException(
            status_code=422,
            detail="Credential-pattern keys are not allowed in settings.",
        )


@router.get("/settings", response_model=List[ProductSetting])
def list_settings(storage: ProductStorage = Depends(get_storage)) -> List[ProductSetting]:
    return [ProductSetting(**r) for r in storage.list_settings()]


@router.get("/settings/{key}", response_model=ProductSetting)
def get_setting(key: str, storage: ProductStorage = Depends(get_storage)) -> ProductSetting:
    _validate_key(key)
    value = storage.get_setting(key)
    if value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Setting {key!r} not set.")
    from qa_ai.product_backend.models import _now_iso
    return ProductSetting(key=key, value=value)


@router.patch("/settings/{key}", response_model=ProductSetting)
def set_setting(
    key: str,
    body: SettingUpdate,
    storage: ProductStorage = Depends(get_storage),
) -> ProductSetting:
    _validate_key(key)
    storage.set_setting(key, body.value)
    from qa_ai.product_backend.models import _now_iso
    return ProductSetting(key=key, value=body.value)
