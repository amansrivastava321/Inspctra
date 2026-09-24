"""
baseline_comparison_engine.py - CI/CD baseline comparison and drift analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class BaselineComparisonEngine:
    """Compare current audit state with historical baseline artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        current: Dict[str, Any] | None = None,
        baseline: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        current_payload = current if isinstance(current, dict) else self._current_snapshot()
        baseline_payload = baseline if isinstance(baseline, dict) else self._baseline_snapshot()

        current_metrics = self._metrics(current_payload)
        baseline_metrics = self._metrics(baseline_payload)

        regressions = {
            "new_regressions": max(0, current_metrics["new_findings"] - baseline_metrics["new_findings"]),
            "resolved_findings": max(0, current_metrics["resolved_findings"] - baseline_metrics["resolved_findings"]),
            "worsened_findings": max(0, current_metrics["worsened_findings"] - baseline_metrics["worsened_findings"]),
            "evidence_quality_degradation": current_metrics["evidence_count"] < baseline_metrics["evidence_count"],
            "runtime_instability_increase": current_metrics["runtime_instability"] > baseline_metrics["runtime_instability"],
        }

        result = {
            "current": current_metrics,
            "baseline": baseline_metrics,
            "regressions": regressions,
            "summary": {
                "baseline_present": bool(baseline_payload),
                "regression_growth": regressions["new_regressions"] + regressions["worsened_findings"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("baseline_comparison_report", result, agent="CICDRuntime.BaselineComparisonEngine")
        return result

    def _current_snapshot(self) -> Dict[str, Any]:
        return {
            "regression_guard_report": self._load("regression_guard_report"),
            "evidence_graph": self._load("evidence_graph"),
            "replay_analysis": self._load("replay_analysis"),
        }

    def _baseline_snapshot(self) -> Dict[str, Any]:
        legacy = self._load("baseline_comparison")
        if legacy:
            return {
                "regression_guard_report": {
                    "summary": {
                        "new_findings": self._to_int(legacy.get("deltas", {}).get("critical_findings_delta", 0)),
                        "resolved_findings": 0,
                        "worsened_findings": self._to_int(legacy.get("deltas", {}).get("high_findings_delta", 0)),
                    }
                },
                "evidence_graph": {"summary": {"total_evidence": self._to_int(legacy.get("baseline", {}).get("evidence_count", 0))}},
                "replay_analysis": {"comparison": {"total_regressions": 0}},
            }
        return {}

    def _metrics(self, payload: Dict[str, Any]) -> Dict[str, int]:
        regression = payload.get("regression_guard_report", {}) if isinstance(payload.get("regression_guard_report"), dict) else {}
        summary = regression.get("summary", {}) if isinstance(regression.get("summary"), dict) else {}

        evidence = payload.get("evidence_graph", {}) if isinstance(payload.get("evidence_graph"), dict) else {}
        evidence_summary = evidence.get("summary", {}) if isinstance(evidence.get("summary"), dict) else {}

        replay = payload.get("replay_analysis", {}) if isinstance(payload.get("replay_analysis"), dict) else {}
        comparison = replay.get("comparison", {}) if isinstance(replay.get("comparison"), dict) else {}

        return {
            "new_findings": self._to_int(summary.get("new_findings", 0)),
            "resolved_findings": self._to_int(summary.get("resolved_findings", 0)),
            "worsened_findings": self._to_int(summary.get("worsened_findings", 0)),
            "evidence_count": self._to_int(evidence_summary.get("total_evidence", evidence.get("evidence_count", 0))),
            "runtime_instability": self._to_int(comparison.get("total_regressions", 0)),
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
