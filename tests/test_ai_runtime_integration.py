"""
Integration smoke test: mock screen + AI decider → fake driver → evidence → grounded verdict.

Tests the full AI-native runtime chain without any real app or LLM.
"""
import tempfile
from pathlib import Path

import pytest

from qa_ai.interactive_runtime.ai_runtime.ai_action_decider import AIActionDecider
from qa_ai.interactive_runtime.ai_runtime.ai_oracle import AIOracle
from qa_ai.interactive_runtime.ai_runtime.confidence_calibrator import ConfidenceCalibrator
from qa_ai.interactive_runtime.ai_runtime.curiosity_engine import CuriosityEngine
from qa_ai.interactive_runtime.ai_runtime.evidence_grounder import EvidenceGrounder
from qa_ai.interactive_runtime.ai_runtime.guided_trace_writer import GuidedTraceWriter
from qa_ai.interactive_runtime.ai_runtime.safety_filter import SafetyFilter
from qa_ai.interactive_runtime.ai_runtime.step_narrator import StepNarrator
from qa_ai.interactive_runtime.schemas import (
    AIGuidanceConfig,
    AIVerdict,
    CuriosityConfig,
    EvidenceGroundingConfig,
    GuidedStep,
    RiskLevel,
    ScreenState,
    UIElement,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)


def _mock_screen() -> ScreenState:
    return ScreenState(
        title="Owner Dashboard",
        visible_text=["Welcome", "AI Briefing", "Sync"],
        elements=[
            UIElement(
                label="AI Briefing",
                element_type="button",
                visible=True,
                enabled=True,
                selector="button#ai-briefing",
            ),
            UIElement(
                label="Sync Data",
                element_type="button",
                visible=True,
                enabled=True,
                selector="button#sync",
            ),
            UIElement(
                label="Settings",
                element_type="button",
                visible=True,
                enabled=True,
                selector="button#settings",
            ),
        ],
    )


def _make_det_pass() -> VerificationResult:
    return VerificationResult(
        step_id="step-001",
        checks=[
            VerificationCheck(check_type="ui_text", status=VerificationStatus.PASSED),
            VerificationCheck(check_type="log_tag", status=VerificationStatus.PASSED),
        ],
        overall_status=VerificationStatus.PASSED,
    )


class TestSmokePipeline:
    def test_decider_proposes_action(self):
        decider = AIActionDecider(
            safety_filter=SafetyFilter(),
            curiosity_config=CuriosityConfig(),
        )
        screen = _mock_screen()
        proposal = decider.decide(screen, vision=None, test_objective="AI Briefing")
        assert proposal.proposed_action is not None or proposal.ask_user

    def test_decider_prefers_objective_element(self):
        decider = AIActionDecider(safety_filter=SafetyFilter())
        screen = _mock_screen()
        proposal = decider.decide(screen, vision=None, test_objective="AI Briefing")
        if proposal.proposed_action and proposal.proposed_action.target_element:
            assert "AI" in proposal.proposed_action.target_element.label or proposal.ask_user

    def test_oracle_returns_suggestion_only(self):
        oracle = AIOracle(AIGuidanceConfig(enabled=False))
        suggestion = oracle.suggest(
            "step-001",
            action_description="click AI Briefing",
            expected_outcome="AI content appears",
            screen_before_summary="Dashboard loaded",
            screen_after_summary="AI Briefing panel opened",
            log_snippets=["[OPENROUTER_REQUEST]", "[OPENROUTER_RESPONSE] 200"],
        )
        assert suggestion.is_suggestion_only is True

    def test_grounder_produces_pass_with_evidence(self):
        grounder = EvidenceGrounder(
            EvidenceGroundingConfig(
                pass_requires_evidence=True,
                require_screenshot_for_ui_actions=False,
            )
        )
        from qa_ai.interactive_runtime.schemas import OracleSuggestion
        oracle_sug = OracleSuggestion(
            step_id="step-001",
            suggested_verdict=AIVerdict.PASS,
            reasoning="Screen changed, logs matched",
            confidence=0.75,
            is_suggestion_only=True,
        )
        result = grounder.ground(
            "step-001",
            oracle_suggestion=oracle_sug,
            deterministic_result=_make_det_pass(),
            screen_after=ScreenState(title="Dashboard", visible_text=["Cloud AI"]),
            log_matches=["[OPENROUTER_RESPONSE] 200", "[AI_ROUTE_SELECTED]"],
        )
        assert result.final_status == AIVerdict.PASS
        assert result.confidence > 0.50

    def test_grounder_blocks_ai_only_pass(self):
        grounder = EvidenceGrounder()
        from qa_ai.interactive_runtime.schemas import OracleSuggestion
        oracle_sug = OracleSuggestion(
            step_id="step-001",
            suggested_verdict=AIVerdict.PASS,
            reasoning="Looks good",
            confidence=0.95,
            is_suggestion_only=True,
        )
        result = grounder.ground(
            "step-001",
            oracle_suggestion=oracle_sug,
        )
        assert result.final_status == AIVerdict.UNCLEAR

    def test_guided_trace_written(self, tmp_path):
        writer = GuidedTraceWriter(str(tmp_path))
        writer.start("TestApp", "AI Briefing", "sess-001")

        step = GuidedStep(
            step_number=1,
            step_id="step-001",
            screen_title="Owner Dashboard",
            plan="Click AI Briefing button",
            why="Tests AI content generation",
            action_taken="clicked 'AI Briefing'",
            evidence_checked=["Log: [AI_ROUTE_SELECTED]", "UI: Cloud AI badge"],
            log_matches=["[OPENROUTER_RESPONSE] 200"],
            screenshot_after="artifacts/screenshots/step_001.png",
            final_verdict=AIVerdict.PASS,
            confidence_pct=88.0,
        )
        writer.add_step(step)
        writer.finish(total_pass=1, total_fail=0, total_unclear=0)

        md_path = tmp_path / "live_interactive_trace.md"
        json_path = tmp_path / "live_interactive_trace.json"
        assert md_path.exists()
        assert json_path.exists()

        import json
        data = json.loads(json_path.read_text())
        assert data["steps"][0]["final_verdict"] == "pass"

    def test_narrator_does_not_crash(self):
        narrator = StepNarrator(silent=True)
        step = GuidedStep(
            step_number=1,
            step_id="step-001",
            screen_title="Dashboard",
            action_taken="click AI Briefing",
            final_verdict=AIVerdict.PASS,
            confidence_pct=90.0,
        )
        text = narrator.narrate(step)
        assert "001" in text

    def test_curiosity_engine_finds_target(self):
        engine = CuriosityEngine(CuriosityConfig(max_actions=10))
        screen = _mock_screen()
        target = engine.choose_next(screen, tested_labels=set(), test_objective="AI Briefing")
        assert not target.stop_condition_met
        assert target.target_element is not None
