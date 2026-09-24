"""
qa_ai.product_backend — Inspectra product backend API layer.

Turns Inspectra from a CLI testing engine into a web product backend.
No app-specific logic. No hardcoded target names.
"""
from qa_ai.product_backend.models import (
    AppTarget,
    AppTargetCreate,
    AppTargetUpdate,
    EvidenceFile,
    LiveRunRecord,
    PermissionRecord,
    Project,
    ProjectCreate,
    ProjectUpdate,
    ReportRecord,
    ValidationPack,
    ValidationPackCreate,
    ValidationPackUpdate,
    ValidationStep,
)
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.event_stream import EventStream
from qa_ai.product_backend.run_manager import RunManager
from qa_ai.product_backend.artifact_index import ArtifactIndex

__all__ = [
    "AppTarget",
    "AppTargetCreate",
    "AppTargetUpdate",
    "ArtifactIndex",
    "EvidenceFile",
    "EventStream",
    "LiveRunRecord",
    "PermissionRecord",
    "ProductStorage",
    "Project",
    "ProjectCreate",
    "ProjectUpdate",
    "ReportRecord",
    "RunManager",
    "ValidationPack",
    "ValidationPackCreate",
    "ValidationPackUpdate",
    "ValidationStep",
]
