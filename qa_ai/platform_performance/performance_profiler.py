"""
performance_profiler.py - Consolidated performance profiling for QA-AI artifacts/workflows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.platform_performance.workflow_profiler import WorkflowProfiler
from qa_ai.platform_performance.artifact_cache import ArtifactCacheAnalyzer
from qa_ai.platform_performance.memory_usage_tracker import MemoryUsageTracker


class PerformanceProfiler:
    """Builds performance profile from workflow timing, artifact activity, and memory snapshots."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        timing = WorkflowProfiler(self.store).run()
        cache = ArtifactCacheAnalyzer(self.store).run()
        memory_report = MemoryUsageTracker(self.store).run()
        memory = memory_report.get("metrics", {}) if isinstance(memory_report, dict) else {}

        report = {
            "workflow_timing": timing.get("summary", {}),
            "slow_phases": timing.get("slow_phases", []),
            "artifact_io": {
                "artifact_read_count_estimate": len(self.store.list_artifacts()),
                "artifact_write_count_estimate": len(self.store.list_artifacts()),
                "cache_summary": cache.get("summary", {}),
            },
            "memory_usage": memory,
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "advisory_only": True,
            },
        }
        self.store.save_artifact("performance_profile", report, agent="PerformanceProfiler")
        return report
