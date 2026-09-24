"""
server.py - FastAPI application factory for the Inspectra LOCAL CLI AUDIT DASHBOARD.

⚠️  DEPRECATION / BOUNDARY NOTICE  ⚠️
This module is the LEGACY CLI audit dashboard, NOT the product backend.

  CLI dashboard  (this file)  → ArtifactStore  → reads per-run filesystem artifacts
  Product backend             → ProductStorage  → reads/writes SQLite persistent state

These two servers MUST remain separate:
  • This server is started by `qa_ai dashboard <artifacts_dir>` (cli/main.py).
  • The product backend is started by `qa_ai server` (qa_ai/server.py → product_backend/server.py).

Port conflict risk: both servers default to port 8765. If you run both simultaneously,
use different ports (e.g. `--port 8766` for the CLI dashboard).

DO NOT import from qa_ai.product_backend here.
DO NOT import from qa_ai.runtime.artifact_store in qa_ai.product_backend.

Usage:
    app = create_app("artifacts/")
    uvicorn.run(app, host="127.0.0.1", port=8765)
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qa_ai.webapp.artifact_api import ArtifactAPI
from qa_ai.webapp.routes import build_router

logger = logging.getLogger(__name__)


def create_app(artifacts_dir: str) -> FastAPI:
    """
    Create and configure the Inspectra dashboard FastAPI application.

    Writes a webapp_session.json artifact to *artifacts_dir* on startup
    so audit consumers can detect that the dashboard was opened.
    """
    api = ArtifactAPI(artifacts_dir)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        _record_session(api, artifacts_dir, application)
        yield

    app = FastAPI(
        title="Inspectra QA Dashboard",
        description="Read-only local dashboard for Inspectra QA-AI audit artifacts",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(build_router(api))

    return app


def _record_session(api: ArtifactAPI, artifacts_dir: str, app: FastAPI) -> None:
    """Write webapp_session.json so audit consumers can detect dashboard use."""
    try:
        from qa_ai.schemas.product_interface_schema import WebAppSessionArtifact
        from qa_ai.runtime.artifact_store import ArtifactStore

        routes: List[str] = [r.path for r in app.routes]  # type: ignore[attr-defined]
        session = WebAppSessionArtifact(
            session_id=str(uuid.uuid4()),
            artifacts_dir=str(Path(artifacts_dir).resolve()),
            started_at=datetime.now(timezone.utc).isoformat(),
            routes_registered=routes,
        )
        store = ArtifactStore(base_dir=Path(artifacts_dir))
        store.save_artifact("webapp_session", session.model_dump())
        logger.info("Dashboard session recorded (session_id=%s)", session.session_id)
    except Exception as exc:
        logger.warning("Could not record webapp_session artifact: %s", exc)
