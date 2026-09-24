"""
test_browser_pool.py - Tests for runtime lab browser session pooling.
"""

import qa_ai.runtime_lab.browser_pool as browser_pool_module
from qa_ai.runtime_lab.browser_pool import BrowserPool


class TestBrowserPool:
    def test_browser_session_lifecycle(self, artifact_store, monkeypatch):
        class FakeEngine:
            def __init__(self, artifact_store, config):
                self.artifact_store = artifact_store
                self.config = config
                self.closed = False

            def launch(self):
                return True

            def close(self):
                self.closed = True

        monkeypatch.setattr(browser_pool_module, "PlaywrightEngine", FakeEngine)
        pool = BrowserPool(artifact_store)

        created = pool.create_session(headless=True)
        assert created["status"] == "ready"
        assert pool.list_sessions()["count"] == 1

        closed = pool.close_all()
        assert closed["closed_sessions"] == 1
        assert pool.list_sessions()["count"] == 0
