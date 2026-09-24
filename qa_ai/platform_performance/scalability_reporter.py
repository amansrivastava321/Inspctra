"""
scalability_reporter.py - Aggregates scalability/performance hardening artifacts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.platform_performance.performance_profiler import PerformanceProfiler
from qa_ai.platform_performance.artifact_lifecycle_manager import ArtifactLifecycleManager
from qa_ai.platform_performance.evidence_storage_optimizer import EvidenceStorageOptimizer
from qa_ai.platform_performance.incremental_graph_manager import IncrementalGraphManager
from qa_ai.platform_performance.parallel_execution_planner import ParallelExecutionPlanner
from qa_ai.platform_performance.memory_usage_tracker import MemoryUsageTracker


class ScalabilityReporter:
    """Builds end-to-end scalability report without changing runtime behavior."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        profile = PerformanceProfiler(self.store).run()
        lifecycle = ArtifactLifecycleManager(self.store).run()
        evidence = EvidenceStorageOptimizer(self.store).run()
        workflow = self._load("workflow_result")
        phases = [str(row.get("phase", "")) for row in workflow.get("phases", []) if isinstance(row, dict)]
        parallel = ParallelExecutionPlanner(self.store).run(phases=phases)
        graph_plan = IncrementalGraphManager(self.store).run(changed_files=[])
        memory = MemoryUsageTracker(self.store).run()

        risks = self._derive_scale_risks(
            profile=profile,
            lifecycle=lifecycle,
            evidence=evidence,
            graph_plan=graph_plan,
            memory=memory,
        )

        report = {
            "performance_profile_summary": profile.get("summary", {}),
            "lifecycle_summary": lifecycle.get("summary", {}),
            "evidence_storage_summary": evidence.get("summary", {}),
            "parallel_execution_plan": parallel,
            "incremental_graph_plan": graph_plan,
            "memory_usage_report": memory,
            "scale_risks": risks,
            "artifacts": {
                "performance_profile": "performance_profile.json",
                "workflow_timing_report": "workflow_timing_report.json",
                "artifact_cache_report": "artifact_cache_report.json",
                "artifact_lifecycle_plan": "artifact_lifecycle_plan.json",
                "evidence_storage_report": "evidence_storage_report.json",
                "incremental_graph_plan": "incremental_graph_plan.json",
                "parallel_execution_plan": "parallel_execution_plan.json",
                "memory_usage_report": "memory_usage_report.json",
                "scalability_report": "scalability_report.json",
            },
            "summary": {
                "advisory_only": True,
                "destructive_cleanup_performed": False,
                "risk_count": len(risks),
                "test_suite_size": self._test_count(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("scalability_report", report, agent="ScalabilityReporter")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _derive_scale_risks(
        self,
        profile: Dict[str, Any],
        lifecycle: Dict[str, Any],
        evidence: Dict[str, Any],
        graph_plan: Dict[str, Any],
        memory: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        risks: list[Dict[str, Any]] = []
        slow_count = int(profile.get("workflow_timing", {}).get("slow_phase_count", 0) or 0)
        if slow_count > 0:
            risks.append({"risk": "slow_workflows", "severity": "medium", "count": slow_count})

        archive_candidates = int(lifecycle.get("summary", {}).get("archive_candidates", 0) or 0)
        if archive_candidates > 0:
            risks.append({"risk": "artifact_bloat", "severity": "medium", "count": archive_candidates})

        compaction_candidates = int(evidence.get("summary", {}).get("compaction_candidates", 0) or 0)
        if compaction_candidates > 0:
            risks.append({"risk": "evidence_growth", "severity": "medium", "count": compaction_candidates})

        graph_nodes = int(graph_plan.get("graph_stats", {}).get("nodes", 0) or 0)
        if graph_nodes >= 2500:
            risks.append({"risk": "graph_growth", "severity": "medium", "nodes": graph_nodes})

        max_rss_kb = int(memory.get("metrics", {}).get("max_rss_kb", 0) or 0)
        if max_rss_kb > 800000:
            risks.append({"risk": "memory_pressure", "severity": "high", "max_rss_kb": max_rss_kb})

        if self._test_count() >= 300:
            risks.append({"risk": "test_suite_growth", "severity": "medium", "test_count": self._test_count()})

        return risks

    def _test_count(self) -> int:
        tests_dir = Path("tests")
        if not tests_dir.exists():
            return 0
        return len(list(tests_dir.glob("test_*.py")))
