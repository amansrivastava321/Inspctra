"""
test_fix_planner.py - Tests for safe fix plan generation.
"""

from qa_ai.improvement.fix_planner import FixPlanner


class TestFixPlanner:
    def test_generates_fix_plan_from_root_causes_and_findings(self, artifact_store):
        planner = FixPlanner(artifact_store)

        result = planner.run(
            findings={
                "findings": [
                    {
                        "id": "F1",
                        "title": "Missing auth on user endpoint",
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
                        "description": "Auth guard is not applied consistently.",
                        "root_type": "endpoint_risk",
                        "finding_ids": ["F1"],
                        "affected_files": ["qa_ai/audit/api_audit.py"],
                        "affected_workflows": ["auth_flow"],
                        "confidence": 0.82,
                    }
                ]
            },
            test_plan={
                "test_suites": {
                    "security": [
                        {"id": "TEST-1", "title": "GET /users requires auth", "type": "security"}
                    ]
                }
            },
        )

        assert result["summary"]["total_fixes"] == 1
        assert result["fixes"][0]["risk_level"] == "high"
        assert result["fixes"][0]["affected_files"] == ["qa_ai/audit/api_audit.py"]
        assert result["fixes"][0]["recommended_tests"] == ["TEST-1"]
        assert artifact_store.artifact_exists("fix_plan")
