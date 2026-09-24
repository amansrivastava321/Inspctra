"""
test_evidence_collector.py - Tests for the EvidenceCollector.
Validates evidence capture, storage, and indexing.
"""

import pytest
from pathlib import Path

from qa_ai.evidence.evidence_collector import EvidenceCollector, EvidenceItem
from qa_ai.evidence.evidence_registry import EvidenceRegistry, EvidenceRecord
from qa_ai.runtime.artifact_store import ArtifactStore


class TestEvidenceCollector:
    def test_capture_api_response(self, artifact_store):
        collector = EvidenceCollector(artifact_store, run_id="test-run")

        item = collector.capture_api_response(
            test_id="TEST-0001",
            test_title="GET /users",
            method="GET",
            url="http://localhost:8000/users",
            response_status=200,
            response_body=[{"id": 1}],
            duration_ms=45.2,
        )

        assert item.evidence_type == "api_response"
        assert item.test_id == "TEST-0001"
        assert item.metadata["status"] == 200
        assert len(collector.get_all()) == 1

    def test_capture_screenshot(self, artifact_store):
        collector = EvidenceCollector(artifact_store, run_id="test-run")
        image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        item = collector.capture_screenshot(
            test_id="TEST-0002",
            test_title="Home page loads",
            image_bytes=image_bytes,
            description="Screenshot after page load",
        )

        assert item.evidence_type == "screenshot"
        assert item.metadata["size_bytes"] == len(image_bytes)

    def test_capture_log(self, artifact_store):
        collector = EvidenceCollector(artifact_store, run_id="test-run")

        item = collector.capture_log(
            test_id="TEST-0003",
            test_title="API test",
            log_content="INFO: Request sent\nINFO: Response 200\n",
        )

        assert item.evidence_type == "log"

    def test_capture_console(self, artifact_store):
        collector = EvidenceCollector(artifact_store, run_id="test-run")

        messages = [
            {"type": "log", "text": "Page loaded"},
            {"type": "error", "text": "TypeError: undefined"},
        ]

        item = collector.capture_console("TEST-0004", messages)

        assert item.evidence_type == "console"
        assert item.metadata["message_count"] == 2

    def test_capture_error(self, artifact_store):
        collector = EvidenceCollector(artifact_store, run_id="test-run")

        try:
            raise ValueError("test error")
        except ValueError as e:
            item = collector.capture_error(
                test_id="TEST-0005",
                test_title="Failing test",
                error=e,
                context="test suite",
            )

        assert item.evidence_type == "error"
        assert "ValueError" in item.description

    def test_get_for_test(self, artifact_store):
        collector = EvidenceCollector(artifact_store, run_id="test-run")

        collector.capture_api_response(
            test_id="TEST-001", test_title="A", method="GET", url="/a", response_status=200,
        )
        collector.capture_api_response(
            test_id="TEST-001", test_title="A", method="POST", url="/a", response_status=201,
        )
        collector.capture_api_response(
            test_id="TEST-002", test_title="B", method="GET", url="/b", response_status=200,
        )

        assert len(collector.get_for_test("TEST-001")) == 2
        assert len(collector.get_for_test("TEST-002")) == 1
        assert len(collector.get_for_test("TEST-999")) == 0

    def test_save_index(self, artifact_store):
        collector = EvidenceCollector(artifact_store, run_id="test-run")
        collector.capture_api_response(
            test_id="T1", test_title="A", method="GET", url="/x", response_status=200,
        )
        collector.save_index()

        index = artifact_store.load_artifact("evidence_index")
        assert index is not None
        assert index["total_items"] == 1
        assert index["by_type"]["api_response"] == 1

    def test_unique_evidence_ids(self, artifact_store):
        collector = EvidenceCollector(artifact_store, run_id="run-1")
        item1 = collector.capture_api_response(
            test_id="T1", test_title="A", method="GET", url="/a", response_status=200,
        )
        item2 = collector.capture_api_response(
            test_id="T2", test_title="B", method="GET", url="/b", response_status=200,
        )
        assert item1.evidence_id != item2.evidence_id


class TestEvidenceRegistry:
    def test_register_and_get(self, artifact_store):
        registry = EvidenceRegistry(artifact_store)

        record = registry.register(
            evidence_id="ev-001",
            evidence_type="api_response",
            filename="test.json",
            path="evidence/api_responses/test.json",
            test_id="TEST-001",
            test_title="GET /users",
            description="200 OK",
        )

        assert record.evidence_id == "ev-001"
        assert registry.get_by_id("ev-001") is not None
        assert registry.get_by_id("ev-999") is None

    def test_get_by_test(self, artifact_store):
        registry = EvidenceRegistry(artifact_store)
        registry.register("ev-1", "api_response", "a.json", "a", test_id="T1")
        registry.register("ev-2", "screenshot", "b.png", "b", test_id="T1")
        registry.register("ev-3", "api_response", "c.json", "c", test_id="T2")

        assert len(registry.get_by_test("T1")) == 2
        assert len(registry.get_by_test("T2")) == 1

    def test_get_by_type(self, artifact_store):
        registry = EvidenceRegistry(artifact_store)
        registry.register("ev-1", "api_response", "a.json", "a")
        registry.register("ev-2", "screenshot", "b.png", "b")
        registry.register("ev-3", "api_response", "c.json", "c")

        assert len(registry.get_by_type("api_response")) == 2
        assert len(registry.get_by_type("screenshot")) == 1

    def test_search(self, artifact_store):
        registry = EvidenceRegistry(artifact_store)
        registry.register("ev-1", "api_response", "a.json", "a", description="GET /users returns 200")
        registry.register("ev-2", "screenshot", "b.png", "b", test_title="Login page loads")

        results = registry.search("users")
        assert len(results) == 1

        results = registry.search("login")
        assert len(results) == 1

    def test_summary(self, artifact_store):
        registry = EvidenceRegistry(artifact_store)
        registry.register("ev-1", "api_response", "a.json", "a", test_id="T1")
        registry.register("ev-2", "screenshot", "b.png", "b", test_id="T1")
        registry.register("ev-3", "log", "c.log", "c", test_id="T2")

        s = registry.summary()
        assert s["total"] == 3
        assert s["by_type"]["api_response"] == 1
        assert s["by_test"]["T1"] == 2

    def test_save_and_load(self, artifact_store):
        registry = EvidenceRegistry(artifact_store)
        registry.register("ev-1", "api_response", "a.json", "a", test_id="T1")
        registry.save()

        registry2 = EvidenceRegistry(artifact_store)
        assert registry2.load_index() is True
        assert len(registry2.all()) == 1

    def test_load_empty(self, artifact_store):
        registry = EvidenceRegistry(artifact_store)
        assert registry.load_index() is False
