"""
connector_evidence.py - Aggregate and format connector evidence.

Collects evidence from all connectors into a single artifact dict.
Redacts secrets. Never fakes content.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorResult

logger = logging.getLogger(__name__)

_SECRET_RE = re.compile(
    r"(?i)(password|token|secret|key|api_key|authorization|bearer)\s*[:=]\s*\S+"
)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _SECRET_RE.sub(r"\1=[REDACTED]", value)
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class ConnectorEvidence:
    """Collect and merge evidence from all connector results."""

    def __init__(self) -> None:
        self._raw: Dict[str, Any] = {}

    def record(
        self,
        connector_id: str,
        result: RuntimeConnectorResult,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        entry: Dict[str, Any] = {
            "connector_id": connector_id,
            "connector_type": result.connector_type.value,
            "status": result.status.value,
            "readiness": result.readiness,
            "endpoint": result.endpoint,
            "process_id": result.process_id,
            "driver_backend": result.driver_backend,
            "errors": result.errors,
            "logs": result.logs[-20:],   # last 20 lines
            "capability_gaps": [g.model_dump() for g in result.capability_gaps],
            "readiness_checks": [rc.model_dump() for rc in result.readiness_checks],
        }
        if extra:
            entry["extra"] = _redact(extra)
        self._raw[connector_id] = _redact(entry)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._raw)

    def summary(self) -> Dict[str, Any]:
        ready = [cid for cid, e in self._raw.items() if e.get("status") == "ready"]
        failed = [cid for cid, e in self._raw.items() if e.get("status") == "failed"]
        blocked = [cid for cid, e in self._raw.items() if e.get("status") == "blocked"]
        gaps = [cid for cid, e in self._raw.items() if e.get("status") == "capability_gap"]
        skipped = [cid for cid, e in self._raw.items() if e.get("status") == "skipped"]
        return {
            "total": len(self._raw),
            "ready": ready,
            "failed": failed,
            "blocked": blocked,
            "capability_gaps": gaps,
            "skipped": skipped,
        }
