"""
runtime_risk_engine.py - Combines static risk scores with runtime evidence
to produce runtime-adjusted risk scores.
Factors in: static risk, runtime failures, verified exploits, execution instability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)

# Runtime adjustment multipliers
VERIFICATION_MULTIPLIERS = {
    "verified": 1.5,              # Confirmed by runtime - increase risk
    "partially_verified": 1.2,    # Partially confirmed - slight increase
    "unverifiable": 1.0,          # No change
    "blocked": 0.8,               # Couldn't verify - slight decrease
}

EXPLOIT_MULTIPLIERS = {
    "high": 2.0,                  # Confirmed exploitable - double risk
    "medium": 1.5,                # Likely exploitable
    "low": 1.1,                   # Potentially exploitable
    "not_exploitable": 0.7,       # Not exploitable - reduce risk
}

INSTABILITY_PENALTY = {
    "repeated_failure": 3.0,
    "flaky_behavior": 2.0,
    "retry_loop": 1.5,
    "navigation_loop": 1.5,
    "timeout_cluster": 2.5,
    "inconsistent_state": 3.0,
    "excessive_failures": 4.0,
}


class RuntimeRiskEngine:
    """
    Combines static and runtime risk signals into adjusted risk scores.

    Runtime-adjusted score = static_score
        * verification_multiplier
        * exploit_multiplier
        + instability_penalty
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        static_risk_report: Optional[Dict[str, Any]] = None,
        verified_findings: Optional[Dict[str, Any]] = None,
        exploit_results: Optional[Dict[str, Any]] = None,
        behavioral_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calculate runtime-adjusted risk scores."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if static_risk_report is None:
            static_risk_report = self.store.load_artifact("overall_risk_report") or {}
        if verified_findings is None:
            verified_findings = self.store.load_artifact("verified_findings") or {}
        if exploit_results is None:
            exploit_results = self.store.load_artifact("exploit_verification_results") or {}
        if behavioral_analysis is None:
            behavioral_analysis = self.store.load_artifact("behavioral_analysis") or {}

        # Build lookup maps
        verification_map = self._build_verification_map(verified_findings)
        exploit_map = self._build_exploit_map(exploit_results)
        instability_score = self._calculate_instability_score(behavioral_analysis)

        # Adjust each finding's risk score
        static_findings = static_risk_report.get("findings", [])
        adjusted_findings: List[Dict[str, Any]] = []
        total_static = 0.0
        total_adjusted = 0.0

        for sf in static_findings:
            fid = sf.get("id", "")
            static_score = sf.get("risk_score", 0.0)
            total_static += static_score

            # Apply verification multiplier
            verification_status = verification_map.get(fid, "unverifiable")
            v_mult = VERIFICATION_MULTIPLIERS.get(verification_status, 1.0)

            # Apply exploit multiplier
            exploit_confidence = exploit_map.get(fid, "not_exploitable")
            e_mult = EXPLOIT_MULTIPLIERS.get(exploit_confidence, 1.0)

            adjusted_score = static_score * v_mult * e_mult
            total_adjusted += adjusted_score

            adjusted_findings.append({
                **sf,
                "static_risk_score": static_score,
                "verification_status": verification_status,
                "exploit_confidence": exploit_confidence,
                "verification_multiplier": v_mult,
                "exploit_multiplier": e_mult,
                "runtime_adjusted_score": round(adjusted_score, 2),
                "risk_change": round(adjusted_score - static_score, 2),
            })

        # Sort by adjusted score
        adjusted_findings.sort(key=lambda x: x["runtime_adjusted_score"], reverse=True)
        for i, f in enumerate(adjusted_findings):
            f["adjusted_priority_rank"] = i + 1

        # Calculate overall adjusted risk
        instability_bonus = instability_score * 5.0  # Convert to score contribution
        total_adjusted_with_instability = total_adjusted + instability_bonus

        max_possible = max(len(static_findings) * 10.0 * 2.0 * 2.0, 1.0)
        overall_static = min(100.0, (total_static / max_possible * 100)) if max_possible > 0 else 0.0
        overall_adjusted = min(100.0, (total_adjusted_with_instability / max_possible * 100)) if max_possible > 0 else 0.0

        # Risk level
        risk_level = self._classify_overall_risk(overall_adjusted)

        # Risk delta analysis
        risk_delta = overall_adjusted - overall_static
        if risk_delta > 10:
            delta_assessment = "significantly_increased"
        elif risk_delta > 3:
            delta_assessment = "increased"
        elif risk_delta < -10:
            delta_assessment = "significantly_decreased"
        elif risk_delta < -3:
            delta_assessment = "decreased"
        else:
            delta_assessment = "stable"

        duration = time.time() - start_time

        result = {
            "metadata": {
                "risk_type": "runtime_adjusted_risk",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "RuntimeRiskEngine",
            },
            "overall_static_risk_score": round(overall_static, 2),
            "overall_adjusted_risk_score": round(overall_adjusted, 2),
            "risk_delta": round(risk_delta, 2),
            "delta_assessment": delta_assessment,
            "risk_level": risk_level,
            "instability_score": round(instability_score, 2),
            "instability_bonus": round(instability_bonus, 2),
            "total_findings": len(adjusted_findings),
            "findings": adjusted_findings,
            "risk_distribution": {
                "critical": sum(1 for f in adjusted_findings if self._classify_risk(f["runtime_adjusted_score"]) == "critical"),
                "high": sum(1 for f in adjusted_findings if self._classify_risk(f["runtime_adjusted_score"]) == "high"),
                "medium": sum(1 for f in adjusted_findings if self._classify_risk(f["runtime_adjusted_score"]) == "medium"),
                "low": sum(1 for f in adjusted_findings if self._classify_risk(f["runtime_adjusted_score"]) == "low"),
            },
        }

        self.store.save_artifact("runtime_risk_report", result, agent="RuntimeRiskEngine")
        logger.info(
            f"Runtime risk assessment: {risk_level} "
            f"(static={overall_static:.1f}, adjusted={overall_adjusted:.1f}, "
            f"delta={risk_delta:+.1f}, {delta_assessment})"
        )
        return result

    def _build_verification_map(self, verified_findings: Dict[str, Any]) -> Dict[str, str]:
        """Build finding_id -> verification_status map."""
        result: Dict[str, str] = {}
        for vf in verified_findings.get("verified_findings", []):
            fid = vf.get("id", "")
            if fid:
                result[fid] = vf.get("verification_status", "unverifiable")
        return result

    def _build_exploit_map(self, exploit_results: Dict[str, Any]) -> Dict[str, str]:
        """Build finding_id -> exploit_confidence map."""
        result: Dict[str, str] = {}
        for er in exploit_results.get("exploit_results", []):
            fid = er.get("id", "")
            if fid:
                result[fid] = er.get("exploit_confidence", "not_exploitable")
        return result

    def _calculate_instability_score(self, behavioral_analysis: Dict[str, Any]) -> float:
        """Calculate a 0-10 instability score from behavioral anomalies."""
        anomalies = behavioral_analysis.get("anomalies", [])
        if not anomalies:
            return 0.0

        total_penalty = 0.0
        for a in anomalies:
            atype = a.get("type", "")
            total_penalty += INSTABILITY_PENALTY.get(atype, 1.0)

        # Normalize to 0-10 scale
        return min(10.0, total_penalty)

    def _classify_risk(self, score: float) -> str:
        if score >= 14.0:
            return "critical"
        elif score >= 8.0:
            return "high"
        elif score >= 3.0:
            return "medium"
        else:
            return "low"

    def _classify_overall_risk(self, score: float) -> str:
        if score >= 75:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "medium"
        else:
            return "low"
