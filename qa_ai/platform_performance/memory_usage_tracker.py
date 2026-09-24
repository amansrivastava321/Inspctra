"""
memory_usage_tracker.py - Capture safe process memory/time metrics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import os
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class MemoryUsageTracker:
    """Collects coarse process resource metrics without mutating system state."""

    def __init__(self, artifact_store: Optional[ArtifactStore] = None):
        self.store = artifact_store

    def snapshot(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "pid": int(os.getpid()),
            "process_time_seconds": float(time.process_time()),
            "collector": "fallback",
        }

        try:
            import psutil  # type: ignore

            process = psutil.Process()
            mem = process.memory_info()
            cpu = process.cpu_times()
            metrics.update(
                {
                    "collector": "psutil",
                    "rss_bytes": int(getattr(mem, "rss", 0) or 0),
                    "vms_bytes": int(getattr(mem, "vms", 0) or 0),
                    "max_rss_kb": int((getattr(mem, "rss", 0) or 0) / 1024),
                    "user_cpu_seconds": float(getattr(cpu, "user", 0.0) or 0.0),
                    "system_cpu_seconds": float(getattr(cpu, "system", 0.0) or 0.0),
                }
            )
            return metrics
        except Exception as e:
            logger.debug("psutil memory metrics collection failed: %s", e)

        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            metrics.update(
                {
                    "collector": "resource",
                    "max_rss_kb": int(getattr(usage, "ru_maxrss", 0) or 0),
                    "user_cpu_seconds": float(getattr(usage, "ru_utime", 0.0) or 0.0),
                    "system_cpu_seconds": float(getattr(usage, "ru_stime", 0.0) or 0.0),
                }
            )
        except Exception as e:
            logger.debug("resource module memory metrics collection failed: %s", e)
            metrics.update({"max_rss_kb": 0, "user_cpu_seconds": 0.0, "system_cpu_seconds": 0.0})
        return metrics

    def run(self) -> Dict[str, Any]:
        metrics = self.snapshot()
        report = {
            "advisory_only": True,
            "metrics": metrics,
            "summary": {
                "collector": str(metrics.get("collector", "fallback")),
                "captured_at": str(metrics.get("captured_at", "")),
            },
        }
        if self.store is not None:
            self.store.save_artifact("memory_usage_report", report, agent="MemoryUsageTracker")
        return report
