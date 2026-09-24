"""
test_change_impact_analyzer.py - Tests for graph-backed change impact analysis.
"""

from qa_ai.improvement.change_impact_analyzer import ChangeImpactAnalyzer


class TestChangeImpactAnalyzer:
    def test_identifies_affected_files_tests_workflows_and_apis(self, artifact_store):
        analyzer = ChangeImpactAnalyzer(artifact_store)

        result = analyzer.run(
            fix_plan={
                "fixes": [
                    {
                        "fix_id": "FIX-001",
                        "affected_files": ["qa_ai/audit/api_audit.py"],
                        "affected_workflows": ["auth_flow"],
                        "affected_apis": ["GET /users"],
                    }
                ]
            },
            app_map={
                "api_endpoints": [{"method": "GET", "path": "/users"}],
                "critical_flows": [{"name": "auth_flow"}],
            },
            graph_context={
                "nodes": [
                    {"source_file": "qa_ai/audit/api_audit.py", "label": "APIAuditAgent"},
                    {"source_file": "tests/test_api_audit.py", "label": "test_api_audit.py"},
                ],
                "links": [],
            },
        )

        assert result["affected_files"] == ["qa_ai/audit/api_audit.py"]
        assert "tests/test_api_audit.py" in result["affected_tests"]
        assert result["affected_workflows"] == ["auth_flow"]
        assert result["affected_apis"] == ["GET /users"]
        assert artifact_store.artifact_exists("change_impact_analysis")

    def test_falls_back_when_graphify_context_is_missing(self, artifact_store, tmp_dir, monkeypatch):
        analyzer = ChangeImpactAnalyzer(artifact_store)
        monkeypatch.chdir(tmp_dir)

        result = analyzer.run(
            fix_plan={"fixes": [{"affected_files": ["qa_ai/audit/api_audit.py"]}]},
            app_map={"api_endpoints": [{"method": "GET", "path": "/users"}]},
        )

        assert result["metadata"]["graph_context_used"] is False
        assert result["affected_files"] == ["qa_ai/audit/api_audit.py"]
        assert result["affected_apis"] == ["GET /users"]
