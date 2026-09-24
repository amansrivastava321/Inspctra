"""
test_quality_score_tracker.py - Tests for software quality trend tracking.
"""

from qa_ai.improvement.quality_score_tracker import QualityScoreTracker


class TestQualityScoreTracker:
    def test_appends_quality_trend_entries(self, artifact_store):
        tracker = QualityScoreTracker(artifact_store)

        first = tracker.run(current_score={"overall_score": 70, "health_level": "fair"})
        second = tracker.run(current_score={"overall_score": 82, "health_level": "good"})

        assert len(first["history"]) == 1
        assert len(second["history"]) == 2
        assert second["trend"]["delta_from_previous"] == 12.0
        assert second["trend"]["direction"] == "improving"
        assert artifact_store.artifact_exists("quality_trend")
