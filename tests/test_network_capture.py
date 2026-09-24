"""
test_network_capture.py - Tests for the NetworkCapture.
Validates request/response capture, failure detection, HAR export, and trace saving.
"""

import pytest

from qa_ai.live_execution.network_capture import NetworkCapture, NetworkEntry


class TestNetworkCapture:
    def test_initializes_with_artifact_store(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        assert capture.store is artifact_store

    def test_capture_creates_entry(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        capture.start()

        entry = capture.capture(
            method="GET",
            url="http://localhost:8000/users",
            status_code=200,
            duration_ms=50.0,
        )

        assert isinstance(entry, NetworkEntry)
        assert entry.method == "GET"
        assert entry.status_code == 200
        assert len(capture.get_all()) == 1

    def test_capture_failed_entry(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        capture.start()

        capture.capture(method="GET", url="/api/fail", status_code=500)
        capture.capture(method="GET", url="/api/ok", status_code=200)

        assert len(capture.get_all()) == 2
        assert len(capture.get_failed()) == 1
        assert capture.get_failed()[0].status_code == 500

    def test_capture_error_entry(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        capture.start()

        capture.capture(method="GET", url="/api/timeout", status_code=0, error="Connection timeout")

        assert len(capture.get_failed()) == 1

    def test_get_slow(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        capture.start()

        capture.capture(method="GET", url="/fast", status_code=200, duration_ms=100)
        capture.capture(method="GET", url="/slow", status_code=200, duration_ms=5000)

        slow = capture.get_slow(threshold_ms=1000)
        assert len(slow) == 1
        assert slow[0].url == "/slow"

    def test_save_trace(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        capture.start()

        capture.capture(method="GET", url="/api/users", status_code=200, duration_ms=50)
        capture.capture(method="POST", url="/api/login", status_code=401, duration_ms=30)

        trace = capture.save_trace()

        assert trace["metadata"]["total_requests"] == 2
        assert trace["metadata"]["failed_requests"] == 1
        assert len(trace["entries"]) == 2
        assert artifact_store.artifact_exists("network_trace")

    def test_export_har(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        capture.start()

        capture.capture(
            method="GET",
            url="/api/users",
            status_code=200,
            request_headers={"Accept": "application/json"},
            response_headers={"Content-Type": "application/json"},
            duration_ms=45.0,
        )

        har = capture.export_har()
        assert "log" in har
        assert har["log"]["version"] == "1.2"
        assert len(har["log"]["entries"]) == 1
        assert har["log"]["entries"][0]["request"]["method"] == "GET"

    def test_summary(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        capture.start()

        capture.capture(method="GET", url="/a", status_code=200, duration_ms=100)
        capture.capture(method="POST", url="/b", status_code=201, duration_ms=200)
        capture.capture(method="GET", url="/c", status_code=500, duration_ms=300)

        trace = capture.save_trace()
        summary = trace["summary"]

        assert summary["total_requests"] == 3
        assert summary["failed_requests"] == 1
        assert "2xx" in summary["status_distribution"]
        assert "5xx" in summary["status_distribution"]
        assert "GET" in summary["method_distribution"]

    def test_start_clears_previous(self, artifact_store):
        capture = NetworkCapture(artifact_store)
        capture.start()
        capture.capture(method="GET", url="/a", status_code=200)

        capture.start()
        assert len(capture.get_all()) == 0

    def test_network_entry_to_dict(self, artifact_store):
        entry = NetworkEntry(
            method="POST",
            url="/login",
            status_code=401,
            duration_ms=25.0,
            error="Unauthorized",
        )
        d = entry.to_dict()
        assert d["method"] == "POST"
        assert d["status_code"] == 401
        assert d["error"] == "Unauthorized"

    def test_network_entry_to_har_entry(self, artifact_store):
        entry = NetworkEntry(
            method="GET",
            url="/users",
            status_code=200,
            request_headers={"Accept": "application/json"},
            response_headers={"Content-Type": "application/json"},
            duration_ms=50.0,
        )
        har = entry.to_har_entry()
        assert har["request"]["method"] == "GET"
        assert har["response"]["status"] == 200
        assert har["time"] == 50.0
