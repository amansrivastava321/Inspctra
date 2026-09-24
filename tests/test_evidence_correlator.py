"""
test_evidence_correlator.py - Tests for the RuntimeEvidenceCorrelator.
Validates evidence graph construction, node types, edge linking,
and artifact persistence.
"""

import pytest

from qa_ai.runtime_intelligence.evidence_correlator import (
    RuntimeEvidenceCorrelator,
    EvidenceNode,
)


class TestRuntimeEvidenceCorrelator:
    def test_initializes_with_artifact_store(self, artifact_store):
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        assert correlator.store is artifact_store

    def test_returns_graph_structure(self, artifact_store):
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings={}, execution_results={}, app_map={})

        assert "metadata" in result
        assert "graph" in result
        assert "summary" in result
        assert result["metadata"]["correlation_type"] == "evidence_correlation"

    def test_creates_finding_nodes(self, artifact_store):
        verified = {
            "verified_findings": [
                {"id": "F1", "title": "Missing auth", "severity": "high", "category": "authentication"},
                {"id": "F2", "title": "Hardcoded secret", "severity": "critical", "category": "secrets"},
            ],
        }
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings=verified, execution_results={}, app_map={})

        assert result["summary"]["finding_nodes"] == 2

    def test_creates_api_nodes(self, artifact_store):
        app_map = {
            "api_endpoints": [
                {"method": "GET", "path": "/users", "auth_required": False},
                {"method": "POST", "path": "/login", "auth_required": True},
            ],
            "screens": [],
        }
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings={}, execution_results={}, app_map=app_map)

        assert result["summary"]["api_nodes"] == 2

    def test_creates_page_nodes(self, artifact_store):
        app_map = {
            "api_endpoints": [],
            "screens": [
                {"name": "Home", "path": "/"},
                {"name": "Login", "path": "/login"},
            ],
        }
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings={}, execution_results={}, app_map=app_map)

        assert result["summary"]["page_nodes"] == 2

    def test_creates_test_execution_nodes(self, artifact_store):
        execution = {
            "suites": [
                {
                    "tests": [
                        {"test_id": "T1", "test_title": "Test 1", "outcome": "passed"},
                        {"test_id": "T2", "test_title": "Test 2", "outcome": "failed"},
                    ],
                },
            ],
        }
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings={}, execution_results=execution, app_map={})

        assert result["summary"]["test_nodes"] == 2

    def test_creates_workflow_nodes(self, artifact_store):
        app_map = {
            "api_endpoints": [],
            "screens": [],
            "critical_flows": [
                {"name": "auth_flow", "priority": "critical", "steps": ["login"]},
            ],
        }
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings={}, execution_results={}, app_map=app_map)

        assert result["summary"]["workflow_nodes"] == 1

    def test_links_finding_to_api(self, artifact_store):
        verified = {
            "verified_findings": [
                {"id": "F1", "title": "Missing auth", "severity": "high", "target": "GET /users"},
            ],
        }
        app_map = {
            "api_endpoints": [{"method": "GET", "path": "/users", "auth_required": False}],
            "screens": [],
        }
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings=verified, execution_results={}, app_map=app_map)

        edges = result["graph"]["edges"]
        api_links = [e for e in edges if e["type"] == "targets_api"]
        assert len(api_links) >= 1

    def test_handles_empty_inputs(self, artifact_store):
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings={}, execution_results={}, app_map={})

        assert result["metadata"]["total_nodes"] == 0
        assert result["metadata"]["total_edges"] == 0

    def test_artifacts_written(self, artifact_store):
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        correlator.run(verified_findings={}, execution_results={}, app_map={})

        assert artifact_store.artifact_exists("evidence_graph")

    def test_graph_has_nodes_and_edges(self, artifact_store):
        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(verified_findings={}, execution_results={}, app_map={})

        assert "nodes" in result["graph"]
        assert "edges" in result["graph"]

    def test_evidence_node_to_dict(self, artifact_store):
        node = EvidenceNode("n1", "finding", {"title": "Test"})
        d = node.to_dict()
        assert d["node_id"] == "n1"
        assert d["node_type"] == "finding"
        assert d["data"]["title"] == "Test"

    def test_loads_from_store(self, artifact_store):
        correlated = {"findings": [{"id": "F1", "title": "T", "category": "auth", "severity": "high"}]}
        artifact_store.save_artifact("correlated_findings", correlated)

        correlator = RuntimeEvidenceCorrelator(artifact_store)
        result = correlator.run(execution_results={}, app_map={})

        assert result["summary"]["finding_nodes"] == 1
