"""
test_process_manager.py - Tests for runtime lab process lifecycle safety.
"""

from __future__ import annotations

import sys
import time

import pytest

from qa_ai.runtime_lab.process_manager import ProcessManager


class TestProcessManager:
    def test_process_lifecycle_tracking(self, tmp_dir):
        manager = ProcessManager(runtime_dir=tmp_dir / "runtime")
        proc = manager.start_process([sys.executable, "-c", "import time; time.sleep(1)"])
        process_id = proc["process_id"]

        assert manager.is_running(process_id) is True
        assert proc["pid"] > 0
        assert proc["command"][0] == sys.executable

        terminated = manager.terminate_process(process_id)
        assert terminated["process_id"] == process_id
        assert manager.is_running(process_id) is False

    def test_enforces_timeouts(self, tmp_dir):
        manager = ProcessManager(runtime_dir=tmp_dir / "runtime")
        proc = manager.start_process(
            [sys.executable, "-c", "import time; time.sleep(2)"],
            timeout_seconds=0.1,
        )
        process_id = proc["process_id"]
        time.sleep(0.2)
        manager.enforce_timeouts()
        refreshed = manager.get_process(process_id)
        assert refreshed is not None
        assert refreshed["timed_out"] is True

    def test_blocks_destructive_commands(self, tmp_dir):
        manager = ProcessManager(runtime_dir=tmp_dir / "runtime")
        with pytest.raises(ValueError):
            manager.start_process(["rm", "-rf", "/"])
