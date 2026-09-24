"""
server.py - FastAPI application factory for the Inspectra product backend.

ARCHITECTURE BOUNDARY RULES (enforce strictly):
  ✅ product_backend  → ProductStorage (SQLite)   — ALLOWED
  ✅ product_backend  → ArtifactIndex             — ALLOWED (read-only filesystem scan)
  ❌ product_backend  → ArtifactStore             — FORBIDDEN
  ❌ product_backend  → qa_ai.runtime.*            — FORBIDDEN (CLI/agent pipeline layer)

ProductStorage is the canonical persistent store for the web product backend.
ArtifactStore is for the CLI audit pipeline only (agents, webapp/server.py).
If you need per-run filesystem data in the product backend, use ArtifactIndex instead.

Usage:
    app = create_product_app()
    uvicorn.run(app, host="127.0.0.1", port=8765)

Security:
- CORS restricted to localhost origins only.
- No wildcard origins.
- No external calls on startup.
- No shell=True. No os.system. No eval.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.event_stream import EventStream
from qa_ai.product_backend.run_manager import RunManager
from qa_ai.product_backend.models import HealthResponse, Provenance
from qa_ai.product_backend.scheduler import PackScheduler
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.run_event_recorder import RunEventRecorder
from qa_ai.product_backend.routers import (
    app_discovery as app_discovery_router,
    app_map as app_map_router,
    apps,
    connectors,
    dashboard,
    dev as dev_router,
    evaluations,
    evidence,
    live_runs,
    local_environment as local_environment_router,
    local_folder_search as local_folder_search_router,
    local_picker as local_picker_router,
    memory as memory_router,
    models as models_router,
    permissions,
    projects,
    reports,
    root_causes,
    run_history,
    run_comparison,
    runtime_doctor,
    settings,
    test_plans,
    validation_packs,
    visual_baselines,
)

logger = logging.getLogger(__name__)

# Localhost-only CORS — never allow arbitrary origins
_LOCAL_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",   # Vite dev server
    "http://localhost:5174",
    "http://localhost:8765",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:8765",
]


def create_product_app(
    artifacts_dir: Optional[str] = None,
    db_path: Optional[str] = None,
) -> FastAPI:
    """
    Create and configure the Inspectra product backend FastAPI application.

    All services are initialized once and stored on app.state for
    dependency injection. No module-level globals.
    """
    resolved_artifacts_dir = artifacts_dir or os.getenv("INSPECTRA_ARTIFACTS_DIR", "artifacts")
    artifacts_path = Path(resolved_artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    resolved_db_path = db_path or str(artifacts_path / "inspectra_product.db")

    storage = ProductStorage(db_path=resolved_db_path)
    event_stream = EventStream()
    artifact_index = ArtifactIndex(artifacts_dir=artifacts_path)
    event_recorder = RunEventRecorder(storage=storage)
    run_manager = RunManager(
        event_stream=event_stream,
        storage=storage,
        artifact_index=artifact_index,
        event_recorder=event_recorder,
    )
    scheduler = PackScheduler(storage=storage, run_manager=run_manager)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Wire services into app.state for dependency injection
        app.state.storage = storage
        app.state.event_stream = event_stream
        app.state.run_manager = run_manager
        app.state.run_event_recorder = event_recorder
        app.state.artifact_index = artifact_index
        app.state.scheduler = scheduler
        scheduler.start()
        logger.info(
            "Inspectra product backend started. "
            "artifacts=%s db=%s",
            resolved_artifacts_dir, resolved_db_path,
        )
        yield
        # Graceful shutdown: stop scheduler before closing storage
        try:
            scheduler.shutdown(wait=True)
        except Exception as exc:
            logger.warning("Scheduler shutdown error: %s", exc)
        # Drain durable event writes before closing their SQLite dependency.
        try:
            event_recorder.close()
        except Exception as exc:
            logger.warning("Run event recorder close error: %s", exc)
        # Cleanup: close DB connection
        try:
            storage.close()
        except Exception as exc:
            logger.warning("Storage close error: %s", exc)

    app = FastAPI(
        title="Inspectra Product API",
        description=(
            "Product backend for the Inspectra QA Platform. "
            "Manages projects, app targets, validation packs, live runs, and artifacts."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_LOCAL_ORIGINS,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Accept", "Authorization"],
        allow_credentials=False,
    )

    @app.get("/api/health", tags=["meta"], response_model=HealthResponse)
    def health_check() -> HealthResponse:
        """Lightweight liveness probe for the frontend health check."""
        return HealthResponse(status="ok", provenance=Provenance.REAL_EXECUTION)

    # Register all routers under /api prefix
    _prefix = "/api"
    app.include_router(dashboard.router, prefix=_prefix)
    app.include_router(projects.router, prefix=_prefix)
    app.include_router(apps.router, prefix=_prefix)
    app.include_router(runtime_doctor.router, prefix=_prefix)
    app.include_router(validation_packs.router, prefix=_prefix)
    app.include_router(test_plans.router, prefix=_prefix)
    app.include_router(live_runs.router, prefix=_prefix)
    app.include_router(permissions.router, prefix=_prefix)
    app.include_router(evidence.router, prefix=_prefix)
    app.include_router(reports.router, prefix=_prefix)
    app.include_router(connectors.router, prefix=_prefix)
    app.include_router(settings.router, prefix=_prefix)
    app.include_router(models_router.router, prefix=_prefix)
    app.include_router(memory_router.router, prefix=_prefix)
    app.include_router(dev_router.router, prefix=_prefix)
    app.include_router(app_discovery_router.router, prefix=_prefix)
    app.include_router(app_map_router.router, prefix=_prefix)
    app.include_router(local_picker_router.router, prefix=_prefix)
    app.include_router(local_environment_router.router, prefix=_prefix)
    app.include_router(local_folder_search_router.router, prefix=_prefix)
    app.include_router(visual_baselines.router, prefix=_prefix)
    app.include_router(evaluations.router, prefix=_prefix)
    app.include_router(root_causes.router, prefix=_prefix)
    app.include_router(run_history.router, prefix=_prefix)
    app.include_router(run_comparison.router, prefix=_prefix)

    return app
