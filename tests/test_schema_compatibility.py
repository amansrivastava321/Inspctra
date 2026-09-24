"""
test_schema_compatibility.py - Tests for backward-compatible artifact schema handling.
"""

from qa_ai.artifacts.artifact_validator import ArtifactValidator


class TestSchemaCompatibility:
    def test_regression_report_legacy_shape_is_accepted(self):
        validator = ArtifactValidator()

        legacy = {
            "summary": {
                "new_findings": 1,
                "worsened_findings": 0,
                "new_test_failures": 0,
            }
        }

        result = validator.validate_for_consumption("regression_guard_report", legacy)

        assert result.data["regression_detected"] is True
        assert result.data["summary"]["new_findings"] == 1
        assert result.data["artifact_metadata"]["artifact_type"] == "regression_guard_report"

    def test_execution_trace_legacy_trace_field_maps_to_events(self):
        validator = ArtifactValidator()

        legacy = {
            "trace": [{"action": "navigate", "target": "/"}],
            "summary": {"total_events": 1},
        }
        result = validator.validate_for_consumption("execution_trace", legacy)

        assert len(result.data["events"]) == 1
        assert result.data["events"][0]["action"] == "navigate"
        assert result.data["artifact_metadata"]["artifact_type"] == "execution_trace"
