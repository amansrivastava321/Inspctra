"""
test_artifact_validator.py - Tests for artifact contract validation behavior.
"""

from qa_ai.artifacts.artifact_validator import ArtifactValidator


class TestArtifactValidator:
    def test_persistence_injects_standard_metadata(self):
        validator = ArtifactValidator()

        result = validator.validate_for_persistence(
            artifact_name="software_health_score",
            data={"overall_score": 80.0, "health_level": "good", "dimensions": {}},
            generated_by="unit-test",
        )

        assert result.valid is True
        assert result.data["artifact_metadata"]["schema_version"] == "1.0"
        assert result.data["artifact_metadata"]["generated_by"] == "unit-test"
        assert result.data["artifact_metadata"]["artifact_type"] == "software_health_score"
        assert "created_at" in result.data

    def test_non_dict_payload_rejected_safely(self):
        validator = ArtifactValidator()

        result = validator.validate_for_consumption(
            artifact_name="fix_plan",
            data=["bad", "payload"],
        )

        assert result.valid is False
        assert result.data["fixes"] == []
        assert result.data["metadata"]["validation_error"] == "artifact_payload_not_dict"

    def test_unknown_artifact_passes_through(self):
        validator = ArtifactValidator()
        payload = {"x": 1}
        result = validator.validate_for_persistence("custom_blob", payload, generated_by="x")

        assert result.valid is True
        assert result.data == payload
