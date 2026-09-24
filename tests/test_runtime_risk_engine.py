"""
test_runtime_risk_engine.py - Tests for the RuntimeRiskEngine.
Validates runtime-adjusted risk scoring, verification/exploit multipliers,
instability penalties, and risk delta analysis.
"""

import pytest

from qa_ai.runtime_intelligence.runtime_risk_engine import RuntimeRiskEngine


class TestRuntimeRiskEngine:
    def test_initializes_with_artifact_store(self, artifact_store):
        engine = RuntimeRiskEngine(artifact_store)
        assert engine.store is artifact_store

    def test_returns_risk_report_structure(self, artifact_store):
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report={}, verified_findings={}, exploit_results={}, behavioral_analysis={})

        assert "metadata" in result
        assert "overall_static_risk_score" in result
        assert "overall_adjusted_risk_score" in result
        assert "risk_delta" in result
        assert "risk_level" in result
        assert result["metadata"]["risk_type"] == "runtime_adjusted_risk"

    def test_increases_risk_for_verified_findings(self, artifact_store):
        static = {
            "findings": [
                {"id": "F1", "risk_score": 10.0, "risk_classification": "high"},
            ],
        }
        verified = {
            "verified_findings": [
                {"id": "F1", "verification_status": "verified"},
            ],
        }
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report=static, verified_findings=verified)

        adjusted = result["findings"][0]
        assert adjusted["runtime_adjusted_score"] > adjusted["static_risk_score"]
        assert adjusted["verification_multiplier"] > 1.0

    def test_increases_risk_for_exploitable_findings(self, artifact_store):
        static = {
            "findings": [
                {"id": "F1", "risk_score": 10.0, "risk_classification": "high"},
            ],
        }
        exploits = {
            "exploit_results": [
                {"id": "F1", "exploit_confidence": "high"},
            ],
        }
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report=static, exploit_results=exploits)

        adjusted = result["findings"][0]
        assert adjusted["exploit_multiplier"] >= 2.0
        assert adjusted["runtime_adjusted_score"] > adjusted["static_risk_score"]

    def test_decreases_risk_for_not_exploitable(self, artifact_store):
        static = {
            "findings": [
                {"id": "F1", "risk_score": 10.0, "risk_classification": "high"},
            ],
        }
        exploits = {
            "exploit_results": [
                {"id": "F1", "exploit_confidence": "not_exploitable"},
            ],
        }
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report=static, exploit_results=exploits)

        adjusted = result["findings"][0]
        assert adjusted["exploit_multiplier"] < 1.0
        assert adjusted["runtime_adjusted_score"] < adjusted["static_risk_score"]

    def test_instability_increases_risk(self, artifact_store):
        static = {"findings": []}
        behavioral = {
            "anomalies": [
                {"type": "excessive_failures"},
                {"type": "timeout_cluster"},
            ],
        }
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report=static, behavioral_analysis=behavioral)

        assert result["instability_score"] > 0
        assert result["instability_bonus"] > 0

    def test_handles_empty_inputs(self, artifact_store):
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run()

        assert result["overall_static_risk_score"] == 0.0
        assert result["overall_adjusted_risk_score"] == 0.0
        assert result["total_findings"] == 0

    def test_artifacts_written(self, artifact_store):
        engine = RuntimeRiskEngine(artifact_store)
        engine.run()

        assert artifact_store.artifact_exists("runtime_risk_report")

    def test_risk_level_classification(self, artifact_store):
        # Many high-risk findings with exploit boost should produce high/critical level
        static = {
            "findings": [
                {"id": f"F{i}", "risk_score": 15.0, "risk_classification": "critical"}
                for i in range(10)
            ],
        }
        verified = {
            "verified_findings": [
                {"id": f"F{i}", "verification_status": "verified"} for i in range(10)
            ],
        }
        exploits = {
            "exploit_results": [
                {"id": f"F{i}", "exploit_confidence": "high"} for i in range(10)
            ],
        }
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report=static, verified_findings=verified, exploit_results=exploits)

        assert result["risk_level"] in ("critical", "high")

    def test_risk_distribution(self, artifact_store):
        static = {
            "findings": [
                {"id": "F1", "risk_score": 15.0, "risk_classification": "critical"},
                {"id": "F2", "risk_score": 8.0, "risk_classification": "high"},
                {"id": "F3", "risk_score": 4.0, "risk_classification": "medium"},
                {"id": "F4", "risk_score": 1.0, "risk_classification": "low"},
            ],
        }
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report=static)

        dist = result["risk_distribution"]
        assert dist["critical"] + dist["high"] + dist["medium"] + dist["low"] == 4

    def test_findings_sorted_by_adjusted_score(self, artifact_store):
        static = {
            "findings": [
                {"id": "F1", "risk_score": 8.0, "risk_classification": "medium"},
                {"id": "F2", "risk_score": 10.0, "risk_classification": "high"},
            ],
        }
        verified = {
            "verified_findings": [
                {"id": "F1", "verification_status": "verified"},  # 8.0 * 1.5 = 12.0
                {"id": "F2", "verification_status": "blocked"},    # 10.0 * 0.8 = 8.0
            ],
        }
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report=static, verified_findings=verified)

        # F1 should now rank higher due to verification boost
        assert result["findings"][0]["id"] == "F1"

    def test_delta_assessment(self, artifact_store):
        static = {
            "findings": [
                {"id": "F1", "risk_score": 10.0, "risk_classification": "high"},
            ],
        }
        verified = {
            "verified_findings": [
                {"id": "F1", "verification_status": "verified"},
            ],
        }
        engine = RuntimeRiskEngine(artifact_store)
        result = engine.run(static_risk_report=static, verified_findings=verified)

        assert result["delta_assessment"] in ("stable", "increased", "significantly_increased", "decreased", "significantly_decreased")
