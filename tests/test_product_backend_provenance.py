"""Contract tests for persisted source-of-truth provenance."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend import models
from qa_ai.product_backend import run_manager as run_manager_module
from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.storage import ProductStorage


def test_provenance_enum_has_stable_upper_snake_case_values() -> None:
    assert hasattr(models, "Provenance")
    assert [member.value for member in models.Provenance] == [
        "REAL_EXECUTION",
        "DRY_RUN",
        "MIXED",
        "SIMULATED",
        "DEMO_EXAMPLE",
        "UNAVAILABLE",
    ]


def test_required_response_models_default_to_unavailable() -> None:
    provenance = models.Provenance.UNAVAILABLE
    assert models.Project(name="P").provenance == provenance
    assert models.AppTarget(project_id="p", name="A", app_type="web").provenance == provenance
    assert models.ValidationPack(project_id="p", name="Pack").provenance == provenance
    assert models.LiveRunRecord(pack_id="pack", app_target_id="app").provenance == provenance
    assert models.EvidenceFile(run_id="run", name="E", relative_path="e.json").provenance == provenance
    assert models.ReportRecord(run_id="run", name="R").provenance == provenance
    assert models.DashboardSummary().provenance == provenance
    assert models.HealthResponse(status="ok").provenance == provenance


def test_run_provenance_aggregation_contract() -> None:
    assert hasattr(run_manager_module, "compute_run_provenance")
    aggregate = run_manager_module.compute_run_provenance
    p = models.Provenance

    assert aggregate([p.REAL_EXECUTION, p.REAL_EXECUTION]) == p.REAL_EXECUTION
    assert aggregate([p.DRY_RUN, p.DRY_RUN]) == p.DRY_RUN
    assert aggregate([p.DEMO_EXAMPLE, p.DEMO_EXAMPLE]) == p.DEMO_EXAMPLE
    assert aggregate([p.UNAVAILABLE, p.UNAVAILABLE]) == p.UNAVAILABLE
    assert aggregate([p.REAL_EXECUTION, p.DRY_RUN]) == p.MIXED
    assert aggregate([p.REAL_EXECUTION, p.UNAVAILABLE]) == p.MIXED
    assert aggregate([p.DRY_RUN, p.UNAVAILABLE]) == p.MIXED
    assert aggregate([]) == p.UNAVAILABLE


def test_storage_migrates_and_persists_provenance(tmp_path: Path) -> None:
    storage = ProductStorage(str(tmp_path / "provenance.db"))
    try:
        for table in (
            "projects",
            "app_targets",
            "validation_packs",
            "live_runs",
            "evidence_files",
            "reports",
        ):
            columns = {
                row["name"] for row in storage._execute(f"PRAGMA table_info({table})").fetchall()
            }
            assert "provenance" in columns

        project = models.Project(name="Persisted", provenance=models.Provenance.REAL_EXECUTION)
        storage.create_project(project.model_dump())
        assert storage.get_project(project.id)["provenance"] == "REAL_EXECUTION"
    finally:
        storage.close()


def test_legacy_run_provenance_uses_evidence_fallback(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE live_runs (
            id TEXT PRIMARY KEY, pack_id TEXT NOT NULL, app_target_id TEXT NOT NULL,
            status TEXT NOT NULL, started_at TEXT, completed_at TEXT,
            step_results TEXT NOT NULL DEFAULT '[]', error TEXT, created_at TEXT NOT NULL,
            retest_of TEXT, execution_mode TEXT NOT NULL DEFAULT 'automated'
        );
        CREATE TABLE evidence_files (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT, type TEXT,
            name TEXT NOT NULL, relative_path TEXT NOT NULL, mime_type TEXT,
            size_bytes INTEGER, sha256 TEXT, metadata_json TEXT, created_at TEXT NOT NULL
        );
        INSERT INTO live_runs
            (id, pack_id, app_target_id, status, step_results, created_at)
        VALUES ('with-evidence', 'pack', 'app', 'completed',
                '[{"step": 1, "step_id": "evidence-step", "status": "passed"}, {"step": 2, "step_id": "no-evidence-step", "status": "passed"}]',
                '2026-01-01'),
               ('without-evidence', 'pack', 'app', 'completed',
                '[{"step": 1, "step_id": "unknown-step", "status": "passed"}]',
                '2026-01-01');
        INSERT INTO evidence_files
            (id, run_id, step_id, type, name, relative_path, mime_type, size_bytes, created_at)
        VALUES ('evidence', 'with-evidence', 'evidence-step', 'api_response',
                'Legacy evidence', 'legacy.json',
                'application/json', 1, '2026-01-01');
        """
    )
    connection.commit()
    connection.close()

    storage = ProductStorage(str(db_path))
    try:
        with_evidence = storage.get_run("with-evidence")
        without_evidence = storage.get_run("without-evidence")
        assert with_evidence["provenance"] == "REAL_EXECUTION"
        assert without_evidence["provenance"] == "UNAVAILABLE"
        assert [step["provenance"] for step in with_evidence["step_results"]] == [
            "REAL_EXECUTION",
            "UNAVAILABLE",
        ]
        assert without_evidence["step_results"][0]["provenance"] == "UNAVAILABLE"
    finally:
        storage.close()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_product_app(
        artifacts_dir=str(tmp_path / "artifacts"),
        db_path=str(tmp_path / "api.db"),
    )
    with TestClient(app) as test_client:
        yield test_client


def test_entity_and_health_responses_include_provenance(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["provenance"] == "REAL_EXECUTION"

    project = client.post("/api/projects", json={"name": "Provenance Project"}).json()
    assert project["provenance"] == "REAL_EXECUTION"
    assert client.get(f"/api/projects/{project['id']}").json()["provenance"] == "REAL_EXECUTION"
    assert client.get("/api/projects").json()[0]["provenance"] == "REAL_EXECUTION"

    app = client.post(
        "/api/apps",
        json={"project_id": project["id"], "name": "App", "app_type": "web"},
    ).json()
    assert app["provenance"] == "REAL_EXECUTION"
    assert client.get(f"/api/apps/{app['id']}").json()["provenance"] == "REAL_EXECUTION"
    assert client.get("/api/apps").json()[0]["provenance"] == "REAL_EXECUTION"

    pack = client.post(
        "/api/validation-packs",
        json={"project_id": project["id"], "app_id": app["id"], "name": "Pack"},
    ).json()
    assert pack["provenance"] == "REAL_EXECUTION"
    assert client.get(f"/api/validation-packs/{pack['id']}").json()["provenance"] == "REAL_EXECUTION"
    assert client.get("/api/validation-packs").json()[0]["provenance"] == "REAL_EXECUTION"

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["provenance"] == "REAL_EXECUTION"

    model_health = client.get("/api/models/health").json()
    assert model_health["provenance"] in {"REAL_EXECUTION", "UNAVAILABLE"}

    connector_health = client.get("/api/connectors").json()
    assert connector_health["provenance"] == "REAL_EXECUTION"
    assert connector_health["connectors"]
    assert {
        connector["provenance"] for connector in connector_health["connectors"]
    } == {"REAL_EXECUTION"}


def test_mixed_run_labels_steps_evidence_and_report(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qa_ai.live_execution.api_engine import ApiEngine

    def execute_api(self, step, app_target, context):
        return {
            "status": "passed",
            "notes": "HTTP request completed",
            "request_summary": {"method": "GET", "url": step["url"]},
            "response_summary": {
                "status_code": 200,
                "response_time_ms": 1,
                "final_url": step["url"],
            },
            "context": context,
        }

    monkeypatch.setattr(ApiEngine, "execute_step", execute_api)

    project = client.post("/api/projects", json={"name": "Mixed Project"}).json()
    app = client.post(
        "/api/apps",
        json={"project_id": project["id"], "name": "API", "app_type": "api"},
    ).json()
    pack = client.post(
        "/api/validation-packs",
        json={
            "project_id": project["id"],
            "app_id": app["id"],
            "name": "Mixed Pack",
            "steps": [
                {
                    "description": "Real API request",
                    "action_type": "api_request",
                    "method": "GET",
                    "url": "https://example.com",
                },
                {
                    "description": "Intentional structural verification",
                    "action_type": "verify",
                },
                {
                    "description": "Unsupported capability",
                    "action_type": "mobile_gesture",
                },
            ],
        },
    ).json()
    started = client.post(
        f"/api/validation-packs/{pack['id']}/run",
        json={"app_target_id": app["id"]},
    ).json()

    deadline = time.monotonic() + 5
    while True:
        run = client.get(f"/api/runs/{started['id']}").json()
        if run["status"] not in {"pending", "running"}:
            break
        assert time.monotonic() < deadline
        time.sleep(0.05)

    assert run["provenance"] == "MIXED"
    assert [step["provenance"] for step in run["step_results"]] == [
        "REAL_EXECUTION",
        "DRY_RUN",
        "UNAVAILABLE",
    ]
    assert client.get("/api/runs").json()[0]["provenance"] == "MIXED"

    evidence = client.get(f"/api/evidence?run_id={run['id']}").json()
    assert evidence
    assert {item["provenance"] for item in evidence} == {"REAL_EXECUTION"}
    assert client.get(f"/api/evidence/{evidence[0]['id']}").json()["provenance"] == "REAL_EXECUTION"

    generated = client.post(f"/api/runs/{run['id']}/report/generate").json()
    assert generated["provenance"] == "MIXED"
    assert client.get(f"/api/reports/{generated['id']}").json()["provenance"] == "MIXED"
    reports = client.get(f"/api/reports?run_id={run['id']}").json()
    assert reports[0]["provenance"] == "MIXED"


def test_api_validation_failure_is_unavailable_not_real(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "Rejected API Project"}).json()
    app = client.post(
        "/api/apps",
        json={"project_id": project["id"], "name": "API", "app_type": "api"},
    ).json()
    pack = client.post(
        "/api/validation-packs",
        json={
            "project_id": project["id"],
            "name": "Rejected API Pack",
            "steps": [
                {
                    "description": "Reject unsupported method before network I/O",
                    "action_type": "api_request",
                    "method": "TRACE",
                    "url": "https://example.com",
                }
            ],
        },
    ).json()
    started = client.post(
        f"/api/validation-packs/{pack['id']}/run",
        json={"app_target_id": app["id"]},
    ).json()

    deadline = time.monotonic() + 5
    while True:
        run = client.get(f"/api/runs/{started['id']}").json()
        if run["status"] not in {"pending", "running"}:
            break
        assert time.monotonic() < deadline
        time.sleep(0.05)

    assert run["provenance"] == "UNAVAILABLE"
    assert run["step_results"][0]["provenance"] == "UNAVAILABLE"


def test_model_health_route_metrics_include_provenance(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from qa_ai.ai import model_health

    report = SimpleNamespace(
        ollama_reachable=True,
        ollama_base_url="http://127.0.0.1:11434",
        installed_models=["model"],
        required_models=["model"],
        missing_models=[],
        present_models=["model"],
        route_coverage=[
            SimpleNamespace(
                task="vision",
                primary_model="model",
                primary_available=True,
                fallback_models=[],
                fallback_available=[],
                status="ready",
            )
        ],
        cloud_providers_disabled=True,
        overall_readiness="ready",
        recommendations=[],
        generated_at="2026-01-01T00:00:00Z",
        error=None,
    )
    monkeypatch.setattr(model_health, "build_health_report", lambda: report)

    response = client.get("/api/models/health")
    assert response.status_code == 200
    data = response.json()
    assert data["provenance"] == "REAL_EXECUTION"
    assert data["route_coverage"][0]["provenance"] == "REAL_EXECUTION"
