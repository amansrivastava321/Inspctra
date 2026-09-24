"""
curiosity_engine.py - Choose what to explore next without hardcoded workflows.

Priority order:
  1. Untested high-risk elements (DELETE, PAYMENT, etc.)
  2. Primary actions/buttons matching test objective
  3. Forms and inputs
  4. Navigation paths
  5. AI/backend/database-triggering actions
  6. Low-risk settings/actions
  7. Avoid destructive actions unless approved

No app-specific logic. Objective is passed by config.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Set

from qa_ai.interactive_runtime.schemas import (
    CuriosityConfig,
    CuriosityTarget,
    FunctionCoverageItem,
    FunctionStatus,
    IntentCategory,
    RiskLevel,
    ScreenState,
    UIElement,
)
from qa_ai.interactive_runtime.ai_runtime.intent_inference import IntentInferenceEngine

logger = logging.getLogger(__name__)

_HIGH_PRIORITY_TYPES = frozenset(["button"])
_MEDIUM_PRIORITY_TYPES = frozenset(["link", "select", "input", "tab"])

_AI_RISK_CATEGORIES = frozenset([
    IntentCategory.GENERATE_AI_CONTENT,
    IntentCategory.SYNC,
])


class CuriosityEngine:
    """
    Drive exploration of untested UI paths.

    Choose next target based on coverage gaps, screen state, and risk profile.
    Stop when budget exhausted, all elements tested, or stop condition met.
    """

    def __init__(
        self,
        config: Optional[CuriosityConfig] = None,
        intent_engine: Optional[IntentInferenceEngine] = None,
    ):
        self._config = config or CuriosityConfig()
        self._intent = intent_engine or IntentInferenceEngine()
        self._action_count = 0

    def choose_next(
        self,
        screen: ScreenState,
        tested_labels: Set[str],
        previous_failures: Optional[List[str]] = None,
        test_objective: str = "",
        coverage_items: Optional[List[FunctionCoverageItem]] = None,
    ) -> CuriosityTarget:
        """
        Choose next element to explore.

        Returns CuriosityTarget. stop_condition_met=True means stop exploration.
        """
        self._action_count += 1

        # Check stop conditions
        stop = self._check_stop(screen, tested_labels)
        if stop:
            return stop

        candidates = self._score_candidates(
            screen.elements, tested_labels, test_objective, coverage_items or []
        )

        if not candidates:
            return CuriosityTarget(
                stop_condition_met=True,
                stop_reason="No more explorable elements on this screen.",
            )

        best = candidates[0]
        element, score, reason = best

        return CuriosityTarget(
            target_element=element,
            target_label=element.label,
            exploration_reason=reason,
            priority_score=score,
            stop_condition_met=False,
        )

    def _check_stop(
        self, screen: ScreenState, tested_labels: Set[str]
    ) -> Optional[CuriosityTarget]:
        if self._action_count > self._config.max_actions:
            return CuriosityTarget(
                stop_condition_met=True,
                stop_reason=f"Action budget exhausted ({self._config.max_actions} max).",
            )

        visible_actionable = [
            e for e in screen.elements
            if e.visible and e.enabled and e.element_type in _HIGH_PRIORITY_TYPES | _MEDIUM_PRIORITY_TYPES
        ]
        if visible_actionable and all(e.label in tested_labels for e in visible_actionable):
            return CuriosityTarget(
                stop_condition_met=True,
                stop_reason="All visible actionable elements on screen have been tested.",
            )

        return None

    def _score_candidates(
        self,
        elements: List[UIElement],
        tested_labels: Set[str],
        test_objective: str,
        coverage_items: List[FunctionCoverageItem],
    ) -> List[tuple]:
        failed_labels = {
            item.element_label for item in coverage_items
            if item.status == FunctionStatus.FAILED
        }

        scored = []
        obj_words = set(w.lower() for w in test_objective.split() if len(w) > 3)

        for element in elements:
            if not element.visible or not element.enabled:
                continue

            label = element.label
            intent = self._intent.infer(element)
            score = 0.0
            reason = ""

            # Skip destructive if configured
            if (
                self._config.avoid_destructive_actions
                and intent.risk_level in (RiskLevel.DESTRUCTIVE, RiskLevel.PRODUCTION_RISK)
            ):
                continue

            # Priority 1: untested high-risk (non-destructive)
            if label not in tested_labels and intent.risk_level in (RiskLevel.HIGH, RiskLevel.EXTERNAL_COST):
                score = 0.90
                reason = f"Untested high-risk element '{label}' — priority exploration."

            # Priority 2: untested and matches objective
            elif label not in tested_labels and obj_words and any(w in label.lower() for w in obj_words):
                score = 0.85
                reason = f"Matches test objective: '{label}' aligns with '{test_objective[:40]}'."

            # Priority 3: untested primary buttons
            elif label not in tested_labels and element.element_type == "button":
                score = 0.75
                reason = f"Untested primary action: '{label}'."

            # Priority 4: untested forms
            elif label not in tested_labels and element.element_type in ("input", "select"):
                score = 0.65
                reason = f"Untested form element: '{label}'."

            # Priority 5: untested navigation
            elif label not in tested_labels and element.element_type in ("link", "tab"):
                score = 0.55
                reason = f"Untested navigation path: '{label}'."

            # Priority 6: AI/backend-triggering (even if tested, re-explore on objective match)
            elif intent.intent_category in _AI_RISK_CATEGORIES and obj_words and any(
                w in label.lower() for w in obj_words
            ):
                score = 0.50
                reason = f"AI-triggering element '{label}' matches objective."

            # Previously failed — re-try for confirmation
            elif label in failed_labels:
                score = 0.40
                reason = f"Previous failure on '{label}' — confirming."

            # Low-risk settings
            elif label not in tested_labels and intent.risk_level == RiskLevel.SAFE:
                score = 0.30
                reason = f"Unexplored safe element: '{label}'."

            else:
                continue  # Already tested and no re-try reason

            scored.append((element, score, reason))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
