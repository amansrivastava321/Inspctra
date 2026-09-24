"""
test_cleanup_manager.py - Tests for robust cleanup behavior after failures.
"""

from qa_ai.runtime_lab.cleanup_manager import CleanupManager


class TestCleanupManager:
    def test_cleanup_runs_even_after_failures(self, artifact_store):
        class BrokenProcessManager:
            def terminate_all(self):
                raise RuntimeError("process cleanup failed")

        class BrokenBrowserPool:
            def close_all(self):
                raise RuntimeError("browser cleanup failed")

        manager = CleanupManager(artifact_store)
        report = manager.cleanup(
            process_manager=BrokenProcessManager(),
            browser_pool=BrokenBrowserPool(),
        )

        assert report["success"] is False
        assert len(report["errors"]) >= 1
        assert artifact_store.artifact_exists("cleanup_report")
