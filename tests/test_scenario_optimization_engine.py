from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.scenario_optimization_engine import ScenarioOptimizationEngine


def test_scenario_optimization_engine_identifies_low_value_scenarios(artifact_store):
    artifact_store.save_artifact(
        "test_plan",
        {"test_suites": {"smoke": [{"id": "T-1"}], "security": [{"id": "T-2"}]}},
        agent="test",
    )
    artifact_store.save_artifact("execution_results", {"failed": 0}, agent="test")
    artifact_store.save_artifact("correlated_findings", {"findings": []}, agent="test")

    report = ScenarioOptimizationEngine(artifact_store).run()

    assert report["advisory_only"] is True
    assert "smoke" in report["low_value_scenarios"]
    assert len(report["recommended_actions"]) >= 1

    validated = ArtifactValidator().validate_for_consumption(
        "scenario_optimization_report",
        artifact_store.load_artifact("scenario_optimization_report"),
    )
    assert isinstance(validated.data, dict)
