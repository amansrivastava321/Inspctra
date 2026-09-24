"""
ui_action_planner.py - Plan UI actions from discovered screen elements.

The planner decides WHAT to do next based on:
- The current ScreenState
- The test objectives from config
- Which functions are already covered
- Risk level of each element
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Optional, Set

from qa_ai.interactive_runtime.schemas import (
    FunctionCoverageItem,
    FunctionStatus,
    RiskLevel,
    ScreenState,
    UIAction,
    UIElement,
)

logger = logging.getLogger(__name__)

# Action types and their risk defaults
_TYPE_RISK: Dict[str, RiskLevel] = {
    "click": RiskLevel.SAFE,
    "type": RiskLevel.SAFE,
    "select": RiskLevel.SAFE,
    "navigate": RiskLevel.SAFE,
    "submit": RiskLevel.MEDIUM,
    "wait": RiskLevel.SAFE,
    "scroll": RiskLevel.SAFE,
}


class UIActionPlanner:
    """
    Generate an ordered list of UIActions from the current screen state.

    Priority:
    1. High-risk / external-triggering buttons (with approval gate)
    2. Core user-journey inputs and forms
    3. Navigation controls
    4. Untested safe buttons
    """

    def __init__(self, test_objectives: Optional[List[str]] = None):
        self._objectives = [o.lower() for o in (test_objectives or [])]

    def plan(
        self,
        screen: ScreenState,
        already_tested: Optional[Set[str]] = None,
        max_actions: int = 20,
    ) -> List[UIAction]:
        """
        Produce an ordered action plan for the current screen.

        Args:
            screen:         Current observed screen state.
            already_tested: Set of element labels already tested (skip).
            max_actions:    Cap on returned actions.

        Returns:
            Ordered list of UIActions ready for approval + execution.
        """
        tested = already_tested or set()
        actions: List[UIAction] = []

        # 1. Elements matching test objectives get priority
        priority_elements = [
            e for e in screen.elements
            if e.enabled and e.visible and self._matches_objective(e.label)
            and e.label not in tested
        ]
        # 2. Remaining untested enabled elements
        remaining = [
            e for e in screen.elements
            if e.enabled and e.visible and e.label not in tested
            and e not in priority_elements
        ]

        all_candidates = priority_elements + remaining
        for element in all_candidates[:max_actions]:
            action = self._element_to_action(element, screen)
            actions.append(action)

        logger.debug("Planned %d actions for screen '%s'", len(actions), screen.title)
        return actions

    def plan_navigation(self, screen: ScreenState, visited_urls: Optional[Set[str]] = None) -> List[UIAction]:
        """Plan navigation actions to unvisited links."""
        visited = visited_urls or set()
        nav_actions: List[UIAction] = []
        for el in screen.elements:
            if el.element_type == "link" and el.visible:
                action = UIAction(
                    action_id=str(uuid.uuid4())[:8],
                    action_type="click",
                    target_element=el,
                    risk_level=RiskLevel.SAFE,
                    requires_approval=False,
                    description=f"Navigate via link: {el.label}",
                )
                nav_actions.append(action)
        return nav_actions

    def create_type_action(
        self,
        element: UIElement,
        value: str,
        step_id: str = "",
    ) -> UIAction:
        return UIAction(
            action_id=str(uuid.uuid4())[:8],
            action_type="type",
            target_element=element,
            input_value=value,
            risk_level=RiskLevel.SAFE,
            requires_approval=False,
            description=f"Type '{value}' into {element.label or 'input'}",
            step_id=step_id,
        )

    def create_wait_action(self, ms: int = 2000) -> UIAction:
        return UIAction(
            action_id=str(uuid.uuid4())[:8],
            action_type="wait",
            wait_ms=ms,
            risk_level=RiskLevel.SAFE,
            requires_approval=False,
            description=f"Wait {ms}ms for app response",
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _element_to_action(self, element: UIElement, screen: ScreenState) -> UIAction:
        action_type = "type" if element.element_type == "input" else "click"
        risk = element.risk_level
        requires_approval = risk in (
            RiskLevel.DESTRUCTIVE, RiskLevel.EXTERNAL_COST, RiskLevel.PRODUCTION_RISK, RiskLevel.HIGH
        )

        return UIAction(
            action_id=str(uuid.uuid4())[:8],
            action_type=action_type,
            target_element=element,
            input_value="test_value" if element.element_type == "input" else None,
            risk_level=risk,
            requires_approval=requires_approval,
            description=f"{action_type.title()} '{element.label or element.element_type}' on {screen.title}",
        )

    def _matches_objective(self, label: str) -> bool:
        label_lower = label.lower()
        return any(obj in label_lower for obj in self._objectives)

    def coverage_items_from_screen(self, screen: ScreenState) -> List[FunctionCoverageItem]:
        """Pre-populate coverage tracker with all discovered elements on this screen."""
        items: List[FunctionCoverageItem] = []
        for el in screen.elements:
            if el.element_type in ("button", "input", "link", "select"):
                items.append(FunctionCoverageItem(
                    item_id=str(uuid.uuid4())[:8],
                    screen=screen.title,
                    element_label=el.label,
                    element_type=el.element_type,
                    action_attempted="",
                    expected_result="",
                    status=FunctionStatus.DISCOVERED,
                ))
        return items
