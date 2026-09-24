"""
connector_reporter.py - Write connector artifacts.

Produces:
  artifacts/runtime_context.json
  artifacts/connector_results.json
  artifacts/connector_evidence.json
  artifacts/connector_capabilities.json
  artifacts/connector_readiness.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.interactive_runtime.connectors.connector_models import (
    RuntimeConnectorResult,
    RuntimeContext,
)

logger = logging.getLogger(__name__)


class ConnectorReporter:
    """Write all connector artifacts to output_dir."""

    def __init__(self, output_dir: str = "artifacts") -> None:
        self._out = Path(output_dir)
        self._out.mkdir(parents=True, exist_ok=True)

    def write_all(
        self,
        context: RuntimeContext,
        results: List[RuntimeConnectorResult],
        evidence: Dict[str, Any],
        capabilities: Dict[str, Any],
    ) -> None:
        self.write_runtime_context(context)
        self.write_connector_results(results)
        self.write_connector_evidence(evidence)
        self.write_connector_capabilities(capabilities)
        self.write_connector_readiness(results)

    def write_runtime_context(self, context: RuntimeContext) -> None:
        self._write_json("runtime_context.json", context.model_dump())

    def write_connector_results(self, results: List[RuntimeConnectorResult]) -> None:
        self._write_json(
            "connector_results.json",
            [r.model_dump() for r in results],
        )

    def write_connector_evidence(self, evidence: Dict[str, Any]) -> None:
        self._write_json("connector_evidence.json", evidence)

    def write_connector_capabilities(self, capabilities: Dict[str, Any]) -> None:
        self._write_json("connector_capabilities.json", capabilities)

    def write_connector_readiness(self, results: List[RuntimeConnectorResult]) -> None:
        readiness_data = []
        for r in results:
            readiness_data.append({
                "connector_id": r.connector_id,
                "connector_type": r.connector_type.value,
                "status": r.status.value,
                "readiness": r.readiness,
                "endpoint": r.endpoint,
                "readiness_checks": [rc.model_dump() for rc in r.readiness_checks],
                "errors": r.errors,
                "setup_instructions": r.setup_instructions,
                "capability_gaps": [g.model_dump() for g in r.capability_gaps],
            })
        self._write_json("connector_readiness.json", readiness_data)

    def write_connector_section_md(self, results: List[RuntimeConnectorResult]) -> str:
        """Return markdown section for connector status (used by SetupReporter)."""
        def tick(v) -> str:
            return "✅" if v else "❌"

        lines = ["\n## Connector Status\n"]
        lines.append("| ID | Type | Status | Endpoint | Gaps |")
        lines.append("|---|---|:---:|---|---|")

        for r in results:
            status_icon = {
                "ready": "✅ ready",
                "failed": "❌ failed",
                "blocked": "🚫 blocked",
                "capability_gap": "⚠️ gap",
                "skipped": "⏭ skipped",
                "pending": "⏳ pending",
                "unavailable": "❌ unavailable",
            }.get(r.status.value, r.status.value)

            gaps = ", ".join(g.gap_id for g in r.capability_gaps[:2]) or "—"
            endpoint = (r.endpoint or "—")[:50]
            lines.append(
                f"| {r.connector_id} | {r.connector_type.value} | {status_icon} | {endpoint} | {gaps} |"
            )

        return "\n".join(lines)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _write_json(self, filename: str, data: Any) -> None:
        path = self._out / filename
        try:
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception as exc:
            logger.warning("ConnectorReporter: failed to write %s: %s", filename, exc)
