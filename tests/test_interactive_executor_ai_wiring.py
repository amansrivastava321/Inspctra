"""
test_interactive_executor_ai_wiring.py

Tests that InteractionExecutor correctly wires ai_runtime modules into the live loop.

Key invariants:
  - AI-only PASS blocked (EvidenceGrounder returns UNCLEAR when no evidence)
  - Deterministic failure overrides AI oracle
  - Safety filter hard-block skips action (no execute)
  - Approval denied writes blocked step (no execute)
  - Default mode (no ai_* modules) runs deterministic loop unchanged
  - live_guided=True triggers trace writer + narrator
  - Reporter generates AI section when guided_steps present
"""
from __future__ import annotations

import types
from unittest.mock import MagicMock, patch, PropertyMock
from typing import List, Optional

import pytest

from qa_ai.interactive_runtime.schemas import (
    ActionResult,
    ActionStatus,
    AIVerdict,
    EvidenceGroundingConfig,
    GuidedStep,
    InteractiveRuntimeConfig,
    PermissionDecision,
    UIElement,
    ScreenState,
    UIAction,
    VerificationResult,
    VerificationStatus,
)
from qa_ai.interactive_runtime.interaction_executor import (
    InteractionExecutor,
    _ai_verdict_to_verification_status,
    _verification_to_ai_verdict,
)
from qa_ai.interactive_runtime.ai_runtime.evidence_grounder import EvidenceGrounder
from qa_ai.interactive_runtime.ai_runtime.safety_filter import SafetyFilter


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _config(max_actions: int = 3) -> InteractiveRuntimeConfig:
    return InteractiveRuntimeConfig(
        app_name="TestApp",
        app_type="web",
        working_dir="/tmp",
        launch_command="echo test",
        max_actions=max_actions,
        max_duration_seconds=60,
    )


def _stable_screen(title: str = "Home", n_elements: int = 2) -> ScreenState:
    elements = [
        UIElement(
            element_id=f"el{i}", label=f"Button{i}",
            element_type="button", visible=True, enabled=True,
        )
        for i in range(n_elements)
    ]
    return ScreenState(title=title, elements=elements, visible_text=[title])


def _passing_vr() -> VerificationResult:
    return VerificationResult(
        step_id="step-0001",
        overall_status=VerificationStatus.PASSED,
        checks=[],
        passed_count=1,
        failed_count=0,
    )


def _failing_vr() -> VerificationResult:
    return VerificationResult(
        step_id="step-0001",
        overall_status=VerificationStatus.FAILED,
        checks=[],
        passed_count=0,
        failed_count=1,
    )


def _action_result(status: ActionStatus = ActionStatus.EXECUTED) -> ActionResult:
    from qa_ai.interactive_runtime.schemas import RiskLevel
    action = UIAction(
        action_type="click",
        description="click Button0",
        risk_level=RiskLevel.LOW,
    )
    return ActionResult(
        action=action,
        status=status,
        duration_ms=50.0,
    )


def _make_executor(
    config=None,
    max_actions: int = 1,
    ai_grounder=None,
    ai_safety_filter=None,
    ai_curiosity_engine=None,
    ai_action_decider=None,
    ai_oracle=None,
    ai_narrator=None,
    ai_trace_writer=None,
    live_guided: bool = False,
    ai_guided: bool = True,
    approval_decision: PermissionDecision = PermissionDecision.APPROVED_ONCE,
) -> InteractionExecutor:
    cfg = config or _config(max_actions=max_actions)

    session = MagicMock()
    session.session_id = "test-session"

    controller = MagicMock()
    controller.capability_gaps = []
    controller._driver = MagicMock()
    driver_caps = MagicMock()
    driver_caps.backend.value = "null"
    driver_caps.can_observe_screen = False
    driver_caps.can_click = False
    driver_caps.can_type = False
    driver_caps.can_screenshot = False
    driver_caps.status.value = "unavailable"
    controller._driver.capabilities.return_value = driver_caps
    screen_after = _stable_screen("HomeAfter")
    controller.execute.return_value = _action_result()
    controller.execute.return_value.screen_after = screen_after

    observer = MagicMock()
    observer.observe.return_value = _stable_screen()

    planner = MagicMock()
    planner.coverage_items_from_screen.return_value = []
    planner.plan.return_value = [
        UIAction(action_type="click", description="click Button0")
    ]

    pgate = MagicMock()
    agate = MagicMock()
    agate.check.return_value = approval_decision
    agate.audit_trail = []

    verifier = MagicMock()
    verifier.verify.return_value = _passing_vr()

    evidence = MagicMock()
    evidence.build.return_value = MagicMock()

    coverage = MagicMock()
    coverage.all_items.return_value = []
    coverage.find_by_label.return_value = None

    screenshots = MagicMock()
    screenshots.capture_from_driver.return_value = None

    return InteractionExecutor(
        config=cfg,
        session=session,
        controller=controller,
        observer=observer,
        planner=planner,
        permission_gate=pgate,
        approval_gate=agate,
        verifier=verifier,
        evidence_builder=evidence,
        coverage=coverage,
        screenshots=screenshots,
        log_watcher=None,
        interactive=False,
        ai_vision_analyzer=None,
        ai_action_decider=ai_action_decider,
        ai_curiosity_engine=ai_curiosity_engine,
        ai_oracle=ai_oracle,
        ai_evidence_grounder=ai_grounder,
        ai_narrator=ai_narrator,
        ai_trace_writer=ai_trace_writer,
        ai_safety_filter=ai_safety_filter,
        live_guided=live_guided,
        ai_guided=ai_guided,
    )


# ── Tests: verdict mapping helpers ────────────────────────────────────────────

def test_verdict_mapping_pass():
    assert _ai_verdict_to_verification_status(AIVerdict.PASS) == VerificationStatus.PASSED


def test_verdict_mapping_fail():
    assert _ai_verdict_to_verification_status(AIVerdict.FAIL) == VerificationStatus.FAILED


def test_verdict_mapping_unclear():
    assert _ai_verdict_to_verification_status(AIVerdict.UNCLEAR) == VerificationStatus.INCONCLUSIVE


def test_verification_to_ai_verdict_passed():
    assert _verification_to_ai_verdict(VerificationStatus.PASSED) == AIVerdict.PASS


def test_verification_to_ai_verdict_failed():
    assert _verification_to_ai_verdict(VerificationStatus.FAILED) == AIVerdict.FAIL


# ── Tests: AI-only PASS blocked ───────────────────────────────────────────────

def test_ai_only_pass_blocked_returns_unclear():
    """EvidenceGrounder with no evidence forces UNCLEAR — AI oracle alone cannot PASS."""
    grounder = EvidenceGrounder(config=EvidenceGroundingConfig(
        pass_requires_evidence=True,
        ai_only_max_confidence=0.5,
    ))
    from qa_ai.interactive_runtime.schemas import OracleSuggestion
    oracle = OracleSuggestion(
        step_id="s1",
        suggested_verdict=AIVerdict.PASS,
        confidence=0.95,
        is_suggestion_only=True,
    )
    verdict = grounder.ground(
        step_id="s1",
        oracle_suggestion=oracle,
        deterministic_result=None,
        screen_after=None,
    )
    assert verdict.final_status == AIVerdict.UNCLEAR
    assert verdict.confidence <= 0.5
    assert verdict.deterministic_override is False


# ── Tests: deterministic failure overrides AI oracle ─────────────────────────

def test_deterministic_failure_overrides_ai_pass():
    """Deterministic FAIL → FAIL regardless of oracle suggesting PASS."""
    grounder = EvidenceGrounder()
    from qa_ai.interactive_runtime.schemas import OracleSuggestion
    oracle = OracleSuggestion(
        step_id="s2",
        suggested_verdict=AIVerdict.PASS,
        confidence=0.99,
        is_suggestion_only=True,
    )
    verdict = grounder.ground(
        step_id="s2",
        oracle_suggestion=oracle,
        deterministic_result=_failing_vr(),
    )
    assert verdict.final_status == AIVerdict.FAIL
    assert verdict.deterministic_override is True


# ── Tests: safety filter blocks action ────────────────────────────────────────

def test_safety_filter_hard_block_skips_execute():
    """SafetyFilter blocking an action means controller.execute is never called."""
    safety = MagicMock()
    safety_decision = MagicMock()
    safety_decision.blocked = True
    safety_decision.block_reason = "delete keyword"
    safety_decision.requires_approval = False
    safety.evaluate.return_value = safety_decision

    # Curiosity returns a target so we enter the action flow
    curiosity = MagicMock()
    target = MagicMock()
    target.stop_condition_met = False
    target.target_element = UIElement(
        element_id="el0", label="Delete", element_type="button",
        visible=True, enabled=True,
    )
    target.target_label = "Delete"
    target.exploration_reason = "test delete path"
    curiosity.choose_next.return_value = target

    # After the blocked step, curiosity says stop
    stop_target = MagicMock()
    stop_target.stop_condition_met = True
    stop_target.stop_reason = "all tested"
    curiosity.choose_next.side_effect = [target, stop_target]

    ex = _make_executor(
        max_actions=5,
        ai_safety_filter=safety,
        ai_curiosity_engine=curiosity,
    )
    ex.run()
    ex._controller.execute.assert_not_called()


# ── Tests: approval denied writes blocked step ────────────────────────────────

def test_approval_denied_no_execute():
    """Approval gate DENIED → controller.execute never called."""
    curiosity = MagicMock()
    target = MagicMock()
    target.stop_condition_met = False
    target.target_element = UIElement(
        element_id="el0", label="Pay", element_type="button",
        visible=True, enabled=True,
    )
    target.target_label = "Pay"
    target.exploration_reason = "test pay"

    stop_target = MagicMock()
    stop_target.stop_condition_met = True
    stop_target.stop_reason = "done"
    curiosity.choose_next.side_effect = [target, stop_target]

    ex = _make_executor(
        max_actions=5,
        ai_curiosity_engine=curiosity,
        approval_decision=PermissionDecision.DENIED,
    )
    ex.run()
    ex._controller.execute.assert_not_called()


# ── Tests: default mode unchanged ─────────────────────────────────────────────

def test_default_mode_runs_deterministic_loop():
    """No ai_* modules → deterministic _loop() runs; execute is called."""
    ex = _make_executor(
        max_actions=1,
        ai_guided=False,
        live_guided=False,
    )
    ex.run()
    ex._controller.execute.assert_called_once()


# ── Tests: live_guided triggers narrator + trace writer ──────────────────────

def test_live_guided_calls_narrator_and_trace():
    """live_guided=True → narrator.narrate and trace_writer.add_step called per step."""
    narrator = MagicMock()
    narrator.narrate.return_value = ""
    trace = MagicMock()

    curiosity = MagicMock()
    target = MagicMock()
    target.stop_condition_met = False
    target.target_element = UIElement(
        element_id="el0", label="Start", element_type="button",
        visible=True, enabled=True,
    )
    target.target_label = "Start"
    target.exploration_reason = "explore start"

    stop_target = MagicMock()
    stop_target.stop_condition_met = True
    stop_target.stop_reason = "done"
    curiosity.choose_next.side_effect = [target, stop_target]

    ex = _make_executor(
        max_actions=5,
        ai_curiosity_engine=curiosity,
        ai_narrator=narrator,
        ai_trace_writer=trace,
        live_guided=True,
        ai_guided=True,
    )
    ex.run()

    narrator.narrate.assert_called()
    trace.add_step.assert_called()


# ── Tests: guided_steps property populated ────────────────────────────────────

def test_guided_steps_populated_after_run():
    """After AI-guided run, guided_steps contains one entry per executed action."""
    curiosity = MagicMock()
    target = MagicMock()
    target.stop_condition_met = False
    target.target_element = UIElement(
        element_id="el0", label="Feature", element_type="button",
        visible=True, enabled=True,
    )
    target.target_label = "Feature"
    target.exploration_reason = "test feature"

    stop_target = MagicMock()
    stop_target.stop_condition_met = True
    stop_target.stop_reason = "done"
    curiosity.choose_next.side_effect = [target, stop_target]

    ex = _make_executor(
        max_actions=5,
        ai_curiosity_engine=curiosity,
        live_guided=True,
        ai_guided=True,
    )
    ex.run()

    steps = ex.guided_steps
    assert len(steps) >= 1
    assert all(isinstance(s, GuidedStep) for s in steps)


# ── Tests: reporter generates AI section ─────────────────────────────────────

def test_reporter_ai_section_present_when_guided_steps():
    """InteractiveReporter._ai_guided_section_html returns non-empty when steps given."""
    from qa_ai.interactive_runtime.interactive_reporter import InteractiveReporter
    import tempfile, os

    step = GuidedStep(
        step_number=1,
        step_id="step-0001",
        screen_title="Home",
        what_inspectra_sees="2 elements, stable",
        plan="click 'Login'",
        why="test login flow",
        action_taken="click 'Login' — status: success",
        evidence_checked=["screenshot before/after"],
        evidence_found=["1 deterministic checks passed"],
        log_matches=[],
        final_verdict=AIVerdict.PASS,
        confidence_pct=85.0,
    )

    with tempfile.TemporaryDirectory() as tmp:
        reporter = InteractiveReporter(tmp)
        html = reporter._ai_guided_section_html([step])
        assert "AI-Guided Testing" in html
        assert "PASS" in html
        assert "Login" in html


def test_reporter_no_ai_section_when_no_steps():
    """InteractiveReporter._ai_guided_section_html returns empty string with no steps."""
    from qa_ai.interactive_runtime.interactive_reporter import InteractiveReporter
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        reporter = InteractiveReporter(tmp)
        html = reporter._ai_guided_section_html([])
        assert html == ""
