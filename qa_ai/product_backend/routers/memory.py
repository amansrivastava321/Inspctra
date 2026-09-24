"""
memory.py - Memory Kernel REST API

GET  /api/memory/scopes/{scope_id}           — scope overview
GET  /api/memory/scopes/{scope_id}/stats     — stats
GET  /api/memory/scopes/{scope_id}/report    — markdown/json report
GET  /api/memory/scopes/{scope_id}/patterns  — patterns
GET  /api/memory/scopes/{scope_id}/baseline  — active baseline
POST /api/memory/scopes/{scope_id}/baseline  — create/promote baseline
POST /api/memory/scopes/{scope_id}/ingest    — ingest run
POST /api/memory/scopes/{scope_id}/recall    — semantic recall
GET  /api/memory/scopes/{scope_id}/retention — retention preview
POST /api/memory/scopes/{scope_id}/retention — execute retention (dry_run param)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["memory"])


# ── Request/response models ────────────────────────────────────────────────────

class IngestRunRequest(BaseModel):
    run_id: str
    run_type: str = "regression"
    verdict: str = "unknown"
    step_count: int = 0
    timing_ms: float = 0.0
    failures: List[str] = Field(default_factory=list)
    evidence_fingerprints: List[str] = Field(default_factory=list)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "medium"
    auto_update_baseline: bool = False


class RecallRequest(BaseModel):
    query: str = Field(max_length=10_000)
    source_types: Optional[List[str]] = None
    top_k: int = Field(default=10, ge=1, le=50)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)


class CreateBaselineRequest(BaseModel):
    run_id: str
    run_type: str = "regression"
    notes: str = ""
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    promote: bool = True


class RetentionRequest(BaseModel):
    dry_run: bool = True
    max_delete_per_run: int = Field(default=500, ge=1, le=5000)


def _get_service():
    """Lazy-init MemoryAPIService singleton."""
    from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
    return MemoryAPIService()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/memory/scopes/{scope_id}")
def get_scope(scope_id: str) -> Dict[str, Any]:
    svc = _get_service()
    scope = svc.get_scope(scope_id)
    if scope is None:
        raise HTTPException(status_code=404, detail=f"Scope {scope_id!r} not found")
    return {"status": "ok", "scope": scope}


@router.get("/memory/scopes/{scope_id}/stats")
def get_stats(scope_id: str) -> Dict[str, Any]:
    svc = _get_service()
    return {"status": "ok", "stats": svc.stats(scope_id)}


@router.get("/memory/scopes/{scope_id}/report")
def get_report(
    scope_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|json)$"),
) -> Dict[str, Any]:
    svc = _get_service()
    report = svc.scope_report(scope_id=scope_id, format=format)
    return {"status": "ok", "format": format, "report": report}


@router.get("/memory/scopes/{scope_id}/patterns")
def get_patterns(
    scope_id: str,
    pattern_type: Optional[str] = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
) -> Dict[str, Any]:
    svc = _get_service()
    return svc.get_patterns(
        scope_id=scope_id,
        pattern_type=pattern_type,
        min_confidence=min_confidence,
        limit=limit,
    )


@router.get("/memory/scopes/{scope_id}/baseline")
def get_baseline(scope_id: str) -> Dict[str, Any]:
    svc = _get_service()
    baseline = svc.get_active_baseline(scope_id=scope_id)
    return {"status": "ok", "baseline": baseline}


@router.post("/memory/scopes/{scope_id}/baseline", status_code=status.HTTP_201_CREATED)
def create_baseline(scope_id: str, req: CreateBaselineRequest) -> Dict[str, Any]:
    svc = _get_service()
    result = svc.create_baseline(
        scope_id=scope_id,
        run_id=req.run_id,
        run_type=req.run_type,
        artifacts=req.artifacts,
        notes=req.notes,
    )
    if result.get("status") != "ok":
        raise HTTPException(status_code=500, detail="Failed to create baseline")
    if req.promote and result.get("baseline_id"):
        svc.promote_baseline(
            baseline_id=result["baseline_id"],
            scope_id=scope_id,
        )
    return result


@router.post("/memory/scopes/{scope_id}/ingest")
def ingest_run(scope_id: str, req: IngestRunRequest) -> Dict[str, Any]:
    svc = _get_service()
    current_run = {
        "run_id": req.run_id,
        "verdict": req.verdict,
        "step_count": req.step_count,
        "timing_ms": req.timing_ms,
        "failures": req.failures,
        "evidence_fingerprints": req.evidence_fingerprints,
        **req.artifacts,
    }
    return svc.ingest_run(
        scope_id=scope_id,
        run_id=req.run_id,
        run_type=req.run_type,
        current_run=current_run,
        auto_update_baseline=req.auto_update_baseline,
        severity=req.severity,
    )


@router.post("/memory/scopes/{scope_id}/recall")
def recall(scope_id: str, req: RecallRequest) -> Dict[str, Any]:
    svc = _get_service()
    return svc.recall(
        scope_id=scope_id,
        query=req.query,
        source_types=req.source_types,
        top_k=req.top_k,
        min_score=req.min_score,
    )


@router.get("/memory/scopes/{scope_id}/retention")
def retention_preview(scope_id: str) -> Dict[str, Any]:
    svc = _get_service()
    return svc.retention_preview(scope_id=scope_id)


@router.post("/memory/scopes/{scope_id}/retention")
def run_retention(scope_id: str, req: RetentionRequest) -> Dict[str, Any]:
    svc = _get_service()
    return svc.run_retention(
        scope_id=scope_id,
        dry_run=req.dry_run,
        max_delete_per_run=req.max_delete_per_run,
    )
