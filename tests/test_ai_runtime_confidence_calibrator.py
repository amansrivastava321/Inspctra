"""Tests for ConfidenceCalibrator."""
import pytest

from qa_ai.interactive_runtime.ai_runtime.confidence_calibrator import ConfidenceCalibrator, _AI_ONLY_MAX
from qa_ai.interactive_runtime.schemas import AIVerdict, EvidenceSource


def _strong(source_type: str = "log") -> EvidenceSource:
    return EvidenceSource(source_type=source_type, description="test", strength="strong")


def _moderate(source_type: str = "ui_state") -> EvidenceSource:
    return EvidenceSource(source_type=source_type, description="test", strength="moderate")


def _weak(source_type: str = "screenshot") -> EvidenceSource:
    return EvidenceSource(source_type=source_type, description="test", strength="weak")


class TestHighConfidence:
    def test_ui_log_db_gives_high_confidence(self):
        cal = ConfidenceCalibrator()
        sources = [_strong("ui_state"), _strong("log"), _strong("db")]
        conf = cal.calibrate(sources)
        assert conf >= 0.90

    def test_ui_plus_log_gives_good_confidence(self):
        cal = ConfidenceCalibrator()
        sources = [_strong("ui_state"), _strong("log")]
        conf = cal.calibrate(sources)
        assert 0.80 <= conf <= 0.95


class TestAIOnlyCapped:
    def test_ai_only_capped_at_limit(self):
        cal = ConfidenceCalibrator()
        conf = cal.calibrate([], ai_judgment_only=True)
        assert conf <= _AI_ONLY_MAX

    def test_empty_sources_capped(self):
        cal = ConfidenceCalibrator()
        conf = cal.calibrate([])
        assert conf <= _AI_ONLY_MAX


class TestCoordinateClick:
    def test_coordinate_click_reduces_confidence(self):
        cal = ConfidenceCalibrator()
        sources = [_strong("ui_state")]
        conf_normal = cal.calibrate(sources, used_coordinate_click=False)
        conf_coord = cal.calibrate(sources, used_coordinate_click=True)
        assert conf_coord < conf_normal

    def test_accessibility_selector_boosts(self):
        cal = ConfidenceCalibrator()
        sources = [_strong("ui_state")]
        conf_no_acc = cal.calibrate(sources, used_accessibility_selector=False)
        conf_acc = cal.calibrate(sources, used_accessibility_selector=True)
        assert conf_acc >= conf_no_acc


class TestDeterministicFailure:
    def test_det_failure_near_zero(self):
        cal = ConfidenceCalibrator()
        sources = [_strong("ui_state"), _strong("log")]
        conf = cal.calibrate(sources, deterministic_failure=True)
        assert conf < 0.15


class TestVerdictMapping:
    def test_det_failure_gives_fail(self):
        cal = ConfidenceCalibrator()
        v = cal.verdict_from_confidence(0.9, False, True, True)
        assert v == AIVerdict.FAIL

    def test_ai_only_gives_unclear(self):
        cal = ConfidenceCalibrator()
        v = cal.verdict_from_confidence(0.9, True, False, False)
        assert v == AIVerdict.UNCLEAR

    def test_high_conf_strong_evidence_gives_pass(self):
        cal = ConfidenceCalibrator()
        v = cal.verdict_from_confidence(0.85, False, False, True)
        assert v == AIVerdict.PASS

    def test_low_confidence_gives_fail(self):
        cal = ConfidenceCalibrator()
        v = cal.verdict_from_confidence(0.30, False, False, True)
        assert v == AIVerdict.FAIL
