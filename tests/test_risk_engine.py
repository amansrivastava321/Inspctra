"""
test_risk_engine.py - Tests for the RiskEngine.
Validates weighted severity scoring, risk classification,
category breakdown, and overall risk calculation.
"""

import pytest

from qa_ai.intelligence.risk_engine import RiskEngine


class TestRiskEngine:
    def test_calculates_risk_score_for_critical_finding(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "Hardcoded secret", "severity": "critical", "category": "secrets", "tags": ["secrets"]},
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        assert result["total_findings"] == 1
        assert result["total_risk_score"] > 0
        assert result["findings"][0]["risk_score"] > 0

    def test_critical_scores_higher_than_low(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "Critical", "severity": "critical", "category": "secrets", "tags": ["secrets"]},
                {"id": "F2", "title": "Low", "severity": "low", "category": "file_size", "tags": ["file_size"]},
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        scores = {f["id"]: f["risk_score"] for f in result["findings"]}
        assert scores["F1"] > scores["F2"]

    def test_security_category_multiplier(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "Security", "severity": "high", "category": "security", "tags": ["security"]},
                {"id": "F2", "title": "Code", "severity": "high", "category": "file_size", "tags": ["file_size"]},
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        scores = {f["id"]: f["risk_score"] for f in result["findings"]}
        assert scores["F1"] > scores["F2"]

    def test_risk_classification_levels(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "Critical", "severity": "critical", "category": "secrets", "tags": ["secrets"]},
                {"id": "F2", "title": "High", "severity": "high", "category": "auth", "tags": ["auth"]},
                {"id": "F3", "title": "Medium", "severity": "medium", "category": "validation", "tags": ["validation"]},
                {"id": "F4", "title": "Low", "severity": "low", "category": "file_size", "tags": ["file_size"]},
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        classifications = {f["id"]: f["risk_classification"] for f in result["findings"]}
        assert classifications["F1"] in ("critical", "high")
        assert classifications["F4"] in ("low", "medium")

    def test_overall_risk_score_range(self, artifact_store):
        correlated = {
            "findings": [
                {"id": f"F{i}", "title": f"T{i}", "severity": "critical", "category": "secrets", "tags": ["secrets"]}
                for i in range(10)
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        assert 0.0 <= result["overall_risk_score"] <= 100.0

    def test_risk_level_classification(self, artifact_store):
        # Many critical findings should be high/critical risk
        correlated = {
            "findings": [
                {"id": f"F{i}", "title": f"T{i}", "severity": "critical", "category": "secrets", "tags": ["secrets"]}
                for i in range(20)
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        assert result["risk_level"] in ("critical", "high")

    def test_low_risk_for_few_low_findings(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "Minor", "severity": "low", "category": "file_size", "tags": ["file_size"]},
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        assert result["risk_level"] == "low"

    def test_empty_input(self, artifact_store):
        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings={"findings": []})

        assert result["total_findings"] == 0
        assert result["overall_risk_score"] == 0.0
        assert result["risk_level"] == "low"

    def test_findings_prioritized_by_rank(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "Low", "severity": "low", "category": "file_size", "tags": ["file_size"]},
                {"id": "F2", "title": "Critical", "severity": "critical", "category": "secrets", "tags": ["secrets"]},
                {"id": "F3", "title": "Medium", "severity": "medium", "category": "auth", "tags": ["auth"]},
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        ranks = [(f["priority_rank"], f["id"]) for f in result["findings"]]
        # Should be sorted by priority_rank ascending
        assert ranks == sorted(ranks, key=lambda x: x[0])
        # Critical should be rank 1
        assert result["findings"][0]["id"] == "F2"

    def test_category_breakdown(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "T1", "severity": "high", "category": "security", "tags": ["security"]},
                {"id": "F2", "title": "T2", "severity": "high", "category": "security", "tags": ["security"]},
                {"id": "F3", "title": "T3", "severity": "medium", "category": "auth", "tags": ["auth"]},
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        assert "security" in result["category_breakdown"]
        assert result["category_breakdown"]["security"] > result["category_breakdown"].get("auth", 0)

    def test_top_risks_limited(self, artifact_store):
        correlated = {
            "findings": [
                {"id": f"F{i}", "title": f"T{i}", "severity": "high", "category": "auth", "tags": ["auth"]}
                for i in range(20)
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        assert len(result["top_risks"]) <= 10

    def test_risk_distribution(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "C", "severity": "critical", "category": "secrets", "tags": ["secrets"]},
                {"id": "F2", "title": "H", "severity": "high", "category": "auth", "tags": ["auth"]},
                {"id": "F3", "title": "M", "severity": "medium", "category": "val", "tags": ["validation"]},
                {"id": "F4", "title": "L", "severity": "low", "category": "file_size", "tags": ["file_size"]},
            ],
        }

        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        dist = result["risk_distribution"]
        assert dist["critical"] + dist["high"] + dist["medium"] + dist["low"] == 4

    def test_artifacts_written(self, artifact_store):
        engine = RiskEngine(artifact_store)
        engine.run(correlated_findings={"findings": []})

        assert artifact_store.artifact_exists("overall_risk_report")

    def test_result_has_metadata(self, artifact_store):
        engine = RiskEngine(artifact_store)
        result = engine.run(correlated_findings={"findings": []})

        assert result["metadata"]["risk_type"] == "risk_assessment"
        assert result["metadata"]["generated_by"] == "RiskEngine"
        assert result["metadata"]["duration_seconds"] >= 0
