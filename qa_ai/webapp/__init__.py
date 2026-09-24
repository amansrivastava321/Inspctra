"""
qa_ai.webapp - Local web dashboard for Inspectra QA-AI.

Read-only FastAPI application that surfaces audit artifacts
through a browser UI and JSON API. No business logic lives here —
all data comes from ArtifactStore.

Usage:
    python -m qa_ai.cli dashboard artifacts/ --port 8765
"""
from qa_ai.webapp.server import create_app

__all__ = ["create_app"]
