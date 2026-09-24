"""
test_improvement_loop.py - Tests for end-to-end improvement orchestration.
"""

from qa_ai.improvement.improvement_loop import ImprovementLoop


class TestImprovementLoop:
    def test_orchestrates_all_improvement_artifacts(self, artifact_store):
        loop = ImprovementLoop(artifact_store)

        result = loop.run(
            findings={
                "findings": [
                    {
                        "id": "F1",
                        "title": "Missing auth on GET /users",
                        "severity": "high",
                        "category": "security",
                        "file_path": "qa_ai/audit/api_audit.py",
                        "api_endpoint": "GET /users",
                    }
                ]
            },
            root_causes={
                "root_causes": [
                    {
                        "cause_id": "RC-1",
                        "description": "Endpoint auth guard missing.",
                        "root_type": "endpoint_risk",
                        "finding_ids": ["F1"],
                        "affected_files": ["qa_ai/audit/api_audit.py"],
                    }
                ]
            },
            risk_report={"overall_risk_score": 55, "risk_level": "high", "findings": []},
            test_plan={
                "test_suites": {
                    "smoke": [{"id": "TEST-SMOKE", "title": "App loads", "type": "smoke"}],
                    "security": [{"id": "TEST-SEC", "title": "GET /users requires auth", "type": "security"}],
                }
            },
            before_audit={"findings": [], "execution_results": {"failed": 0}},
            after_audit={"findings": [], "execution_results": {"failed": 0}},
        )

        assert result["health_score"]["overall_score"] <= 100
        assert result["improvement_backlog"]["summary"]["total_items"] >= 1
        assert result["fix_plan"]["summary"]["total_fixes"] >= 1
        assert result["regression_guard"]["regression_detected"] is False

        for artifact_name in [
            "software_health_score",
            "improvement_backlog",
            "fix_plan",
            "change_impact_analysis",
            "remediation_plan",
            "retest_results",
            "quality_trend",
            "regression_guard_report",
            "learning_registry",
        ]:
            assert artifact_store.artifact_exists(artifact_name)

    def test_artifact_contracts_have_expected_top_level_structure(self, artifact_store):
        loop = ImprovementLoop(artifact_store)
        loop.run(
            findings={"findings": []},
            root_causes={"root_causes": []},
            risk_report={"overall_risk_score": 0, "risk_level": "low", "findings": []},
            test_plan={"test_suites": {"smoke": [{"id": "TEST-SMOKE", "title": "App loads", "type": "smoke"}]}},
            before_audit={"findings": [], "execution_results": {"failed": 0}},
            after_audit={"findings": [], "execution_results": {"failed": 0}},
        )

        contracts = {
            "software_health_score": ["metadata", "overall_score", "health_level", "dimensions"],
            "improvement_backlog": ["metadata", "items", "summary"],
            "fix_plan": ["metadata", "fixes", "summary"],
            "remediation_plan": ["metadata", "permission_required", "actions", "summary"],
            "retest_results": ["metadata", "selected_tests", "results", "summary"],
            "quality_trend": ["metadata", "history", "latest", "trend"],
            "regression_guard_report": ["metadata", "regression_detected", "summary"],
            "learning_registry": ["metadata", "false_positives", "summary"],
            "change_impact_analysis": ["metadata", "affected_files", "affected_tests", "risk_summary"],
        }

        for artifact_name, required_keys in contracts.items():
            artifact = artifact_store.load_artifact(artifact_name)
            assert artifact is not None
            for key in required_keys:
                assert key in artifact
