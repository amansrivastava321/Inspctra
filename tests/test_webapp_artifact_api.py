"""
test_webapp_artifact_api.py - Tests for the ArtifactAPI read-only adapter.
"""
import json
import pytest
from pathlib import Path

from qa_ai.webapp.artifact_api import ArtifactAPI


@pytest.fixture
def api(tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    return ArtifactAPI(str(artifacts_dir))


@pytest.fixture
def api_with_data(tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    (artifacts_dir / "audit_summary.json").write_text(
        json.dumps({
            "status": "completed",
            "target_path": "/app",
            "profile": "api",
            "phases_executed": ["discovery", "analysis"],
        })
    )
    (artifacts_dir / "findings.json").write_text(
        json.dumps({
            "findings": [
                {"id": "F001", "title": "SQL Injection", "severity": "critical", "category": "security"},
                {"id": "F002", "title": "Missing Auth", "severity": "high", "category": "auth"},
            ]
        })
    )
    (artifacts_dir / "risk_report.json").write_text(
        json.dumps({"overall_score": 7.5, "risk_level": "high"})
    )
    return ArtifactAPI(str(artifacts_dir))


class TestListArtifacts:
    def test_empty_dir_returns_empty_list(self, api):
        assert api.list_artifacts() == []

    def test_lists_json_files(self, api_with_data):
        names = [a["name"] for a in api_with_data.list_artifacts()]
        assert any("audit_summary" in n for n in names)

    def test_each_entry_has_required_keys(self, api_with_data):
        for entry in api_with_data.list_artifacts():
            assert "name" in entry
            assert "size_bytes" in entry


class TestGetSummary:
    def test_returns_empty_dict_when_missing(self, api):
        result = api.get_summary()
        assert result == {}

    def test_returns_summary_data(self, api_with_data):
        summary = api_with_data.get_summary()
        assert summary["status"] == "completed"
        assert summary["profile"] == "api"


class TestGetFindings:
    def test_returns_empty_list_when_no_data(self, api):
        assert api.get_findings() == []

    def test_returns_findings_list(self, api_with_data):
        findings = api_with_data.get_findings()
        assert len(findings) == 2
        assert findings[0]["id"] == "F001"

    def test_always_returns_list_type(self, api_with_data):
        assert isinstance(api_with_data.get_findings(), list)


class TestGetRisk:
    def test_returns_empty_dict_when_missing(self, api):
        assert api.get_risk() == {}

    def test_returns_risk_data(self, api_with_data):
        risk = api_with_data.get_risk()
        assert risk["overall_score"] == 7.5
        assert risk["risk_level"] == "high"


class TestGetArtifact:
    def test_returns_none_for_missing(self, api):
        assert api.get_artifact("nonexistent") is None

    def test_returns_artifact_data(self, api_with_data):
        data = api_with_data.get_artifact("risk_report")
        assert data is not None
        assert data["risk_level"] == "high"

    def test_accepts_name_with_json_extension(self, api_with_data):
        data = api_with_data.get_artifact("risk_report.json")
        assert data is not None


class TestGetStoreStats:
    def test_returns_stat_keys(self, api_with_data):
        stats = api_with_data.get_store_stats()
        assert "artifact_count" in stats
        assert "evidence_count" in stats
        assert "artifacts_dir" in stats

    def test_artifact_count_matches_files(self, api_with_data):
        stats = api_with_data.get_store_stats()
        assert stats["artifact_count"] >= 3


class TestNoWriteMethods:
    def test_api_has_no_save_method(self, api):
        assert not hasattr(api, "save_artifact")

    def test_api_has_no_delete_method(self, api):
        assert not hasattr(api, "delete_artifact")

    def test_api_has_no_write_method(self, api):
        assert not hasattr(api, "write_artifact")
