"""
test_runtime_monitor.py - Tests for runtime health/crash monitoring.
"""

from __future__ import annotations

import sys
import time

from qa_ai.runtime_lab.process_manager import ProcessManager
from qa_ai.runtime_lab.runtime_monitor import RuntimeMonitor


class TestRuntimeMonitor:
    def test_runtime_crash_detection(self, artifact_store, tmp_dir):
        manager = ProcessManager(runtime_dir=tmp_dir / "runtime")
        proc = manager.start_process(
            [sys.executable, "-c", "import sys; sys.stderr.write('error line\\n'); sys.exit(1)"]
        )
        time.sleep(0.1)

        monitor = RuntimeMonitor(artifact_store, manager)
        report = monitor.monitor(
            process_id=proc["process_id"],
            app_name="crashy",
            duration_seconds=0.4,
            poll_interval=0.1,
            expect_running=True,
        )

        assert report["crashed"] is True
        assert artifact_store.artifact_exists("runtime_monitor_report")
