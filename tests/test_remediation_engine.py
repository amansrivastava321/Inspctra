"""
test_remediation_engine.py - Tests for remediation planning and permission gates.
"""

from qa_ai.improvement.remediation_engine import RemediationEngine


class TestRemediationEngine:
    def test_remediation_requires_permission(self, artifact_store):
        engine = RemediationEngine(artifact_store)

        result = engine.run(
            fix_plan={"fixes": [{"fix_id": "FIX-001", "risk_level": "low", "affected_files": ["app.py"]}]},
            approved=False,
            dry_run=False,
        )

        assert result["permission_required"] is True
        assert result["can_apply"] is False
        assert result["actions"][0]["status"] == "blocked_pending_permission"
        assert artifact_store.artifact_exists("remediation_plan")

    def test_dry_run_mode_prepares_actions_without_applying(self, artifact_store):
        engine = RemediationEngine(artifact_store)

        result = engine.run(
            fix_plan={"fixes": [{"fix_id": "FIX-001", "risk_level": "low", "affected_files": ["app.py"]}]},
            approved=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["can_apply"] is False
        assert result["actions"][0]["status"] == "dry_run_only"

    def test_non_boolean_approval_does_not_unlock_apply(self, artifact_store):
        engine = RemediationEngine(artifact_store)

        result = engine.run(
            fix_plan={"fixes": [{"fix_id": "FIX-001", "risk_level": "low", "affected_files": ["app.py"]}]},
            approved="yes",  # type: ignore[arg-type]
            dry_run=False,
        )

        assert result["approved"] is False
        assert result["permission_required"] is True
        assert result["can_apply"] is False
        assert result["actions"][0]["status"] == "blocked_pending_permission"
