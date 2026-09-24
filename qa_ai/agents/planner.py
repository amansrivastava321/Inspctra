"""
planner.py - Test Planner Agent wrapper.
Provides a class-based interface to the test planner for use by the WorkflowEngine.
Delegates to LLMTestPlanner for the actual work.
"""

from typing import Optional, Dict, Any

from qa_ai.agents.llm_test_planner import LLMTestPlanner
from qa_ai.runtime.artifact_store import ArtifactStore


class TestPlannerAgent:
    """
    Test Planner Agent — generates a test plan from an app_map.

    This wraps LLMTestPlanner to provide the class-based interface
    expected by the WorkflowEngine.
    """

    def __init__(
        self,
        artifact_store: ArtifactStore,
        model: str = "phi4-mini:latest",
    ):
        self.planner = LLMTestPlanner(
            artifact_store=artifact_store,
            model=model,
        )

    def generate_plan(self, app_map: dict) -> Dict[str, Any]:
        """Generate a test plan from the app_map."""
        return self.planner.generate_plan(app_map)
