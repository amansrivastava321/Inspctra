"""Tests for StepNarrator — prints action, evidence, verdict, no secrets."""
import pytest

from qa_ai.interactive_runtime.ai_runtime.step_narrator import StepNarrator, _redact
from qa_ai.interactive_runtime.schemas import AIVerdict, GuidedStep


def _step(
    verdict: AIVerdict = AIVerdict.PASS,
    confidence: float = 90.0,
    screen: str = "Dashboard",
    action: str = "click AI Briefing",
) -> GuidedStep:
    return GuidedStep(
        step_number=1,
        step_id="step-001",
        screen_title=screen,
        plan="Click the AI Briefing button",
        why="It tests AI content generation",
        permission_needed="ai_provider",
        action_taken=action,
        evidence_checked=["Log tag [AI_ROUTE_SELECTED]", "UI: Cloud AI badge"],
        evidence_found=["Log matched", "Badge visible"],
        log_matches=["[OPENROUTER_RESPONSE] 200"],
        screenshot_after="artifacts/screenshots/step_001.png",
        final_verdict=verdict,
        confidence_pct=confidence,
    )


class TestNarratorOutput:
    def test_narrate_returns_string(self):
        narrator = StepNarrator(silent=True)
        text = narrator.narrate(_step())
        assert isinstance(text, str)
        assert len(text) > 0

    def test_narrate_includes_step_number(self):
        narrator = StepNarrator(silent=True)
        text = narrator.narrate(_step())
        assert "001" in text

    def test_narrate_includes_verdict(self):
        narrator = StepNarrator(silent=True)
        text = narrator.narrate(_step(verdict=AIVerdict.PASS))
        assert "PASS" in text

    def test_narrate_fail_verdict(self):
        narrator = StepNarrator(silent=True)
        text = narrator.narrate(_step(verdict=AIVerdict.FAIL))
        assert "FAIL" in text

    def test_narrate_includes_screen(self):
        narrator = StepNarrator(silent=True)
        text = narrator.narrate(_step(screen="Owner Dashboard"))
        assert "Owner Dashboard" in text

    def test_narrate_includes_confidence(self):
        narrator = StepNarrator(silent=True)
        text = narrator.narrate(_step(confidence=94.0))
        assert "94" in text


class TestSecretRedaction:
    def test_redacts_openrouter_key(self):
        result = _redact("Key: sk-or-abc123def456ghi789jkl012mno345")
        assert "sk-or-" not in result
        assert "[REDACTED]" in result

    def test_redacts_bearer_token(self):
        result = _redact("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")
        assert "eyJhbGciOiJIUzI1NiJ9" not in result

    def test_normal_text_not_redacted(self):
        result = _redact("Dashboard loaded successfully")
        assert result == "Dashboard loaded successfully"

    def test_narrator_does_not_output_secret(self):
        narrator = StepNarrator(silent=True)
        step = _step(action="click with token sk-or-faketoken123456789012345678")
        text = narrator.narrate(step)
        assert "sk-or-" not in text
