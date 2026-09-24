"""
software_health_model.py - Calculates an overall software health score.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import time

from qa_ai.runtime.artifact_store import ArtifactStore


class SoftwareHealthModel:
    """Combines audit, runtime, release, evidence, and regression signals."""

    WEIGHTS = {
        "security": 0.20,
        "code_quality": 0.15,
        "runtime": 0.15,
        "release": 0.10,
        "sync": 0.10,
        "database": 0.10,
        "evidence": 0.08,
        "regression": 0.12,
    }

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        signals: Optional[Dict[str, float]] = None,
        risk_report: Optional[Dict[str, Any]] = None,
        regression_report: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calculate health and write software_health_score.json."""
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        signal_scores = self._load_signals(signals, risk_report, regression_report, evidence)
        dimensions = {
            name: {
                "score": self._clamp(score),
                "weight": weight,
                "weighted_score": round(self._clamp(score) * weight, 2),
            }
            for name, weight in self.WEIGHTS.items()
            for score in [signal_scores.get(name, 100.0)]
        }

        overall = round(sum(d["weighted_score"] for d in dimensions.values()), 1)
        result = {
            "metadata": {
                "model": "continuous_software_health",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "SoftwareHealthModel",
            },
            "overall_score": overall,
            "health_level": self._health_level(overall),
            "dimensions": dimensions,
            "recommendation": self._recommendation(overall),
        }
        self.store.save_artifact("software_health_score", result, agent="SoftwareHealthModel")
        return result

    def _load_signals(
        self,
        signals: Optional[Dict[str, float]],
        risk_report: Optional[Dict[str, Any]],
        regression_report: Optional[Dict[str, Any]],
        evidence: Optional[Dict[str, Any]],
    ) -> Dict[str, float]:
        if signals is not None:
            return {key: self._clamp(value) for key, value in signals.items()}

        risk_report = self._as_dict(risk_report) or self._as_dict(self.store.load_artifact("overall_risk_report")) or {}
        regression_report = self._as_dict(regression_report) or self._as_dict(self.store.load_artifact("regression_guard_report")) or {}
        evidence = self._as_dict(evidence) or self._as_dict(self.store.load_artifact("evidence_index")) or self._as_dict(self.store.load_artifact("evidence_graph"))

        return {
            "security": self._score_audit("security_audit_results", "security", risk_report),
            "code_quality": self._score_audit("code_quality_results", "code_quality", risk_report),
            "runtime": self._runtime_score(),
            "release": self._score_audit("release_readiness_results", "release", risk_report),
            "sync": self._score_audit("sync_audit_results", "sync", risk_report),
            "database": self._score_audit("database_audit_results", "database", risk_report),
            "evidence": self._evidence_score(evidence),
            # Missing regression evidence should not be treated as perfect quality.
            "regression": 55.0 if regression_report.get("regression_detected") else (100.0 if regression_report else 65.0),
        }

    def _score_audit(self, artifact_name: str, category: str, risk_report: Dict[str, Any]) -> float:
        raw_artifact = self.store.load_artifact(artifact_name)
        artifact = self._as_dict(raw_artifact)
        if artifact is None:
            return 60.0

        explicit = artifact.get("score") or artifact.get("readiness_score") or artifact.get("quality_score")
        if explicit is not None:
            return self._clamp(float(explicit))

        findings = self._extract_findings(artifact)
        if not findings and category in {"security", "code_quality"}:
            findings = [
                f for f in risk_report.get("findings", [])
                if category in {f.get("category"), *(f.get("tags") or [])}
            ]
        return self._score_from_findings(findings)

    def _runtime_score(self) -> float:
        runtime = self._as_dict(self.store.load_artifact("runtime_risk_report"))
        if runtime is None:
            return 60.0

        adjusted = runtime.get("overall_adjusted_risk_score")
        if adjusted is not None:
            return self._clamp(100.0 - float(adjusted))
        return self._score_from_findings(self._extract_findings(runtime))

    def _evidence_score(self, evidence: Dict[str, Any]) -> float:
        if not evidence:
            return 35.0
        total = evidence.get("total_evidence") or evidence.get("total") or evidence.get("summary", {}).get("total")
        if total is None:
            return 45.0
        return self._clamp(50.0 + min(float(total), 10.0) * 5.0)

    def _score_from_findings(self, findings: list[Dict[str, Any]]) -> float:
        penalties = {"critical": 25.0, "high": 15.0, "medium": 7.0, "low": 2.0, "info": 0.5}
        penalty = sum(penalties.get(str(f.get("severity", "medium")).lower(), 7.0) for f in findings)
        return self._clamp(100.0 - penalty)

    def _extract_findings(self, artifact: Any) -> list[Dict[str, Any]]:
        if not isinstance(artifact, dict):
            return []
        for key in ("findings", "issues", "vulnerabilities", "results"):
            value = artifact.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def _health_level(self, score: float) -> str:
        if score >= 90:
            return "excellent"
        if score >= 70:
            return "good"
        if score >= 50:
            return "fair"
        return "poor"

    def _recommendation(self, score: float) -> str:
        if score >= 90:
            return "Maintain current controls and continue trend monitoring."
        if score >= 70:
            return "Prioritize high-confidence fixes and regression prevention."
        if score >= 50:
            return "Address systemic root causes before release expansion."
        return "Pause release activity until critical remediation plans are approved."

    def _clamp(self, value: float) -> float:
        return round(max(0.0, min(100.0, float(value))), 2)

    def _as_dict(self, value: Any) -> Optional[Dict[str, Any]]:
        return value if isinstance(value, dict) else None
