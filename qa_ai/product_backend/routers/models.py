"""
routers/models.py - Model provider and routing management API.

Endpoints:
  GET    /api/models/providers
  POST   /api/models/providers
  GET    /api/models/providers/{provider_id}
  PATCH  /api/models/providers/{provider_id}
  DELETE /api/models/providers/{provider_id}
  POST   /api/models/providers/{provider_id}/test
  GET    /api/models/routes
  PATCH  /api/models/routes/{route_id}
  GET    /api/models/health
  POST   /api/models/benchmark
  GET    /api/models/usage

Security:
- Never returns raw API key values.
- Provider URL validated (no SSRF).
- Cloud provider test requires explicit approval token.
- No shell. No subprocess. No eval.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from qa_ai.product_backend.models import (
    ModelProviderCreate,
    ModelProviderRecord,
    ModelProviderUpdate,
    ModelRouteRecord,
    ModelRouteUpdate,
    ModelUsageEvent,
    ModelHealthResponse,
    Provenance,
    ProviderTestRequest,
    ProviderTestResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["models"])


def _storage(request: Request):
    return request.app.state.storage


def _provider_to_record(row: Dict[str, Any], *, check_key: bool = True) -> ModelProviderRecord:
    """Convert storage row → ModelProviderRecord.  Never exposes raw key values."""
    import json as _json
    api_key_configured = False
    if check_key and row.get("api_key_env"):
        import os
        api_key_configured = bool(os.environ.get(str(row["api_key_env"]), "").strip())

    meta = row.get("metadata", "{}")
    if isinstance(meta, str):
        try:
            meta = _json.loads(meta)
        except (ValueError, TypeError):
            meta = {}

    return ModelProviderRecord(
        provider_id=row["provider_id"],
        provider_type=row["provider_type"],
        name=row["name"],
        enabled=bool(row.get("enabled", 0)),
        base_url=row.get("base_url"),
        api_key_env=row.get("api_key_env"),  # env var name only — safe to return
        secret_ref=row.get("secret_ref"),
        allow_cloud=bool(row.get("allow_cloud", 0)),
        local_only=bool(row.get("local_only", 1)),
        metadata=meta,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        api_key_configured=api_key_configured,
    )


def _route_to_record(row: Dict[str, Any]) -> ModelRouteRecord:
    import json as _json
    fb = row.get("fallback_models", "[]")
    if isinstance(fb, str):
        try:
            fb = _json.loads(fb)
        except (ValueError, TypeError):
            fb = []
    return ModelRouteRecord(
        id=row["id"],
        task=row["task"],
        provider_id=row["provider_id"],
        model=row["model"],
        priority=int(row.get("priority", 1)),
        enabled=bool(row.get("enabled", 1)),
        fallback_models=list(fb),
        temperature=float(row.get("temperature", 0.1)),
        timeout_seconds=int(row.get("timeout_seconds", 60)),
        estimated_memory_gb=float(row.get("estimated_memory_gb", 4.0)),
        local_only=bool(row.get("local_only", 1)),
        requires_approval=bool(row.get("requires_approval", 0)),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ── Provider CRUD ──────────────────────────────────────────────────────────────

@router.get("/models/providers", response_model=List[ModelProviderRecord])
def list_providers(request: Request):
    rows = _storage(request).list_model_providers()
    return [_provider_to_record(r) for r in rows]


@router.post("/models/providers", response_model=ModelProviderRecord, status_code=201)
def create_provider(body: ModelProviderCreate, request: Request):
    existing = _storage(request).get_model_provider(body.provider_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Provider already exists: {body.provider_id!r}")
    row = _storage(request).create_model_provider(body.model_dump())
    return _provider_to_record(row)


@router.get("/models/providers/{provider_id}", response_model=ModelProviderRecord)
def get_provider(provider_id: str, request: Request):
    row = _storage(request).get_model_provider(provider_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id!r}")
    return _provider_to_record(row)


@router.patch("/models/providers/{provider_id}", response_model=ModelProviderRecord)
def update_provider(provider_id: str, body: ModelProviderUpdate, request: Request):
    row = _storage(request).get_model_provider(provider_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id!r}")
    updated = _storage(request).update_model_provider(
        provider_id, body.model_dump(exclude_none=True)
    )
    return _provider_to_record(updated or row)


@router.delete("/models/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: str, request: Request):
    deleted = _storage(request).delete_model_provider(provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id!r}")


# ── Provider test ──────────────────────────────────────────────────────────────

@router.post("/models/providers/{provider_id}/test", response_model=ProviderTestResult)
def test_provider(provider_id: str, body: ProviderTestRequest, request: Request):
    """
    Test provider connectivity.

    Local Ollama: sends tiny probe to /api/tags — no model loaded, no prompt sent.
    Cloud provider: requires approval_token — currently returns capability_gap.
    """
    row = _storage(request).get_model_provider(provider_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id!r}")

    provider_type = row.get("provider_type", "")
    allow_cloud = bool(row.get("allow_cloud", 0))

    # Cloud provider: always require approval
    if allow_cloud and not row.get("local_only", 1):
        if not body.approval_token:
            return ProviderTestResult(
                provider_id=provider_id,
                success=False,
                error=(
                    "Cloud provider test requires explicit approval. "
                    "Provide approval_token to proceed. "
                    "Note: a minimal test prompt will be sent to the provider."
                ),
                cloud_call=True,
                approved=False,
            )

    # Local Ollama test: just check /api/tags — no model call, no data sent
    if provider_type == "ollama":
        base_url = (row.get("base_url") or "http://127.0.0.1:11434").rstrip("/")
        start = time.time()
        try:
            import json
            import urllib.request
            req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            latency_ms = (time.time() - start) * 1000
            model_count = len(data.get("models", []))
            return ProviderTestResult(
                provider_id=provider_id,
                success=True,
                latency_ms=round(latency_ms, 1),
                model_used=None,
                error=None,
                cloud_call=False,
                approved=True,
            )
        except Exception as exc:
            return ProviderTestResult(
                provider_id=provider_id,
                success=False,
                latency_ms=(time.time() - start) * 1000,
                error=f"Ollama not reachable at {base_url}: {exc}",
                cloud_call=False,
                approved=True,
            )

    # Other local providers
    return ProviderTestResult(
        provider_id=provider_id,
        success=False,
        error=f"Test not implemented for provider_type={provider_type!r}. Use Ollama or check manually.",
        cloud_call=allow_cloud,
        approved=False,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/models/routes", response_model=List[ModelRouteRecord])
def list_routes(request: Request):
    rows = _storage(request).list_model_routes()
    return [_route_to_record(r) for r in rows]


@router.patch("/models/routes/{route_id}", response_model=ModelRouteRecord)
def update_route(route_id: str, body: ModelRouteUpdate, request: Request):
    row = _storage(request).get_model_route(route_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Route not found: {route_id!r}")
    updated = _storage(request).upsert_model_route({
        **row,
        **body.model_dump(exclude_none=True),
        "id": route_id,
    })
    return _route_to_record(updated or row)


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/models/health", response_model=ModelHealthResponse)
def model_health(request: Request) -> Dict[str, Any]:
    """
    Check Ollama reachability and route coverage.

    Read-only. No model loading.
    """
    try:
        from qa_ai.ai.model_health import build_health_report
        report = build_health_report()
        return {
            "ollama_reachable": report.ollama_reachable,
            "ollama_base_url": report.ollama_base_url,
            "installed_models": report.installed_models,
            "required_models": report.required_models,
            "missing_models": report.missing_models,
            "present_models": report.present_models,
            "route_coverage": [
                {
                    "task": r.task,
                    "primary_model": r.primary_model,
                    "primary_available": r.primary_available,
                    "fallback_models": r.fallback_models,
                    "fallback_available": r.fallback_available,
                    "status": r.status,
                    "provenance": Provenance.REAL_EXECUTION.value,
                }
                for r in report.route_coverage
            ],
            "cloud_providers_disabled": report.cloud_providers_disabled,
            "overall_readiness": report.overall_readiness,
            "recommendations": report.recommendations,
            "generated_at": report.generated_at,
            "error": report.error,
            "provenance": Provenance.REAL_EXECUTION.value,
        }
    except Exception as exc:
        logger.warning("model_health endpoint error: %s", exc)
        return {
            "ollama_reachable": False,
            "error": str(exc),
            "overall_readiness": "unavailable",
            "provenance": Provenance.UNAVAILABLE.value,
        }


# ── Benchmark ─────────────────────────────────────────────────────────────────

@router.post("/models/benchmark")
def run_benchmark(
    request: Request,
    quick: bool = True,
    dry_run: bool = True,
    approved: bool = False,
) -> Dict[str, Any]:
    """
    Run latency benchmark.

    approved=True required for real calls.
    dry_run=True (default) returns stub results.
    quick=True (default) skips heavy models.
    """
    try:
        from qa_ai.ai.model_benchmarker import run_benchmark as _bench
        report = _bench(approved=approved, dry_run=dry_run, quick=quick)
        return {
            "generated_at": report.generated_at,
            "approved": report.approved,
            "dry_run": report.dry_run,
            "quick_mode": report.quick_mode,
            "summary": report.summary,
            "entries": [
                {
                    "model": e.model,
                    "task": e.task,
                    "latency_ms": e.latency_ms,
                    "status": e.status,
                    "error": e.error,
                    "recommendation": e.recommendation,
                }
                for e in report.entries
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Benchmark error: {exc}")


# ── Usage ─────────────────────────────────────────────────────────────────────

@router.get("/models/usage", response_model=List[ModelUsageEvent])
def list_usage(request: Request, limit: int = 100):
    rows = _storage(request).list_model_usage(limit=min(limit, 500))
    return [ModelUsageEvent(**r) for r in rows]


# ── Adaptive profile endpoints ────────────────────────────────────────────────

@router.get("/models/hardware")
def get_hardware(request: Request) -> Dict[str, Any]:
    """
    Return detected hardware profile for this machine.

    Read-only. No model loading. No secrets.
    Exposes: RAM, platform, arch, GPU type, container flag.
    Does NOT expose: process names, user info, network interfaces.
    """
    try:
        from qa_ai.model_runtime.hardware_detector import detect_hardware
        hw = detect_hardware()
        return {
            "platform": hw.platform,
            "architecture": hw.architecture,
            "total_ram_gb": hw.total_ram_gb,
            "available_ram_gb": hw.available_ram_gb,
            "apple_silicon": hw.apple_silicon,
            "cuda_available": hw.cuda_available,
            "metal_available": hw.metal_available,
            "gpu_label": hw.gpu_label,
            "inside_container": hw.inside_container,
            "recommended_profile": hw.recommended_profile,
            "detection_confidence": hw.detection_confidence,
            "warnings": hw.warnings,
        }
    except Exception as exc:
        logger.warning("hardware detection error: %s", exc)
        return {"error": str(exc), "recommended_profile": "mac_m4_16gb"}


@router.get("/models/profiles")
def list_profiles(request: Request) -> Dict[str, Any]:
    """
    Return all available adaptive resource profiles.
    """
    try:
        from qa_ai.model_runtime.adaptive_profiles import get_all_profiles
        profiles = get_all_profiles()
        return {
            "profiles": [
                {
                    "profile_id": p.profile_id,
                    "name": p.name,
                    "description": p.description,
                    "min_ram_gb": p.min_ram_gb,
                    "max_ram_gb": p.max_ram_gb,
                    "max_parallel_model_calls": p.max_parallel_model_calls,
                    "max_model_memory_gb": p.max_model_memory_gb,
                    "allow_heavy_models": p.allow_heavy_models,
                    "vision_enabled_by_default": p.vision_enabled_by_default,
                    "notes": p.notes,
                }
                for p in profiles.values()
            ]
        }
    except Exception as exc:
        logger.warning("profiles error: %s", exc)
        return {"error": str(exc), "profiles": []}


@router.get("/models/profile/current")
def get_current_profile(request: Request) -> Dict[str, Any]:
    """
    Auto-detect hardware and return the recommended profile + per-task routes.

    Read-only. No model loading. No secrets.
    """
    try:
        from qa_ai.model_runtime.profile_selector import select_profile
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        selected = select_profile()
        return build_profile_report(selected)
    except Exception as exc:
        logger.warning("profile/current error: %s", exc)
        return {"error": str(exc), "profile_id": "mac_m4_16gb"}


@router.post("/models/profile/select")
def select_profile_endpoint(
    request: Request,
    profile_id: str,
) -> Dict[str, Any]:
    """
    Apply a specific profile. Returns recommended routes for that profile.

    Does not persist — use /profile/apply-recommended to write settings.
    """
    try:
        from qa_ai.model_runtime.adaptive_profiles import get_profile_by_id
        from qa_ai.model_runtime.profile_selector import select_profile
        from qa_ai.model_runtime.profile_reporter import build_profile_report

        if get_profile_by_id(profile_id) is None:
            from qa_ai.model_runtime.adaptive_profiles import get_all_profiles
            valid = list(get_all_profiles().keys())
            raise HTTPException(status_code=400,
                                detail=f"Unknown profile_id: {profile_id!r}. Valid: {valid}")

        selected = select_profile(profile_override=profile_id)
        return build_profile_report(selected)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/models/profile/auto-detect")
def auto_detect_profile(request: Request) -> Dict[str, Any]:
    """
    Re-run hardware detection and return the auto-selected profile.
    """
    try:
        from qa_ai.model_runtime.profile_selector import select_profile
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        selected = select_profile()
        return build_profile_report(selected)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/models/discovered-providers")
def discovered_providers(
    request: Request,
    probe_lmstudio: bool = True,
    probe_llamacpp: bool = True,
) -> Dict[str, Any]:
    """
    Discover locally running LLM providers.

    Probes localhost only. No cloud calls. No auth tokens sent.
    Returns reachable providers and their installed models.
    """
    try:
        from qa_ai.model_runtime.provider_discovery import discover_providers
        providers = discover_providers(
            probe_lmstudio=probe_lmstudio,
            probe_llamacpp=probe_llamacpp,
            probe_vllm=False,
        )
        return {
            "providers": [
                {
                    "provider_id": p.provider_id,
                    "provider_type": p.provider_type,
                    "base_url": p.base_url,
                    "reachable": p.reachable,
                    "model_count": len(p.models),
                    "models": p.models[:50],   # cap at 50
                    "local_only": p.local_only,
                    "warnings": p.warnings,
                }
                for p in providers
            ]
        }
    except Exception as exc:
        logger.warning("provider discovery error: %s", exc)
        return {"error": str(exc), "providers": []}


@router.post("/models/providers/discover")
def trigger_provider_discovery(request: Request) -> Dict[str, Any]:
    """Alias for GET /models/discovered-providers (POST-friendly for UIs)."""
    return discovered_providers(request)


@router.post("/models/routes/recommend")
def recommend_routes(
    request: Request,
    profile_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return recommended model routes for the given (or auto-detected) profile.

    Does not apply them — use apply-recommended to write.
    """
    try:
        from qa_ai.model_runtime.profile_selector import select_profile
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        selected = select_profile(profile_override=profile_id)
        report = build_profile_report(selected)
        return {
            "profile_id": selected.selected_profile.profile_id,
            "recommended_routes": report["task_routes"],
            "available_models": report["available_models"],
            "missing_models": report["missing_models"],
            "warnings": report["warnings"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/models/routes/apply-recommended")
def apply_recommended_routes(
    request: Request,
    profile_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute recommended routes and upsert them into the model_routes storage table.

    Cloud-enabled routes blocked — only local Ollama routes written.
    """
    try:
        from qa_ai.model_runtime.profile_selector import select_profile
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        import uuid
        from datetime import datetime, timezone

        selected = select_profile(profile_override=profile_id)
        storage = _storage(request)
        applied: List[str] = []
        skipped: List[str] = []

        now = datetime.now(timezone.utc).isoformat()

        for task, dec in selected.task_routes.items():
            if dec.capability_gap or dec.model is None:
                skipped.append(task)
                continue
            row = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"route-{task}")),
                "task": task,
                "provider_id": "ollama_local",
                "model": dec.model,
                "priority": 1,
                "enabled": 1,
                "fallback_models": dec.fallback_models,
                "temperature": 0.1,
                "timeout_seconds": 90,
                "estimated_memory_gb": dec.estimated_memory_gb,
                "local_only": 1,
                "requires_approval": 0,
                "created_at": now,
                "updated_at": now,
            }
            try:
                storage.upsert_model_route(row)
                applied.append(task)
            except Exception as e:
                logger.warning("Failed to upsert route for %s: %s", task, e)
                skipped.append(task)

        return {
            "status": "ok",
            "profile_id": selected.selected_profile.profile_id,
            "applied_tasks": applied,
            "skipped_tasks": skipped,
            "warnings": selected.warnings,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
