"""
model_usage_logger.py - Structured routing and model-usage telemetry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore


class ModelUsageLogger:
    def __init__(self, artifact_store: Optional[ArtifactStore] = None):
        self.store = artifact_store
        self.entries: List[Dict[str, Any]] = []

    def log(
        self,
        component: str,
        model: str,
        provider: str,
        latency_ms: float,
        fallback_used: bool,
        fallback_reason: str,
        privacy_mode: str,
        success: bool,
    ) -> None:
        self.entries.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": component,
                "model": model,
                "provider": provider,
                "latency_ms": float(latency_ms),
                "fallback_used": bool(fallback_used),
                "fallback_reason": fallback_reason,
                "privacy_mode": privacy_mode,
                "success": bool(success),
            }
        )

    def flush(self, routing_mode: str) -> Dict[str, Any]:
        usage_payload = {
            "entries": list(self.entries),
            "summary": {
                "total": len(self.entries),
                "success": sum(1 for item in self.entries if item.get("success")),
                "failures": sum(1 for item in self.entries if not item.get("success")),
            },
        }
        report_payload = {
            "routing_mode": routing_mode,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "components": self._component_rollup(),
            "summary": usage_payload["summary"],
        }

        if self.store is not None:
            self.store.save_artifact("model_usage_log", usage_payload, agent="ModelUsageLogger")
            self.store.save_artifact("model_routing_report", report_payload, agent="ModelUsageLogger")
        else:
            artifact_dir = Path("artifacts")
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "model_usage_log.json").write_text(json.dumps(usage_payload, indent=2), encoding="utf-8")
            (artifact_dir / "model_routing_report.json").write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

        return report_payload

    def _component_rollup(self) -> Dict[str, Any]:
        rollup: Dict[str, Dict[str, Any]] = {}
        for item in self.entries:
            key = str(item.get("component", "unknown"))
            current = rollup.setdefault(key, {"calls": 0, "fallbacks": 0, "providers": {}})
            current["calls"] += 1
            if item.get("fallback_used"):
                current["fallbacks"] += 1
            provider = str(item.get("provider", "unknown"))
            current["providers"][provider] = current["providers"].get(provider, 0) + 1
        return rollup
