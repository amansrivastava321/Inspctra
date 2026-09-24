"""
routes.py - FastAPI route definitions for the Inspectra local dashboard.

All routes are read-only except explicit Corpus integration authorization actions.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from integrations.corpus_connection import CorpusConnectionManager
from qa_ai.webapp.artifact_api import ArtifactAPI
from qa_ai.webapp.dashboard_builder import DashboardBuilder

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_corpus_manager() -> CorpusConnectionManager:
    return CorpusConnectionManager(
        app_name="inspectra",
        app_version="1.0.0",
        workspace_name="AI Engineering Workspace",
        capabilities=["EMIT_SIGNALS", "RECEIVE_SIGNALS", "RESPOND_CHECKPOINT"],
        permissions=["EMIT_SIGNALS", "RECEIVE_SIGNALS", "RESPOND_CHECKPOINT"],
    )


class CorpusTokenPayload(BaseModel):
    token: str
    expires_at: str | None = None
    scopes: list[str] = Field(default_factory=list)
    workspace_id: str


def build_router(api: ArtifactAPI) -> APIRouter:
    """Return a fully-configured router bound to *api*."""
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DashboardBuilder(api).build()

    @router.get("/health")
    async def health() -> Dict[str, Any]:
        stats = api.get_store_stats()
        return {"status": "ok", "artifacts_dir": stats.get("artifacts_dir", ""), **stats}

    # ── corpus integration routes ────────────────────────────────────────────

    @router.get("/api/corpus/runtime")
    async def corpus_runtime() -> Dict[str, Any]:
        manager = _get_corpus_manager()
        return manager.detect_runtime(allow_launch=False)

    @router.get("/api/corpus/status")
    @router.get("/api/integrations/corpus/status")
    async def corpus_status() -> Dict[str, Any]:
        manager = _get_corpus_manager()
        return manager.get_status().to_dict()

    @router.post("/api/corpus/request")
    @router.post("/api/integrations/corpus/request-connection")
    async def corpus_request() -> Dict[str, Any]:
        manager = _get_corpus_manager()
        return manager.request_connection()

    @router.post("/api/integrations/corpus/check-approval")
    async def corpus_check_approval() -> Dict[str, Any]:
        manager = _get_corpus_manager()
        return manager.get_status().to_dict()

    @router.post("/api/corpus/token")
    async def corpus_store_token(payload: CorpusTokenPayload) -> Dict[str, Any]:
        manager = _get_corpus_manager()
        manager.store_approved_token(
            token_value=payload.token,
            expires_at=payload.expires_at,
            scopes=payload.scopes,
            workspace_id=payload.workspace_id,
        )
        return {"stored": True}

    @router.post("/api/corpus/reconnect")
    @router.post("/api/integrations/corpus/reconnect")
    async def corpus_reconnect() -> Dict[str, Any]:
        manager = _get_corpus_manager()
        return {"connected": manager.reconnect_with_saved_token()}

    @router.post("/api/corpus/disconnect")
    @router.post("/api/integrations/corpus/disconnect")
    async def corpus_disconnect() -> Dict[str, Any]:
        manager = _get_corpus_manager()
        return {"disconnected": manager.disconnect()}

    @router.get("/settings/integrations/corpus", response_class=HTMLResponse)
    async def corpus_settings() -> str:
        manager = _get_corpus_manager()
        state = manager.get_status().to_dict().get("state", "disconnected")
        label = {
            "connected": "Connected",
            "pending_approval": "Pending Approval",
            "denied": "Connect to Corpus",
            "disconnected": "Connect to Corpus",
        }.get(str(state), "Connect to Corpus")
        return (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<title>Inspectra — Corpus Integration</title></head><body>"
            "<main><h1>Corpus Integration</h1>"
            f"<p>{label}</p>"
            "<p>Corpus connections require workspace approval before any signals are exchanged.</p>"
            "<a href='/'>Back to dashboard</a></main></body></html>"
        )

    # ── artifact routes ───────────────────────────────────────────────────────

    @router.get("/api/artifacts")
    async def list_artifacts() -> List[Dict[str, Any]]:
        return api.list_artifacts()

    @router.get("/api/artifacts/{name:path}")
    async def get_artifact(name: str) -> Any:
        data = api.get_artifact(name)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Artifact '{name}' not found")
        return data

    # ── summary / findings ────────────────────────────────────────────────────

    @router.get("/api/summary")
    async def get_summary() -> Dict[str, Any]:
        return api.get_summary() or {}

    @router.get("/api/findings")
    async def get_findings() -> List[Dict[str, Any]]:
        return api.get_findings()

    # ── analysis artifacts ────────────────────────────────────────────────────

    @router.get("/api/risk")
    async def get_risk() -> Dict[str, Any]:
        return api.get_risk() or {}

    @router.get("/api/remediation")
    async def get_remediation() -> Dict[str, Any]:
        return api.get_remediation() or {}

    @router.get("/api/benchmarks")
    async def get_benchmarks() -> Dict[str, Any]:
        return api.get_benchmarks() or {}

    @router.get("/api/cicd")
    async def get_cicd() -> Dict[str, Any]:
        return api.get_cicd() or {}

    @router.get("/api/self-optimization")
    async def get_self_optimization() -> Dict[str, Any]:
        return api.get_self_optimization() or {}

    # ── reports / evidence ────────────────────────────────────────────────────

    @router.get("/api/reports")
    async def list_reports() -> List[str]:
        return api.list_reports()

    @router.get("/api/evidence")
    async def list_evidence() -> List[str]:
        return api.list_evidence()

    return router
