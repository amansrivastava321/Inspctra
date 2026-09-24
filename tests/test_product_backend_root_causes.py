from __future__ import annotations

import importlib
import sqlite3
import uuid
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.models import EvidenceFile, LiveRunRecord, Provenance
from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.storage import ProductStorage


@pytest.fixture
def api_env(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "product.db"
    artifacts = tmp_path / "artifacts"
    app = create_product_app(artifacts_dir=str(artifacts), db_path=str(db_path))
    storage = ProductStorage(str(db_path))
    module = importlib.import_module("qa_ai.ai.root_cause_suggester")
    monkeypatch.setattr(module.AIRootCauseSuggester, "_try_model", lambda self, context: None)
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "RCA Project", "description": ""}).json()
        target = client.post(
            "/api/apps",
            json={
                "project_id": project["id"],
                "name": "RCA App",
                "app_type": "web",
                "base_url": "https://example.com",
            },
        ).json()
        pack = client.post(
            "/api/validation-packs",
            json={
                "project_id": project["id"],
                "name": "RCA Pack",
                "description": "",
                "steps": [{
                    "description": "Title shows welcome text",
                    "action_type": "assert_text",
                    "target": "#title",
                    "expected": "Welcome",
                }],
            },
        ).json()
        yield client, storage, project, target, pack, artifacts, db_path
    storage.close()


def _create_run(client: TestClient, storage: ProductStorage, pack: dict, target: dict, *, status: str = "failed") -> str:
    run = LiveRunRecord(
        id=f"rca-{uuid.uuid4()}",
        pack_id=pack["id"],
        app_target_id=target["id"],
        status=status,
        error="AssertionError" if status == "failed" else None,
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_run(run.model_dump(mode="json"))
    if status == "failed":
        storage.append_run_step_result(
            run.id,
            1,
            {
                "step_id": "step-1",
                "action_type": "assert_text",
                "status": "failed",
                "failure_reason": "Expected Welcome but was Login",
                "expected": "Welcome",
                "actual": "Login",
                "provenance": Provenance.REAL_EXECUTION.value,
            },
        )
    elif status == "completed":
        storage.append_run_step_result(
            run.id, 1, {"step_id": "step-1", "status": "passed", "provenance": "REAL_EXECUTION"}
        )
    return run.id


def test_post_persists_draft_and_get_returns_latest_batch(api_env):
    client, storage, _project, target, pack, _artifacts, _db = api_env
    run_id = _create_run(client, storage, pack, target)

    response = client.post(f"/api/runs/{run_id}/root-cause-ai", json={})

    assert response.status_code == 201
    created = response.json()
    assert created["run_id"] == run_id
    assert created["authoritative"] is False
    assert created["suggestions"]
    fetched = client.get(f"/api/runs/{run_id}/root-cause-ai")
    assert fetched.status_code == 200
    assert fetched.json()["analysis_id"] == created["analysis_id"]


def test_get_before_generation_returns_empty_inconclusive(api_env):
    client, storage, _project, target, pack, _artifacts, _db = api_env
    run_id = _create_run(client, storage, pack, target)

    response = client.get(f"/api/runs/{run_id}/root-cause-ai")

    assert response.status_code == 200
    assert response.json()["status"] == "inconclusive"
    assert response.json()["suggestions"] == []
    assert response.json()["authoritative"] is False


@pytest.mark.parametrize("active_status", ["pending", "queued", "running", "starting"])
def test_post_rejects_active_run(api_env, active_status):
    client, storage, _project, target, pack, _artifacts, _db = api_env
    run_id = _create_run(client, storage, pack, target, status="pending")
    storage.update_run_status(run_id, active_status)

    response = client.post(f"/api/runs/{run_id}/root-cause-ai", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == "Root cause suggestions not available — run is still in progress."


def test_post_rejects_passing_terminal_run(api_env):
    client, storage, _project, target, pack, _artifacts, _db = api_env
    run_id = _create_run(client, storage, pack, target, status="completed")

    response = client.post(f"/api/runs/{run_id}/root-cause-ai", json={})

    assert response.status_code == 409
    assert "no failure signal" in response.json()["detail"].lower()


def test_missing_run_and_step_return_404(api_env):
    client, storage, _project, target, pack, _artifacts, _db = api_env
    assert client.post("/api/runs/missing/root-cause-ai", json={}).status_code == 404
    run_id = _create_run(client, storage, pack, target)
    response = client.post(f"/api/runs/{run_id}/root-cause-ai", json={"step_id": "missing-step"})
    assert response.status_code == 404


def test_internal_error_is_sanitized(api_env, monkeypatch):
    client, storage, _project, target, pack, _artifacts, _db = api_env
    run_id = _create_run(client, storage, pack, target)
    module = importlib.import_module("qa_ai.ai.root_cause_suggester")
    monkeypatch.setattr(
        module.AIRootCauseSuggester,
        "suggest",
        lambda self, run_id, step_id=None: (_ for _ in ()).throw(RuntimeError("Bearer secret-value")),
    )

    response = client.post(f"/api/runs/{run_id}/root-cause-ai", json={})

    assert response.status_code == 500
    assert response.json()["detail"] == "Root cause suggestion generation failed."
    assert "secret-value" not in response.text


def test_post_does_not_mutate_product_records(api_env):
    client, storage, _project, target, pack, _artifacts, _db = api_env
    run_id = _create_run(client, storage, pack, target)
    evidence = EvidenceFile(
        id="ev-1",
        run_id=run_id,
        step_id="step-1",
        evidence_type="console",
        name="console",
        relative_path="runs/missing.log",
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_evidence(evidence.model_dump())
    before_run = deepcopy(storage.get_run(run_id))
    before_evidence = deepcopy(storage.list_evidence(run_id))
    before_pack = deepcopy(storage.get_validation_pack(pack["id"]))
    before_cases = deepcopy(storage.list_test_cases(pack["id"]))

    response = client.post(f"/api/runs/{run_id}/root-cause-ai", json={})

    assert response.status_code == 201
    assert storage.get_run(run_id) == before_run
    assert storage.list_evidence(run_id) == before_evidence
    assert storage.get_validation_pack(pack["id"]) == before_pack
    assert storage.list_test_cases(pack["id"]) == before_cases


def test_persistence_survives_storage_restart(api_env):
    client, storage, _project, target, pack, _artifacts, db_path = api_env
    run_id = _create_run(client, storage, pack, target)
    created = client.post(f"/api/runs/{run_id}/root-cause-ai", json={}).json()

    reopened = ProductStorage(str(db_path))
    try:
        latest = reopened.get_latest_ai_root_cause_batch(run_id)
        assert latest is not None
        assert latest["analysis_id"] == created["analysis_id"]
    finally:
        reopened.close()


def test_legacy_database_migrates_without_losing_data(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
    connection.execute("INSERT INTO settings VALUES ('legacy-key', 'legacy-value', '2026-01-01T00:00:00Z')")
    connection.commit()
    connection.close()

    storage = ProductStorage(str(db_path))
    try:
        tables = {row["name"] for row in storage._execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        indexes = {row["name"] for row in storage._execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        assert "ai_root_cause_analyses" in tables
        assert "ai_root_cause_suggestions" in tables
        assert "idx_ai_rca_run_created" in indexes
        assert storage.get_setting("legacy-key") == "legacy-value"
    finally:
        storage.close()
