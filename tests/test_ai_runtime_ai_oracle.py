"""Tests for AIOracle — suggestion-only, cannot finalize verdicts."""
import pytest

from qa_ai.interactive_runtime.ai_runtime.ai_oracle import AIOracle
from qa_ai.interactive_runtime.schemas import (
    AIGuidanceConfig,
    AIVerdict,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)


def _det_fail():
    return VerificationResult(
        step_id="s1",
        checks=[VerificationCheck(check_type="ui_text", status=VerificationStatus.FAILED)],
        overall_status=VerificationStatus.FAILED,
    )


def _det_pass():
    return VerificationResult(
        step_id="s1",
        checks=[VerificationCheck(check_type="ui_text", status=VerificationStatus.PASSED)],
        overall_status=VerificationStatus.PASSED,
    )


class TestOracleSuggestionOnly:
    def test_result_is_always_suggestion_only(self):
        oracle = AIOracle(AIGuidanceConfig(enabled=False))
        result = oracle.suggest("s1", "click", "outcome", "before", "after")
        assert result.is_suggestion_only is True

    def test_returns_oracle_suggestion_type(self):
        from qa_ai.interactive_runtime.schemas import OracleSuggestion
        oracle = AIOracle(AIGuidanceConfig(enabled=False))
        result = oracle.suggest("s1", "click", "outcome", "before", "after")
        assert isinstance(result, OracleSuggestion)

    def test_step_id_preserved(self):
        oracle = AIOracle(AIGuidanceConfig(enabled=False))
        result = oracle.suggest("step-042", "click btn", "text appears", "", "")
        assert result.step_id == "step-042"


class TestDeterministicShortCircuit:
    def test_det_failure_produces_fail_suggestion(self):
        oracle = AIOracle()
        result = oracle.suggest(
            "s1", "click", "expected",
            "before", "after",
            deterministic_result=_det_fail(),
        )
        assert result.suggested_verdict == AIVerdict.FAIL

    def test_det_failure_high_confidence(self):
        oracle = AIOracle()
        result = oracle.suggest(
            "s1", "click", "expected",
            "before", "after",
            deterministic_result=_det_fail(),
        )
        assert result.confidence >= 0.80

    def test_det_failure_still_suggestion_only(self):
        oracle = AIOracle()
        result = oracle.suggest(
            "s1", "click", "expected",
            "before", "after",
            deterministic_result=_det_fail(),
        )
        assert result.is_suggestion_only is True


class TestCapabilityGapNoModel:
    def test_disabled_config_returns_unclear_by_default(self):
        oracle = AIOracle(AIGuidanceConfig(enabled=False))
        result = oracle.suggest(
            "s1", "click btn", "text appears", "screen A", "screen A",
        )
        # No change detected, no logs → UNCLEAR is expected heuristic
        assert result.suggested_verdict == AIVerdict.UNCLEAR

    def test_disabled_config_has_evidence_gaps(self):
        oracle = AIOracle(AIGuidanceConfig(enabled=False))
        result = oracle.suggest(
            "s1", "click btn", "text appears", "A", "A",
        )
        assert len(result.evidence_gaps) > 0
