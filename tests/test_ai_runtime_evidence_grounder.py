"""Tests for EvidenceGrounder — the authoritative verdict producer.

Rules under test:
  - AI-only → UNCLEAR (never PASS)
  - UI + log evidence can produce PASS
  - Deterministic failure overrides AI oracle PASS
  - Missing evidence lowers confidence
"""
from qa_ai.interactive_runtime.ai_runtime.evidence_grounder import EvidenceGrounder
from qa_ai.interactive_runtime.schemas import (
    AIVerdict,
    EvidenceGroundingConfig,
    OracleSuggestion,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)


def _det_pass(passed: int = 1, failed: int = 0) -> VerificationResult:
    checks = [
        VerificationCheck(
            check_type="ui_text",
            status=VerificationStatus.PASSED if i < passed else VerificationStatus.FAILED,
        )
        for i in range(passed + failed)
    ]
    status = VerificationStatus.PASSED if failed == 0 else VerificationStatus.FAILED
    return VerificationResult(step_id="s1", checks=checks, overall_status=status)


def _det_fail() -> VerificationResult:
    return VerificationResult(
        step_id="s1",
        checks=[VerificationCheck(check_type="ui_text", status=VerificationStatus.FAILED)],
        overall_status=VerificationStatus.FAILED,
    )


def _oracle(verdict: AIVerdict, conf: float = 0.8) -> OracleSuggestion:
    return OracleSuggestion(
        step_id="s1",
        suggested_verdict=verdict,
        confidence=conf,
        reasoning="test",
        is_suggestion_only=True,
    )


class TestAIOnlyIsUnclear:
    def test_no_evidence_produces_unclear(self):
        grounder = EvidenceGrounder()
        result = grounder.ground("s1", oracle_suggestion=_oracle(AIVerdict.PASS))
        assert result.final_status == AIVerdict.UNCLEAR

    def test_no_evidence_confidence_capped(self):
        grounder = EvidenceGrounder(EvidenceGroundingConfig(ai_only_max_confidence=0.5))
        result = grounder.ground("s1", oracle_suggestion=_oracle(AIVerdict.PASS, 0.99))
        assert result.confidence <= 0.50

    def test_oracle_pass_with_no_evidence_stays_unclear(self):
        grounder = EvidenceGrounder()
        result = grounder.ground(
            "s1",
            oracle_suggestion=_oracle(AIVerdict.PASS, 0.95),
            deterministic_result=None,
            screen_after=None,
            log_matches=None,
        )
        assert result.final_status == AIVerdict.UNCLEAR


class TestDeterministicFailureOverrides:
    def test_det_failure_overrides_oracle_pass(self):
        grounder = EvidenceGrounder()
        result = grounder.ground(
            "s1",
            oracle_suggestion=_oracle(AIVerdict.PASS, 0.99),
            deterministic_result=_det_fail(),
        )
        assert result.final_status == AIVerdict.FAIL

    def test_det_failure_sets_deterministic_override_flag(self):
        grounder = EvidenceGrounder()
        result = grounder.ground(
            "s1",
            oracle_suggestion=_oracle(AIVerdict.PASS),
            deterministic_result=_det_fail(),
        )
        assert result.deterministic_override is True

    def test_det_failure_confidence_near_zero(self):
        grounder = EvidenceGrounder()
        result = grounder.ground("s1", deterministic_result=_det_fail())
        assert result.confidence < 0.20


class TestEvidenceCanPass:
    def test_ui_plus_log_evidence_can_pass(self):
        from qa_ai.interactive_runtime.schemas import ScreenState
        grounder = EvidenceGrounder(EvidenceGroundingConfig(require_screenshot_for_ui_actions=False))
        screen = ScreenState(title="Dashboard", visible_text=["Welcome"], elements=[])
        result = grounder.ground(
            "s1",
            oracle_suggestion=_oracle(AIVerdict.PASS),
            deterministic_result=_det_pass(passed=2),
            screen_after=screen,
            log_matches=["[AI_ROUTE_SELECTED]", "[OPENROUTER_RESPONSE] 200"],
        )
        assert result.final_status == AIVerdict.PASS

    def test_pass_has_evidence_sources(self):
        from qa_ai.interactive_runtime.schemas import ScreenState
        grounder = EvidenceGrounder(EvidenceGroundingConfig(require_screenshot_for_ui_actions=False))
        screen = ScreenState(title="Home", visible_text=["loaded"], elements=[])
        result = grounder.ground(
            "s1",
            deterministic_result=_det_pass(passed=1),
            screen_after=screen,
            log_matches=["[SUCCESS]"],
        )
        assert len(result.evidence_sources_used) > 0


class TestMissingEvidenceLowersConfidence:
    def test_no_logs_lowers_confidence(self):
        from qa_ai.interactive_runtime.schemas import ScreenState
        grounder = EvidenceGrounder(EvidenceGroundingConfig(require_screenshot_for_ui_actions=False))
        screen = ScreenState(title="Test", visible_text=["ok"])
        result_with_logs = grounder.ground(
            "s1",
            deterministic_result=_det_pass(),
            screen_after=screen,
            log_matches=["[TAG]"],
        )
        result_no_logs = grounder.ground(
            "s1",
            deterministic_result=_det_pass(),
            screen_after=screen,
            log_matches=None,
        )
        assert result_with_logs.confidence >= result_no_logs.confidence

    def test_missing_evidence_listed(self):
        grounder = EvidenceGrounder()
        result = grounder.ground("s1")
        assert len(result.evidence_sources_missing) > 0
