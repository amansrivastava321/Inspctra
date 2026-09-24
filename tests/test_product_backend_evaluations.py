"""
test_product_backend_evaluations.py - API integration tests for AI Evidence Evaluation.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.models import LiveRunRecord


@pytest.fixture
def test_env(tmp_path: Path):
    db_path = str(tmp_path / "test_evals.db")
    artifacts_dir = str(tmp_path / "artifacts")
    app = create_product_app(artifacts_dir=artifacts_dir, db_path=db_path)
    storage = ProductStorage(db_path)
    
    with TestClient(app) as client:
        # Create project and pack via REST API to populate IDs and datetimes correctly
        proj = client.post("/api/projects", json={"name": "Test Project", "description": ""}).json()
        pack = client.post("/api/validation-packs", json={
            "project_id": proj["id"],
            "name": "Smoke Pack",
            "description": "Test pack",
        }).json()
        yield client, storage, pack, proj


def test_evaluate_run_persists_note_and_does_not_mutate_run_status(test_env):
    client, storage, pack, proj = test_env

    # 1. Create a run target and a run
    target = client.post("/api/apps", json={
        "project_id": proj["id"],
        "name": "Test Target",
        "app_type": "web",
        "base_url": "http://localhost:3000"
    }).json()

    run = client.post(f"/api/validation-packs/{pack['id']}/runs", json={
        "app_target_id": target["id"]
    }).json()
    run_id = run["id"]

    # Verify initial run status is pending
    assert run["status"] == "pending"

    # Append a test step result to verify the run has content
    storage.append_run_step_result(run_id, 1, {
        "description": "Verify homepage title",
        "status": "passed",
        "notes": "Title matches expected"
    })

    # Mock the LLM Router response
    with patch("qa_ai.ai.model_router.ModelRouter.route") as mock_route:
        mock_route_result = MagicMock()
        mock_route_result.success = True
        mock_route_result.content = json.dumps({
            "verdict_assessment": "supports_verdict",
            "suggested_verdict": "pass",
            "confidence": 0.90,
            "summary": "Everything checks out",
            "evidence_used": [],
            "missing_evidence": [],
            "risk_flags": [],
            "rationale": "All step results passed"
        })
        mock_route.return_value = mock_route_result

        # Capture run status before evaluation
        status_before = storage.get_run(run_id)["status"]

        # POST to evaluate endpoint
        resp = client.post(f"/api/runs/{run_id}/evaluate-ai", json={})
        assert resp.status_code == 201
        note = resp.json()

        assert note["run_id"] == run_id
        assert note["verdict_assessment"] == "supports_verdict"
        assert note["suggested_verdict"] == "pass"
        assert note["confidence"] == 0.90
        assert note["generation_source"] == "ollama"

        # Verify it was persisted in the storage
        persisted_notes = storage.list_ai_evaluation_notes(run_id)
        assert len(persisted_notes) == 1
        assert persisted_notes[0]["evaluation_id"] == note["evaluation_id"]

        # CRITICAL CONSTRAINT: Run status remains untouched by evaluation
        assert storage.get_run(run_id)["status"] == status_before


def test_evaluate_nonexistent_run_returns_404(test_env):
    client, storage, pack, proj = test_env
    resp = client.post("/api/runs/nonexistent-run-id/evaluate-ai", json={})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_evaluate_run_with_routing_failure_uses_fallback(test_env):
    client, storage, pack, proj = test_env

    target = client.post("/api/apps", json={
        "project_id": proj["id"],
        "name": "Test Target",
        "app_type": "web",
        "base_url": "http://localhost:3000"
    }).json()

    run = client.post(f"/api/validation-packs/{pack['id']}/runs", json={
        "app_target_id": target["id"]
    }).json()
    run_id = run["id"]

    # Trigger completed status and append step result to force completed-pass fallback path
    storage.update_run_status(run_id, "completed")
    storage.append_run_step_result(run_id, 1, {"status": "passed", "notes": "ok"})

    # Force route failure
    with patch("qa_ai.ai.model_router.ModelRouter.route", side_effect=RuntimeError("Connection timeout")):
        resp = client.post(f"/api/runs/{run_id}/evaluate-ai", json={})
        assert resp.status_code == 201
        note = resp.json()
        assert note["generation_source"] == "local_fallback"
        assert note["verdict_assessment"] == "supports_verdict"
        assert note["suggested_verdict"] == "pass"
        assert note["confidence"] == 0.55
        assert "local_fallback_active" in note["risk_flags"]


def test_get_run_evaluations(test_env):
    client, storage, pack, proj = test_env

    target = client.post("/api/apps", json={
        "project_id": proj["id"],
        "name": "Test Target",
        "app_type": "web",
        "base_url": "http://localhost:3000"
    }).json()

    run = client.post(f"/api/validation-packs/{pack['id']}/runs", json={
        "app_target_id": target["id"]
    }).json()
    run_id = run["id"]

    # Directly create notes in DB
    note1 = {
        "evaluation_id": "e1",
        "run_id": run_id,
        "step_id": None,
        "verdict_assessment": "supports_verdict",
        "suggested_verdict": "pass",
        "confidence": 0.85,
        "summary": "Pass",
        "evidence_used": ["screenshot.png"],
        "missing_evidence": [],
        "risk_flags": [],
        "rationale": "ok",
        "generation_source": "ollama",
        "generation_metadata_json": {},
        "created_at": "2026-06-18T10:00:00Z"
    }
    note2 = {
        "evaluation_id": "e2",
        "run_id": run_id,
        "step_id": None,
        "verdict_assessment": "inconclusive",
        "suggested_verdict": None,
        "confidence": 0.50,
        "summary": "Inconclusive",
        "evidence_used": [],
        "missing_evidence": [],
        "risk_flags": [],
        "rationale": "no steps",
        "generation_source": "local_fallback",
        "generation_metadata_json": {},
        "created_at": "2026-06-18T09:00:00Z"
    }
    storage.create_ai_evaluation_note(note1)
    storage.create_ai_evaluation_note(note2)

    # GET request
    resp = client.get(f"/api/runs/{run_id}/evaluation-ai")
    assert resp.status_code == 200
    notes = resp.json()
    assert len(notes) == 2
    assert notes[0]["evaluation_id"] == "e1"
    assert notes[1]["evaluation_id"] == "e2"


def test_get_nonexistent_run_evaluations_returns_404(test_env):
    client, storage, pack, proj = test_env
    resp = client.get("/api/runs/nonexistent-run-id/evaluation-ai")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
