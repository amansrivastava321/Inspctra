"""
test_artifact_store.py - Tests for the ArtifactStore.
Validates save, load, versioning, evidence, and report management.
"""

import pytest
from pathlib import Path

from qa_ai.runtime.artifact_store import ArtifactStore, reset_artifact_store


class TestArtifactStore:
    def test_save_and_load(self, artifact_store):
        data = {"key": "value", "nested": {"a": 1}}
        artifact_store.save_artifact("test_data", data)
        loaded = artifact_store.load_artifact("test_data")
        assert loaded["key"] == "value"
        assert loaded["nested"]["a"] == 1

    def test_save_with_version(self, artifact_store):
        data = {"version": 1}
        artifact_store.save_artifact("versioned", data, version="1.0.0")
        artifact_store.save_artifact("versioned", {"version": 2}, version="2.0.0")

        v1 = artifact_store.load_artifact("versioned", version="1.0.0")
        v2 = artifact_store.load_artifact("versioned", version="2.0.0")
        latest = artifact_store.load_artifact("versioned")

        assert v1["version"] == 1
        assert v2["version"] == 2
        assert latest["version"] == 2

    def test_list_artifacts(self, artifact_store):
        artifact_store.save_artifact("alpha", {"a": 1})
        artifact_store.save_artifact("beta", {"b": 2})
        artifacts = artifact_store.list_artifacts()
        assert "alpha.json" in artifacts
        assert "beta.json" in artifacts

    def test_list_versions(self, artifact_store):
        artifact_store.save_artifact("app_map", {"v": 1}, version="1.0.0")
        artifact_store.save_artifact("app_map", {"v": 2}, version="1.1.0")
        versions = artifact_store.list_versions("app_map")
        assert "1.0.0" in versions
        assert "1.1.0" in versions

    def test_artifact_exists(self, artifact_store):
        assert not artifact_store.artifact_exists("missing")
        artifact_store.save_artifact("present", {"x": 1})
        assert artifact_store.artifact_exists("present")

    def test_get_artifact_metadata(self, artifact_store):
        artifact_store.save_artifact(
            "meta_test",
            {"data": True},
            version="1.0.0",
            metadata={"source": "test"},
        )
        meta = artifact_store.get_artifact_metadata("meta_test", version="1.0.0")
        assert meta is not None
        assert meta["source"] == "test"

    def test_convenience_methods(self, artifact_store):
        artifact_store.save_artifact("app_map", {"stack": {}})
        app_map = artifact_store.get_latest_app_map()
        assert app_map["stack"] == {}

        artifact_store.save_artifact("test_plan", {"summary": {}})
        test_plan = artifact_store.get_latest_test_plan()
        assert test_plan["summary"] == {}

        artifact_store.save_artifact("findings", {"findings": []})
        findings = artifact_store.get_latest_findings()
        assert findings["findings"] == []

    def test_save_findings(self, artifact_store):
        artifact_store.save_findings({"bugs": 3}, agent="SecurityAgent")
        loaded = artifact_store.get_latest_findings()
        assert loaded["bugs"] == 3

    def test_append_findings(self, artifact_store):
        artifact_store.save_findings({"findings": [{"id": 1}]})
        artifact_store.append_findings([{"id": 2}, {"id": 3}], agent="TestAgent")
        loaded = artifact_store.get_latest_findings()
        assert len(loaded["findings"]) == 3

    def test_evidence_binary(self, artifact_store):
        data = b"PNG screenshot data"
        path = artifact_store.save_evidence("screenshots", "test.png", data)
        assert path.exists()

        loaded = artifact_store.load_evidence("screenshots", "test.png")
        assert loaded == data

    def test_evidence_json(self, artifact_store):
        data = {"status": 200, "body": "OK"}
        artifact_store.save_evidence_json("api_responses", "get_users.json", data)
        assert artifact_store.load_evidence("api_responses", "get_users.json") is not None

    def test_list_evidence(self, artifact_store):
        artifact_store.save_evidence("logs", "run1.log", b"log data")
        evidence = artifact_store.list_evidence("logs")
        assert len(evidence) >= 1

    def test_reports(self, artifact_store):
        artifact_store.save_report("audit.md", "# Audit Report")
        assert artifact_store.load_report("audit.md") == "# Audit Report"
        assert "audit.md" in artifact_store.list_reports()

    def test_clear(self, artifact_store):
        artifact_store.save_artifact("temp", {"x": 1})
        artifact_store.save_report("keep.md", "keep")
        artifact_store.clear(keep_reports=True)
        assert not artifact_store.artifact_exists("temp")
        assert artifact_store.load_report("keep.md") == "keep"

    def test_get_store_size(self, artifact_store):
        artifact_store.save_artifact("size_test", {"data": "x" * 1000})
        size = artifact_store.get_store_size()
        assert size["total_bytes"] > 0
        assert size["file_count"] >= 1

    def test_nonexistent_load(self, artifact_store):
        assert artifact_store.load_artifact("does_not_exist") is None
        assert artifact_store.load_artifact("does_not_exist", version="1.0.0") is None

    def test_metadata_injection(self, artifact_store):
        data = {"original": True}
        artifact_store.save_artifact("injected", data, agent="TestAgent")
        loaded = artifact_store.load_artifact("injected")
        assert "_metadata" in loaded
        assert loaded["_metadata"]["produced_by"] == "TestAgent"
        assert loaded["original"] is True

    def test_json_extension_handling(self, artifact_store):
        artifact_store.save_artifact("test.json", {"x": 1})
        loaded = artifact_store.load_artifact("test")
        assert loaded is not None
        assert loaded["x"] == 1
