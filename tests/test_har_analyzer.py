"""
test_har_analyzer.py - Tests for the HARAnalyzer.
Validates detection of failures, slow requests, retry storms, auth failures,
caching issues, and polling loops.
"""

import pytest

from qa_ai.live_execution.har_analyzer import HARAnalyzer, NetworkAnomaly


class TestHARAnalyzer:
    def test_initializes_with_artifact_store(self, artifact_store):
        analyzer = HARAnalyzer(artifact_store)
        assert analyzer.store is artifact_store

    def test_returns_analysis_structure(self, artifact_store):
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace={"entries": []})

        assert "metadata" in result
        assert "anomalies" in result
        assert "summary" in result
        assert result["metadata"]["analysis_type"] == "har_analysis"

    def test_detects_failed_requests(self, artifact_store):
        trace = {
            "entries": [
                {"method": "GET", "url": "/api/users", "status_code": 200, "duration_ms": 50},
                {"method": "GET", "url": "/api/fail", "status_code": 500, "duration_ms": 100},
                {"method": "POST", "url": "/api/data", "status_code": 400, "duration_ms": 30},
            ],
        }
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace=trace)

        failures = [a for a in result["anomalies"] if a["anomaly_type"] == "failed_request"]
        assert len(failures) == 2

    def test_detects_slow_requests(self, artifact_store):
        trace = {
            "entries": [
                {"method": "GET", "url": "/fast", "status_code": 200, "duration_ms": 100},
                {"method": "GET", "url": "/slow", "status_code": 200, "duration_ms": 5000},
            ],
        }
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace=trace, slow_threshold_ms=1000)

        slow = [a for a in result["anomalies"] if a["anomaly_type"] == "slow_request"]
        assert len(slow) == 1
        assert slow[0]["url"] == "/slow"

    def test_detects_retry_storms(self, artifact_store):
        trace = {
            "entries": [
                {"method": "GET", "url": "/api/data", "status_code": 200, "duration_ms": 50},
                {"method": "GET", "url": "/api/data", "status_code": 200, "duration_ms": 50},
                {"method": "GET", "url": "/api/data", "status_code": 200, "duration_ms": 50},
                {"method": "GET", "url": "/api/data", "status_code": 200, "duration_ms": 50},
            ],
        }
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace=trace, retry_threshold=3)

        storms = [a for a in result["anomalies"] if a["anomaly_type"] == "retry_storm"]
        assert len(storms) >= 1

    def test_detects_auth_failures(self, artifact_store):
        trace = {
            "entries": [
                {"method": "GET", "url": "/api/protected", "status_code": 401, "duration_ms": 30},
                {"method": "GET", "url": "/api/admin", "status_code": 403, "duration_ms": 20},
                {"method": "GET", "url": "/api/public", "status_code": 200, "duration_ms": 50},
            ],
        }
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace=trace)

        auth = [a for a in result["anomalies"] if a["anomaly_type"] == "auth_failure"]
        assert len(auth) == 2

    def test_detects_caching_issues(self, artifact_store):
        trace = {
            "entries": [
                {
                    "method": "GET",
                    "url": "/static/app.js",
                    "status_code": 200,
                    "duration_ms": 100,
                    "response_headers": {},
                },
                {
                    "method": "GET",
                    "url": "/static/style.css",
                    "status_code": 200,
                    "duration_ms": 50,
                    "response_headers": {"Cache-Control": "max-age=3600"},
                },
            ],
        }
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace=trace)

        caching = [a for a in result["anomalies"] if a["anomaly_type"] == "caching_issue"]
        assert len(caching) == 1  # app.js missing cache headers

    def test_handles_empty_trace(self, artifact_store):
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace={"entries": []})

        assert result["summary"]["total_anomalies"] == 0

    def test_artifacts_written(self, artifact_store):
        analyzer = HARAnalyzer(artifact_store)
        analyzer.run(network_trace={"entries": []})

        assert artifact_store.artifact_exists("har_analysis")

    def test_summary_by_severity(self, artifact_store):
        trace = {
            "entries": [
                {"method": "GET", "url": "/a", "status_code": 500, "duration_ms": 50},  # critical
                {"method": "GET", "url": "/b", "status_code": 400, "duration_ms": 50},  # high
            ],
        }
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace=trace)

        assert "by_severity" in result["summary"]
        assert result["summary"]["by_severity"].get("critical", 0) >= 1

    def test_summary_by_type(self, artifact_store):
        trace = {
            "entries": [
                {"method": "GET", "url": "/a", "status_code": 500, "duration_ms": 50},
                {"method": "GET", "url": "/b", "status_code": 401, "duration_ms": 50},
            ],
        }
        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run(network_trace=trace)

        assert "by_type" in result["summary"]

    def test_network_anomaly_to_dict(self):
        anomaly = NetworkAnomaly(
            anomaly_type="failed_request",
            severity="critical",
            description="HTTP 500 on GET /api/fail",
            url="/api/fail",
            metadata={"status_code": 500},
        )
        d = anomaly.to_dict()
        assert d["anomaly_type"] == "failed_request"
        assert d["severity"] == "critical"
        assert d["metadata"]["status_code"] == 500

    def test_loads_from_artifact_store(self, artifact_store):
        trace = {
            "entries": [
                {"method": "GET", "url": "/ok", "status_code": 200, "duration_ms": 50},
            ],
        }
        artifact_store.save_artifact("network_trace", trace)

        analyzer = HARAnalyzer(artifact_store)
        result = analyzer.run()  # Should load from store

        assert result["metadata"]["total_entries"] == 1
