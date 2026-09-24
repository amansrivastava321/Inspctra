"""
dependencies.py - FastAPI dependency injection for product backend services.

All services are stored on app.state and injected via request.app.state.
No globals. No module-level singletons.
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.event_stream import EventStream
from qa_ai.product_backend.run_manager import RunManager
from qa_ai.product_backend.run_event_recorder import RunEventRecorder
from qa_ai.product_backend.storage import ProductStorage


def get_storage(request: Request) -> ProductStorage:
    storage: ProductStorage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not initialized.",
        )
    return storage


def get_event_stream(request: Request) -> EventStream:
    stream: EventStream = getattr(request.app.state, "event_stream", None)
    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event stream not initialized.",
        )
    return stream


def get_run_manager(request: Request) -> RunManager:
    manager: RunManager = getattr(request.app.state, "run_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Run manager not initialized.",
        )
    return manager


def get_run_event_recorder(request: Request) -> RunEventRecorder:
    recorder: RunEventRecorder = getattr(request.app.state, "run_event_recorder", None)
    if recorder is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Run event recorder not initialized.",
        )
    return recorder


def get_artifact_index(request: Request) -> ArtifactIndex:
    index: ArtifactIndex = getattr(request.app.state, "artifact_index", None)
    if index is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Artifact index not initialized.",
        )
    return index
