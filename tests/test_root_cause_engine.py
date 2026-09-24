"""
test_root_cause_engine.py - Tests for the RootCauseEngine.
Validates root cause identification by file, endpoint, category,
cascading failures, and hotspot detection.
"""

import pytest

from qa_ai.intelligence.root_cause_engine import RootCauseEngine


class TestRootCauseEngine:
    def test_identifies_file_hotspot(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "T1", "severity": "high", "category": "auth", "file_path": "config.py", "tags": ["auth"]},
                {"id": "F2", "title": "T2", "severity": "critical", "category": "secrets", "file_path": "config.py", "tags": ["secrets"]},
                {"id": "F3", "title": "T3", "severity": "medium", "category": "debug", "file_path": "config.py", "tags": ["debug"]},
            ],
            "correlations": {"cross_cutting": {}},
        }

        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        file_rca = [rc for rc in result["root_causes"] if rc["root_type"] == "file_hotspot"]
        assert len(file_rca) > 0
        assert "config.py" in file_rca[0]["affected_files"]

    def test_identifies_endpoint_risk(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "No auth", "severity": "critical", "category": "auth", "api_endpoint": "DELETE /users", "tags": ["auth"]},
                {"id": "F2", "title": "No idempotency", "severity": "medium", "category": "idempotency", "api_endpoint": "DELETE /users", "tags": ["idempotency"]},
            ],
            "correlations": {"cross_cutting": {}},
        }

        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        ep_rca = [rc for rc in result["root_causes"] if rc["root_type"] == "endpoint_risk"]
        assert len(ep_rca) > 0
        assert "DELETE /users" in ep_rca[0]["affected_endpoints"]

    def test_identifies_category_cluster(self, artifact_store):
        correlated = {
            "findings": [
                {"id": f"F{i}", "title": f"Security {i}", "severity": "high", "category": "security", "tags": ["security"]}
                for i in range(4)
            ],
            "correlations": {"cross_cutting": {}},
        }

        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        cat_rca = [rc for rc in result["root_causes"] if rc["root_type"] == "category_cluster"]
        assert len(cat_rca) > 0

    def test_detects_cascading_failures(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "T1", "severity": "critical", "category": "auth", "file_path": "hot.py", "tags": ["auth"]},
                {"id": "F2", "title": "T2", "severity": "high", "category": "secrets", "file_path": "hot.py", "tags": ["secrets"]},
                {"id": "F3", "title": "T3", "severity": "high", "category": "debug", "file_path": "hot.py", "tags": ["debug"]},
            ],
            "correlations": {
                "cross_cutting": {
                    "hotspot_files": ["hot.py"],
                    "multi_issue_endpoints": [],
                },
            },
        }

        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        cascade_rca = [rc for rc in result["root_causes"] if rc["root_type"] == "cascading_failure"]
        assert len(cascade_rca) > 0

    def test_finds_hotspots(self, artifact_store):
        correlated = {
            "findings": [],
            "correlations": {
                "cross_cutting": {
                    "hotspot_files": ["big.py"],
                    "multi_issue_endpoints": ["POST /data"],
                },
            },
        }

        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        assert len(result["hotspots"]) == 2

    def test_empty_input(self, artifact_store):
        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings={"findings": [], "correlations": {}})

        assert result["root_causes"] == []
        assert result["summary"]["total_root_causes"] == 0

    def test_result_has_metadata(self, artifact_store):
        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings={"findings": [], "correlations": {}})

        assert result["metadata"]["analysis_type"] == "root_cause_analysis"
        assert result["metadata"]["generated_by"] == "RootCauseEngine"
        assert result["metadata"]["duration_seconds"] >= 0

    def test_artifacts_written(self, artifact_store):
        engine = RootCauseEngine(artifact_store)
        engine.run(correlated_findings={"findings": [], "correlations": {}})

        assert artifact_store.artifact_exists("root_cause_analysis")

    def test_confidence_scores(self, artifact_store):
        correlated = {
            "findings": [
                {"id": f"F{i}", "title": f"T{i}", "severity": "high", "category": "auth", "file_path": "x.py", "tags": ["auth"]}
                for i in range(5)
            ],
            "correlations": {"cross_cutting": {}},
        }

        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        for rc in result["root_causes"]:
            assert 0.0 <= rc["confidence"] <= 1.0

    def test_summary_counts(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "T1", "severity": "high", "category": "auth", "file_path": "a.py", "api_endpoint": "GET /x", "tags": ["auth"]},
                {"id": "F2", "title": "T2", "severity": "high", "category": "auth", "file_path": "a.py", "api_endpoint": "GET /x", "tags": ["auth"]},
            ],
            "correlations": {"cross_cutting": {}},
        }

        engine = RootCauseEngine(artifact_store)
        result = engine.run(correlated_findings=correlated)

        assert "file_hotspots" in result["summary"]
        assert "endpoint_risks" in result["summary"]
        assert "category_clusters" in result["summary"]
        assert "cascading_failures" in result["summary"]
