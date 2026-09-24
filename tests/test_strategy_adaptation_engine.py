from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.strategy_adaptation_engine import StrategyAdaptationEngine


def test_strategy_adaptation_engine_uses_evidence_and_benchmark_gaps(artifact_store):
    artifact_store.save_artifact(
        "audit_memory_index",
        {
            "runs": [
                {
                    "memory_id": "MEM-1",
                    "source": {
                        "evidence_completeness": 0.5,
                        "runtime_verification_rate": 0.4,
                        "missed_expected_issues": 2,
                    },
                }
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact("benchmark_comparison_report", {"degraded_detection": True}, agent="test")
    artifact_store.save_artifact("benchmark_coverage_trend", {"trend_direction": "decreasing"}, agent="test")

    report = StrategyAdaptationEngine(artifact_store).run()
    strategies = {row.get("strategy") for row in report.get("recommendations", []) if isinstance(row, dict)}

    assert report["advisory_only"] is True
    assert report["deterministic_evidence_required"] is True
    assert "increase_evidence_capture" in strategies
    assert "expand_runtime_validation" in strategies
    assert "target_missed_issue_patterns" in strategies
    assert "re-prioritize_detection_domains" in strategies

    validated = ArtifactValidator().validate_for_consumption(
        "strategy_adaptation_plan",
        artifact_store.load_artifact("strategy_adaptation_plan"),
    )
    assert isinstance(validated.data, dict)


def test_strategy_adaptation_engine_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("audit_memory_index", "bad", agent="test")
    report = StrategyAdaptationEngine(artifact_store).run()
    assert report["advisory_only"] is True
    assert len(report["recommendations"]) >= 1
