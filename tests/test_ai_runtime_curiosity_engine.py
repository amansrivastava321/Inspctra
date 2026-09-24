"""Tests for CuriosityEngine — prioritizes untested elements, avoids destructive."""
import pytest

from qa_ai.interactive_runtime.ai_runtime.curiosity_engine import CuriosityEngine
from qa_ai.interactive_runtime.schemas import (
    CuriosityConfig,
    RiskLevel,
    ScreenState,
    UIElement,
)


def _screen(*buttons: str) -> ScreenState:
    return ScreenState(
        title="TestScreen",
        elements=[
            UIElement(label=b, element_type="button", visible=True, enabled=True)
            for b in buttons
        ],
    )


class TestPrioritizesUntested:
    def test_prefers_untested_elements(self):
        engine = CuriosityEngine()
        screen = _screen("AI Briefing", "Settings", "Dashboard")
        target = engine.choose_next(screen, tested_labels={"Settings"}, test_objective="AI Briefing")
        assert target.target_label != "Settings"

    def test_no_untested_returns_stop(self):
        engine = CuriosityEngine()
        screen = _screen("Settings")
        target = engine.choose_next(screen, tested_labels={"Settings"})
        assert target.stop_condition_met is True

    def test_objective_keyword_boosts_priority(self):
        engine = CuriosityEngine()
        screen = _screen("AI Briefing", "Random Button")
        target = engine.choose_next(screen, tested_labels=set(), test_objective="AI Briefing")
        assert "AI Briefing" in target.target_label or target.priority_score >= 0.80


class TestAvoidDestructive:
    def test_delete_skipped_when_avoid_destructive(self):
        engine = CuriosityEngine(CuriosityConfig(avoid_destructive_actions=True))
        screen = ScreenState(
            title="Test",
            elements=[
                UIElement(
                    label="Delete All",
                    element_type="button",
                    visible=True,
                    enabled=True,
                    risk_level=RiskLevel.DESTRUCTIVE,
                ),
                UIElement(
                    label="View Report",
                    element_type="button",
                    visible=True,
                    enabled=True,
                ),
            ],
        )
        target = engine.choose_next(screen, tested_labels=set())
        assert target.stop_condition_met or target.target_label != "Delete All"

    def test_safe_elements_explored(self):
        engine = CuriosityEngine(CuriosityConfig(avoid_destructive_actions=True))
        screen = _screen("Dashboard", "Settings")
        target = engine.choose_next(screen, tested_labels=set())
        assert not target.stop_condition_met


class TestStopsAtMaxActions:
    def test_stops_at_max_actions(self):
        config = CuriosityConfig(max_actions=2)
        engine = CuriosityEngine(config)
        screen = _screen("A", "B", "C")
        # Exhaust budget
        engine._action_count = 100
        target = engine.choose_next(screen, tested_labels=set())
        assert target.stop_condition_met is True
        assert "budget" in target.stop_reason.lower()
