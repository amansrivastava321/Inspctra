"""
parallel_execution_planner.py - Advisory parallelization planning for workflow phases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore

class ParallelExecutionPlanner:
    """Produces advisory phase batching plan; does not alter execution behavior."""

    def __init__(self, artifact_store: Optional[ArtifactStore] = None):
        self.store = artifact_store

    def plan(self, phases: List[str]) -> Dict[str, Any]:
        phase_list = [str(phase).strip() for phase in phases if str(phase).strip()]
        independent = {"security_audit", "api_audit", "database_audit", "sync_audit", "code_quality_audit", "dependency_audit"}
        group_a = [phase for phase in phase_list if phase in independent]
        group_b = [phase for phase in phase_list if phase not in independent]

        return {
            "advisory_only": True,
            "apply_by_default": False,
            "requires_explicit_approval_to_apply": True,
            "parallel_groups": [
                {"group": "independent_audits", "phases": group_a},
                {"group": "serial_or_dependent", "phases": group_b},
            ],
            "dependency_notes": [
                "No workflow mutation is applied automatically.",
                "Execution order changes must be explicitly approved.",
            ],
            "summary": {
                "total_phases": len(phase_list),
                "parallel_candidate_count": len(group_a),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    def run(self, phases: List[str]) -> Dict[str, Any]:
        plan = self.plan(phases=phases)
        if self.store is not None:
            self.store.save_artifact("parallel_execution_plan", plan, agent="ParallelExecutionPlanner")
        return plan
