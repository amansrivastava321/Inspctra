"""
test_regression_guard.py - Tests for before/after regression detection.
"""

from qa_ai.improvement.regression_guard import RegressionGuard


class TestRegressionGuard:
    def test_detects_new_and_worsened_regressions(self, artifact_store):
        guard = RegressionGuard(artifact_store)

        result = guard.run(
            before={
                "findings": [{"id": "F1", "severity": "low", "title": "Existing issue"}],
                "execution_results": {"failed": 0},
            },
            after={
                "findings": [
                    {"id": "F1", "severity": "high", "title": "Existing issue"},
                    {"id": "F2", "severity": "medium", "title": "New issue"},
                ],
                "execution_results": {"failed": 1},
            },
        )

        assert result["regression_detected"] is True
        assert result["summary"]["new_findings"] == 1
        assert result["summary"]["worsened_findings"] == 1
        assert result["summary"]["new_test_failures"] == 1
        assert artifact_store.artifact_exists("regression_guard_report")

    def test_handles_malformed_payloads_without_crashing(self, artifact_store):
        guard = RegressionGuard(artifact_store)

        result = guard.run(
            before=["bad"],  # type: ignore[arg-type]
            after={"findings": "bad", "execution_results": "bad"},
        )

        assert result["regression_detected"] is False
        assert result["summary"]["new_findings"] == 0
        assert result["summary"]["new_test_failures"] == 0
