"""
test_software_health_model.py - Tests for software health scoring.
"""

from qa_ai.improvement.software_health_model import SoftwareHealthModel


class TestSoftwareHealthModel:
    def test_calculates_weighted_health_score_and_writes_artifact(self, artifact_store):
        model = SoftwareHealthModel(artifact_store)

        result = model.run(
            signals={
                "security": 80,
                "code_quality": 70,
                "runtime": 90,
                "release": 60,
                "sync": 100,
                "database": 100,
                "evidence": 50,
                "regression": 75,
            }
        )

        assert result["overall_score"] == 79.0
        assert result["health_level"] == "good"
        assert result["dimensions"]["security"]["score"] == 80.0
        assert artifact_store.artifact_exists("software_health_score")

    def test_missing_artifacts_do_not_default_to_excellent(self, artifact_store):
        model = SoftwareHealthModel(artifact_store)

        result = model.run()

        assert result["overall_score"] < 90.0
        assert result["dimensions"]["evidence"]["score"] <= 45.0
        assert result["dimensions"]["regression"]["score"] == 65.0
