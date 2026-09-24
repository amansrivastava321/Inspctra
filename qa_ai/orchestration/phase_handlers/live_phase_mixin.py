"""
live_phase_mixin.py - Live execution phase methods for WorkflowEngine.
Extracted from workflow_engine.py. All methods require WorkflowEngine instance state.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    pass  # Avoid circular imports


class LivePhaseMixin:
    """Mixin providing live execution phase methods for WorkflowEngine."""

    def _run_live_scenario_execution(self) -> Dict[str, Any]:
        """Live scenario execution phase: run scenarios with real browser."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.live_execution.live_scenario_runner import LiveScenarioRunner
        from qa_ai.config.settings import get_settings as _get_settings

        self.context.transition_to(AuditPhase.EXECUTION)

        runner = LiveScenarioRunner(
            artifact_store=self.store,
            config={
                "base_url": getattr(self.context, "app_url", None) or _get_settings().app_base_url,
                "headless": True,
            },
        )
        result = runner.run(base_url=getattr(self.context, "app_url", None))
        return result

    def _run_trace_capture(self) -> Dict[str, Any]:
        """Trace capture phase: finalize and index execution traces."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.live_execution.trace_recorder import TraceRecorder

        self.context.transition_to(AuditPhase.EVIDENCE)

        recorder = TraceRecorder(artifact_store=self.store)
        # Load any existing execution trace events
        existing_trace = self._load_validated_artifact("execution_trace", {})
        if isinstance(existing_trace, dict) and "events" in existing_trace:
            for event in existing_trace["events"]:
                recorder.record_step(
                    action=event.get("action", ""),
                    target=event.get("target", ""),
                    result=event.get("result", ""),
                    status=event.get("status", "success"),
                    duration_ms=event.get("duration_ms", 0.0),
                )
        result = recorder.save_trace()
        return result

    def _run_replay_analysis(self) -> Dict[str, Any]:
        """Replay analysis phase: compare current vs previous execution traces."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.live_execution.replay_engine import ReplayEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        engine = ReplayEngine(artifact_store=self.store)
        result = engine.run()
        return result

    def _run_visual_regression(self) -> Dict[str, Any]:
        """Visual regression phase: compare screenshots for visual changes."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.live_execution.visual_regression import VisualRegression

        self.context.transition_to(AuditPhase.ANALYSIS)

        regression = VisualRegression(artifact_store=self.store)
        # No screenshots to compare by default - this phase becomes useful
        # when screenshots are captured during live scenario execution
        result = regression.run(current_screenshots={})
        return result
