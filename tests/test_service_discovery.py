"""
test_service_discovery.py - Tests for service readiness discovery behavior.
"""

from qa_ai.runtime_lab.service_discovery import ServiceDiscovery


class TestServiceDiscovery:
    def test_service_readiness_timeout_handling(self):
        discovery = ServiceDiscovery()
        result = discovery.wait_for_service(
            host="127.0.0.1",
            port=65501,
            timeout_seconds=0.5,
        )

        assert result["ready"] is False
        assert result["error"] == "service_readiness_timeout"

    def test_infer_base_url_none_when_no_open_port(self):
        discovery = ServiceDiscovery()
        inferred = discovery.infer_base_url("127.0.0.1", [65502, 65503])
        assert inferred is None
