"""
model_health.py - Health checks for local Ollama models and route coverage.

Used by Runtime Doctor and CLI models doctor command.
All checks are read-only. No model loading. No installs.
Returns structured health state for every configured task route.
No shell. No subprocess. No eval.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, FrozenSet, List, Optional, Set

from qa_ai.ai.task_profiles import (
    ModelTask,
    REQUIRED_LOCAL_MODELS,
    get_default_task_routes,
)

logger = logging.getLogger(__name__)


@dataclass
class ModelHealthStatus:
    provider_id: str
    model: str
    available: bool
    loaded: bool
    latency_ms: float
    memory_estimate_gb: float
    supports_task: Optional[str]
    last_checked_at: str
    error: Optional[str]


@dataclass
class RouteHealthSummary:
    task: str
    primary_model: str
    primary_available: bool
    fallback_models: List[str]
    fallback_available: List[bool]
    status: str        # "ready" | "partial" | "unavailable"


@dataclass
class ModelHealthReport:
    generated_at: str
    ollama_reachable: bool
    ollama_base_url: str
    installed_models: List[str]
    required_models: List[str]
    missing_models: List[str]
    present_models: List[str]
    route_coverage: List[RouteHealthSummary]
    cloud_providers_disabled: bool
    overall_readiness: str    # "full" | "partial" | "degraded" | "unavailable"
    recommendations: List[str]
    error: Optional[str]


def check_ollama_health(
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 3.0,
) -> tuple[bool, List[str], Optional[str]]:
    """
    Check Ollama reachability and list installed models.

    Returns (reachable, model_names, error_message).
    """
    url = f"{base_url}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        models = data.get("models", [])
        model_names: List[str] = []
        for m in models:
            if isinstance(m, dict):
                name = m.get("name", "")
                if name:
                    model_names.append(name)
        return True, model_names, None
    except urllib.error.URLError as exc:
        return False, [], f"Ollama not reachable: {exc}"
    except Exception as exc:
        return False, [], f"Health check error: {exc}"


def probe_ollama_chat_ready(
    model: str,
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 2.0,
) -> tuple[bool, Optional[str]]:
    """
    Verify that Ollama can answer a tiny non-streaming chat request quickly.

    This is stricter than /api/tags reachability and avoids long UI hangs when
    the daemon is up but model execution is unhealthy or too slow for product
    flows that should fall back immediately.
    """
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 1},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        if isinstance(data, dict) and data.get("message", {}).get("content") is not None:
            return True, None
        return False, "Ollama chat probe returned an unexpected payload."
    except urllib.error.HTTPError as exc:
        return False, f"Ollama chat probe failed: HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"Ollama chat probe failed: {exc}"
    except Exception as exc:
        return False, f"Ollama chat probe error: {exc}"


def _normalize_model_name(name: str) -> str:
    """Normalize model names for comparison (lowercase, strip trailing :latest if needed)."""
    return name.strip().lower()


def _model_present(installed: FrozenSet[str], required: str) -> bool:
    """Check if required model is in installed list (case-insensitive)."""
    req_norm = _normalize_model_name(required)
    for installed_name in installed:
        inst_norm = _normalize_model_name(installed_name)
        # Match exact or prefix (e.g. "qwen2.5vl:7b" matches "qwen2.5vl:7b")
        if inst_norm == req_norm:
            return True
        # Also match if installed name is base model without tag
        base = req_norm.split(":")[0]
        if inst_norm.startswith(base + ":") or inst_norm == base:
            # Only match if exact same tag or required has :latest and base matches
            if ":" in req_norm:
                if inst_norm == req_norm:
                    return True
            else:
                return True
    return False


def build_health_report(
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 3.0,
) -> ModelHealthReport:
    """
    Build a full health report for all configured routes.

    Read-only. No model loading. No network calls except Ollama /api/tags.
    """
    now = datetime.now(timezone.utc).isoformat()
    reachable, installed_list, error = check_ollama_health(base_url, timeout)

    installed_set: FrozenSet[str] = frozenset(installed_list)
    required_list = sorted(REQUIRED_LOCAL_MODELS)

    present: List[str] = [m for m in required_list if _model_present(installed_set, m)]
    missing: List[str] = [m for m in required_list if not _model_present(installed_set, m)]

    routes = get_default_task_routes()
    route_coverage: List[RouteHealthSummary] = []
    recommendations: List[str] = []

    for task, route in routes.items():
        primary_ok = _model_present(installed_set, route.model) if reachable else False
        fallback_ok = [
            _model_present(installed_set, fb) if reachable else False
            for fb in route.fallback_models
        ]

        if primary_ok:
            status = "ready"
        elif any(fallback_ok):
            status = "partial"
        else:
            status = "unavailable"
            recommendations.append(
                f"ollama pull {route.model}  # required for {task.value}"
            )

        route_coverage.append(RouteHealthSummary(
            task=task.value,
            primary_model=route.model,
            primary_available=primary_ok,
            fallback_models=list(route.fallback_models),
            fallback_available=fallback_ok,
            status=status,
        ))

    # Overall readiness
    ready_count = sum(1 for r in route_coverage if r.status == "ready")
    total_count = len(route_coverage)
    if not reachable:
        overall = "unavailable"
        recommendations.insert(0, "Start Ollama: ollama serve")
    elif ready_count == total_count:
        overall = "full"
    elif ready_count >= total_count * 0.6:
        overall = "partial"
    else:
        overall = "degraded"

    if missing:
        recommendations.append(
            f"Missing {len(missing)} required models. "
            f"Run: ollama pull {' && ollama pull '.join(missing[:3])}"
        )

    return ModelHealthReport(
        generated_at=now,
        ollama_reachable=reachable,
        ollama_base_url=base_url,
        installed_models=sorted(installed_list),
        required_models=required_list,
        missing_models=missing,
        present_models=present,
        route_coverage=route_coverage,
        cloud_providers_disabled=True,  # Default: cloud disabled
        overall_readiness=overall,
        recommendations=list(dict.fromkeys(recommendations)),  # dedupe
        error=error,
    )
