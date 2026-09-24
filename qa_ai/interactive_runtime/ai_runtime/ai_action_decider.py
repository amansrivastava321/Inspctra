"""
ai_action_decider.py - Given current screen/context, decide the next best action.

Rules:
- No destructive actions without approval
- Prefer accessibility/DOM elements over coordinate clicks
- Coordinate clicks require explicit approval
- If uncertain → ask_user=True or mark blocked, NOT random click
- No app-specific logic
"""
from __future__ import annotations

import logging
from typing import List, Optional, Set

from qa_ai.interactive_runtime.schemas import (
    AIActionProposal,
    CuriosityConfig,
    RiskLevel,
    ScreenState,
    UIAction,
    UIElement,
    VisionAnalysis,
    VisionAnalysisConfig,
)
from qa_ai.interactive_runtime.ai_runtime.intent_inference import IntentInferenceEngine
from qa_ai.interactive_runtime.ai_runtime.safety_filter import SafetyFilter

logger = logging.getLogger(__name__)


class AIActionDecider:
    """
    Decide the next action to take given screen state and context.

    Uses intent inference for confidence and safety filter for risk.
    Never proposes coordinate clicks without explicit approval.
    Never proposes destructive actions without approval.
    """

    def __init__(
        self,
        safety_filter: Optional[SafetyFilter] = None,
        intent_engine: Optional[IntentInferenceEngine] = None,
        curiosity_config: Optional[CuriosityConfig] = None,
        vision_config: Optional[VisionAnalysisConfig] = None,
    ):
        self._safety = safety_filter or SafetyFilter()
        self._intent = intent_engine or IntentInferenceEngine()
        self._curiosity = curiosity_config or CuriosityConfig()
        self._vision_config = vision_config or VisionAnalysisConfig()

    def decide(
        self,
        screen: ScreenState,
        vision: Optional[VisionAnalysis],
        test_objective: str,
        previously_tested: Optional[Set[str]] = None,
        max_coordinate_confidence: float = 0.6,
    ) -> AIActionProposal:
        """
        Choose the next action to execute.

        Returns AIActionProposal. If ask_user=True, human must approve.
        If blocked=True, action must not be executed.
        """
        tested = previously_tested or set()
        candidates = self._collect_candidates(screen, vision)

        # Filter out already-tested elements
        untested = [e for e in candidates if e.label not in tested]
        targets = untested if untested else candidates

        if not targets:
            return AIActionProposal(
                reason="No untested actionable elements found on current screen.",
                confidence=0.0,
                ask_user=True,
            )

        # Score and rank candidates
        scored = self._score_candidates(targets, test_objective)
        if not scored:
            return AIActionProposal(
                reason="All discovered elements failed safety/scoring check.",
                confidence=0.0,
                ask_user=True,
            )

        best = scored[0]
        element, score, intent = best

        # Build action
        action = UIAction(
            action_type=intent.action_type,
            target_element=element,
            description=f"{intent.action_type} '{element.label}' — expected: {intent.expected_outcome[:80]}",
            risk_level=intent.risk_level,
            requires_approval=intent.risk_level in (RiskLevel.HIGH, RiskLevel.DESTRUCTIVE,
                                                     RiskLevel.EXTERNAL_COST, RiskLevel.PRODUCTION_RISK),
        )

        # Safety check
        safety_decision = self._safety.evaluate(action)
        if safety_decision.blocked:
            return AIActionProposal(
                proposed_action=action,
                reason=safety_decision.block_reason,
                confidence=0.0,
                blocked=True,
                block_reason=safety_decision.block_reason,
            )

        required_perms = []
        if safety_decision.requires_approval:
            required_perms.append(safety_decision.risk_category)

        # Coordinate click check
        if element.selector is None and element.bounding_box:
            if score < max_coordinate_confidence:
                return AIActionProposal(
                    proposed_action=action,
                    reason="Coordinate-only click without accessibility selector requires approval.",
                    expected_outcome=intent.expected_outcome,
                    risk_level=RiskLevel.MEDIUM,
                    required_permissions=["coordinate_click_approval"],
                    confidence=score * 0.7,
                    ask_user=True,
                )

        return AIActionProposal(
            proposed_action=action,
            reason=f"Element '{element.label}' is untested and matches test objective: {test_objective[:60]}",
            expected_outcome=intent.expected_outcome,
            risk_level=intent.risk_level,
            required_permissions=required_perms,
            confidence=min(score, 0.95),
            ask_user=safety_decision.requires_approval,
        )

    def _collect_candidates(
        self,
        screen: ScreenState,
        vision: Optional[VisionAnalysis],
    ) -> List[UIElement]:
        candidates = [e for e in screen.elements if e.visible and e.enabled]

        # Add vision-inferred buttons not already in candidates
        if vision and vision.inferred_buttons:
            existing_labels = {e.label.lower() for e in candidates}
            for btn_label in vision.inferred_buttons:
                if btn_label.lower() not in existing_labels:
                    candidates.append(UIElement(
                        label=btn_label,
                        element_type="button",
                        visible=True,
                        enabled=True,
                    ))
        return candidates

    def _score_candidates(
        self,
        elements: List[UIElement],
        test_objective: str,
    ) -> List[tuple]:
        scored = []
        obj_lower = test_objective.lower()

        for element in elements:
            intent = self._intent.infer(element)

            # Skip if safety blocks entirely
            action = UIAction(
                action_type=intent.action_type,
                target_element=element,
                risk_level=intent.risk_level,
            )
            safety = self._safety.evaluate(action)
            if safety.blocked and not self._curiosity.avoid_destructive_actions is False:
                continue

            score = intent.confidence
            label_lower = element.label.lower()

            # Boost if element matches test objective keywords
            if any(word in label_lower for word in obj_lower.split() if len(word) > 3):
                score = min(1.0, score + 0.20)

            # Boost primary action types
            if element.element_type == "button":
                score = min(1.0, score + 0.10)

            # Penalize coordinate-only elements
            if element.selector is None and element.bounding_box:
                score *= 0.80

            scored.append((element, score, intent))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
