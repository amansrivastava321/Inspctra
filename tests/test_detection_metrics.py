"""
test_detection_metrics.py - Tests for benchmark detection metric calculations.
"""

from qa_ai.benchmarking.detection_metrics import DetectionMetrics


class TestDetectionMetrics:
    def test_metrics_generated_from_benchmark_results(self):
        summary = {
            "apps": [
                {
                    "app_name": "demo",
                    "findings": [
                        {"title": "Missing auth on /users", "category": "security", "target": "/users"},
                        {"title": "Missing auth on /users", "category": "security", "target": "/users"},
                        {"title": "TODO debt found", "category": "technical_debt", "target": "app.py"},
                    ],
                    "expected_issues": [
                        {"issue_id": "missing_auth", "keywords": ["auth", "/users"]},
                        {"issue_id": "todo_debt", "keywords": ["todo", "debt"]},
                    ],
                    "runtime_validation_summary": {"verified": 1, "partially_verified": 1, "blocked": 1},
                    "evidence_summary": {"evidence_nodes": 2},
                }
            ]
        }

        result = DetectionMetrics().run(summary)

        metrics = result["metrics"]
        assert metrics["issue_coverage"] > 0
        assert metrics["duplicate_findings"] >= 1
        assert metrics["runtime_verification_rate"] > 0
        assert metrics["evidence_completeness"] > 0
        assert len(result["per_app"]) == 1

    def test_malformed_benchmark_data_handled_safely(self):
        result = DetectionMetrics().run({"apps": "bad-payload"})
        assert result["metrics"]["apps_evaluated"] == 0
        assert result["metrics"]["issue_coverage"] == 0.0
        assert result["per_app"] == []
