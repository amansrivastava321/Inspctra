"""
connectors.py - Connector status API /api/connectors

GET /api/connectors — returns status of available runtime connectors.

Read-only: reports what connectors are configured/available.
No connector credentials are returned. No cloud calls made.

Design intent:
  These are GLOBAL runtime dependencies — they tell you whether the Inspectra
  runtime can reach the tools it needs.  They are NOT app-specific connectors.
  App-specific connector status (e.g. "can Inspectra reach this app's backend")
  belongs to future per-app health endpoints.

Appium status semantics:
  partial=True  → client library is installed but CLI or server is missing.
                  Mobile testing will fail at runtime.
  ready=True    → client installed AND CLI available AND server reachable.
  ready=False, partial=False → client library not installed.

  Sub-checks are included so the UI can show granular status without making
  separate API calls.
"""
from __future__ import annotations

import logging
import shutil
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from qa_ai.product_backend.models import ConnectorHealthResponse, Provenance

logger = logging.getLogger(__name__)
router = APIRouter(tags=["connectors"])

_APPIUM_SERVER_URL = "http://localhost:4723/status"


@router.get("/connectors", response_model=ConnectorHealthResponse)
def list_connectors() -> ConnectorHealthResponse:
    """
    Return status of all runtime connectors.

    Checks connector module availability without:
    - Establishing any connections beyond health probes
    - Returning credential values (env var names are safe)
    - Making external API calls
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    connectors: List[Dict[str, Any]] = []

    connectors.append(_check_playwright())
    connectors.append(_check_appium())
    connectors.append(_check_sqlite())
    connectors.append(_check_ollama())

    for connector in connectors:
        connector["provenance"] = Provenance.REAL_EXECUTION.value
        for sub_check in connector.get("sub_checks", []):
            sub_check["provenance"] = Provenance.REAL_EXECUTION.value

    return ConnectorHealthResponse(
        checked_at=checked_at,
        connectors=connectors,
        total=len(connectors),
        ready=sum(1 for c in connectors if c.get("ready")),
        partial=sum(1 for c in connectors if c.get("partial")),
        provenance=Provenance.REAL_EXECUTION,
    )


# ── Individual checks ─────────────────────────────────────────────────────────

def _check_playwright() -> Dict[str, Any]:
    try:
        import playwright  # noqa: F401
        return {
            "connector_id": "playwright",
            "connector_type": "browser",
            "ready": True,
            "partial": False,
            "check_type": "client_library",
            "details": "playwright package importable",
        }
    except ImportError:
        return {
            "connector_id": "playwright",
            "connector_type": "browser",
            "ready": False,
            "partial": False,
            "check_type": "client_library",
            "details": "playwright not installed — run: pip install playwright && playwright install",
        }


def _check_appium() -> Dict[str, Any]:
    """
    Composite check: client library + CLI + server reachability.

    partial=True means client is installed but mobile testing will still fail.
    ready=True only when all three layers are operational.
    """
    client_ok = _import_ok("appium")
    cli_ok = bool(shutil.which("appium"))
    server_ok = _appium_server_reachable()

    sub_checks: List[Dict[str, Any]] = [
        {
            "id": "appium_client",
            "name": "Client library",
            "ready": client_ok,
            "check_type": "client_library",
            "details": (
                "appium-python-client installed"
                if client_ok
                else "not installed — run: pip install Appium-Python-Client"
            ),
        },
        {
            "id": "appium_cli",
            "name": "CLI (appium command)",
            "ready": cli_ok,
            "check_type": "command_available",
            "details": (
                "`appium` command found in PATH"
                if cli_ok
                else "`appium` command not found — run: npm install -g appium"
            ),
        },
        {
            "id": "appium_server",
            "name": "Server (localhost:4723)",
            "ready": server_ok,
            "check_type": "server_reachable",
            "details": (
                "Appium server reachable at localhost:4723"
                if server_ok
                else "Appium server not reachable — start with: appium server"
            ),
        },
    ]

    overall_ready = client_ok and cli_ok and server_ok
    # partial = client is there but the stack is incomplete
    partial = client_ok and not overall_ready

    if overall_ready:
        summary = "Appium ready — client, CLI, and server all operational"
    elif partial:
        missing_parts = [s["name"] for s in sub_checks if not s["ready"]]
        summary = f"Appium partial — client installed but missing: {', '.join(missing_parts)}"
    else:
        summary = "Appium not available — client library not installed"

    return {
        "connector_id": "appium",
        "connector_type": "mobile",
        "ready": overall_ready,
        "partial": partial,
        "check_type": "composite",
        "details": summary,
        "sub_checks": sub_checks,
    }


def _check_sqlite() -> Dict[str, Any]:
    try:
        import sqlite3  # noqa: F401
        return {
            "connector_id": "sqlite",
            "connector_type": "database",
            "ready": True,
            "partial": False,
            "check_type": "client_library",
            "details": "sqlite3 (built-in)",
        }
    except ImportError:
        return {
            "connector_id": "sqlite",
            "connector_type": "database",
            "ready": False,
            "partial": False,
            "check_type": "client_library",
            "details": "sqlite3 not available",
        }


def _check_ollama() -> Dict[str, Any]:
    """Check if Ollama server is reachable on localhost. No cloud calls."""
    ready = _http_ok("http://localhost:11434/api/tags", timeout=2)
    return {
        "connector_id": "ollama",
        "connector_type": "ai_vision",
        "ready": ready,
        "partial": False,
        "check_type": "server_reachable",
        "details": (
            "Ollama reachable at localhost:11434"
            if ready
            else "Ollama not reachable — start with: ollama serve"
        ),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _import_ok(module: str) -> bool:
    import importlib
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def _appium_server_reachable() -> bool:
    """Probe the Appium server status endpoint. No cloud calls."""
    return _http_ok(_APPIUM_SERVER_URL, timeout=2)


def _http_ok(url: str, timeout: int = 2) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False
