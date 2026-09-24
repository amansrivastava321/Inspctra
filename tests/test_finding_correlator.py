"""
test_finding_correlator.py - Tests for the FindingCorrelator.
Validates finding ingestion, correlation by endpoint/file/category/workflow,
and cross-cutting concern identification.
"""

import pytest

from qa_ai.intelligence.finding_correlator import FindingCorrelator


class TestFindingCorrelator:
    def test_ingests_api_audit_findings(self, artifact_store):
        api_audit = {
            "checks": [
                {
                    "check_id": "API-AUTH-001",
                    "title": "Missing auth on DELETE /users",
                    "description": "No auth required.",
                    "status": "failed",
                    "severity": "critical",
                    "category": "authentication",
                    "target": "DELETE /users",
                    "recommendation": "Add auth.",
                },
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(api_audit=api_audit)

        assert result["metadata"]["total_findings"] == 1
        assert result["findings"][0]["id"] == "API-AUTH-001"

    def test_ingests_multiple_sources(self, artifact_store):
        api_audit = {"checks": [{"check_id": "C1", "title": "T1", "status": "failed", "severity": "high", "category": "auth", "target": "GET /x"}]}
        security_audit = {"checks": [{"check_id": "C2", "title": "T2", "status": "warning", "severity": "medium", "category": "secrets", "target": "config.py"}]}
        code_quality = {"checks": [{"check_id": "C3", "title": "T3", "status": "warning", "severity": "low", "category": "file_size", "target": "big.py"}]}

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(api_audit=api_audit, security_audit=security_audit, code_quality_audit=code_quality)

        assert result["metadata"]["total_findings"] == 3

    def test_skips_passed_checks(self, artifact_store):
        api_audit = {
            "checks": [
                {"check_id": "C1", "title": "OK", "status": "passed", "severity": "low", "category": "auth"},
                {"check_id": "C2", "title": "Bad", "status": "failed", "severity": "high", "category": "auth"},
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(api_audit=api_audit)

        assert result["metadata"]["total_findings"] == 1

    def test_correlates_by_endpoint(self, artifact_store):
        api_audit = {
            "checks": [
                {"check_id": "C1", "title": "Auth missing", "status": "failed", "severity": "critical", "category": "authentication", "target": "DELETE /users"},
                {"check_id": "C2", "title": "No idempotency", "status": "warning", "severity": "medium", "category": "idempotency", "target": "DELETE /users"},
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(api_audit=api_audit)

        by_endpoint = result["correlations"]["by_endpoint"]
        assert len(by_endpoint) == 1
        assert by_endpoint[0]["count"] == 2

    def test_correlates_by_file(self, artifact_store):
        security_audit = {
            "checks": [
                {"check_id": "C1", "title": "Secret", "status": "failed", "severity": "critical", "category": "secrets", "target": "config.py"},
                {"check_id": "C2", "title": "Debug", "status": "warning", "severity": "medium", "category": "debug_flags", "target": "config.py"},
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(security_audit=security_audit)

        by_file = result["correlations"]["by_file"]
        assert len(by_file) == 1
        assert by_file[0]["count"] == 2

    def test_correlates_by_category(self, artifact_store):
        api_audit = {
            "checks": [
                {"check_id": "C1", "title": "T1", "status": "failed", "severity": "high", "category": "authentication"},
                {"check_id": "C2", "title": "T2", "status": "failed", "severity": "high", "category": "authentication"},
                {"check_id": "C3", "title": "T3", "status": "warning", "severity": "low", "category": "validation"},
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(api_audit=api_audit)

        by_category = result["correlations"]["by_category"]
        auth_group = next(g for g in by_category if g["key"] == "authentication")
        assert auth_group["count"] == 2

    def test_correlates_by_severity(self, artifact_store):
        api_audit = {
            "checks": [
                {"check_id": "C1", "title": "T1", "status": "failed", "severity": "critical", "category": "auth"},
                {"check_id": "C2", "title": "T2", "status": "failed", "severity": "critical", "category": "auth"},
                {"check_id": "C3", "title": "T3", "status": "warning", "severity": "medium", "category": "val"},
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(api_audit=api_audit)

        by_severity = result["correlations"]["by_severity"]
        assert by_severity.get("critical", 0) == 2
        assert by_severity.get("medium", 0) == 1

    def test_identifies_cross_cutting_hotspots(self, artifact_store):
        security_audit = {
            "checks": [
                {"check_id": f"C{i}", "title": f"T{i}", "status": "failed", "severity": "critical", "category": "secrets", "target": "config.py"}
                for i in range(4)
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(security_audit=security_audit)

        assert "config.py" in result["cross_cutting"]["hotspot_files"]

    def test_ingests_execution_failures(self, artifact_store):
        execution_results = {
            "suites": [
                {
                    "tests": [
                        {"test_id": "T1", "test_title": "Test 1", "outcome": "failed", "error_message": "assertion failed"},
                        {"test_id": "T2", "test_title": "Test 2", "outcome": "passed"},
                    ],
                },
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(execution_results=execution_results)

        assert result["metadata"]["total_findings"] == 1
        assert result["findings"][0]["title"] == "Test 1"

    def test_correlates_by_workflow(self, artifact_store, sample_app_map):
        api_audit = {
            "checks": [
                {"check_id": "C1", "title": "Auth issue with login", "status": "failed", "severity": "high", "category": "auth", "target": "POST /login"},
            ],
        }

        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(api_audit=api_audit, app_map=sample_app_map)

        by_workflow = result["correlations"]["by_workflow"]
        # auth_flow should match because "login" is in the title
        assert len(by_workflow) > 0

    def test_artifacts_written(self, artifact_store, sample_app_map):
        correlator = FindingCorrelator(artifact_store)
        correlator.run(app_map=sample_app_map)

        assert artifact_store.artifact_exists("correlated_findings")

    def test_empty_input(self, artifact_store):
        correlator = FindingCorrelator(artifact_store)
        result = correlator.run()

        assert result["metadata"]["total_findings"] == 0
        assert result["findings"] == []

    def test_result_has_metadata(self, artifact_store, sample_app_map):
        correlator = FindingCorrelator(artifact_store)
        result = correlator.run(app_map=sample_app_map)

        assert result["metadata"]["correlation_type"] == "finding_correlation"
        assert result["metadata"]["generated_by"] == "FindingCorrelator"
        assert result["metadata"]["duration_seconds"] >= 0
