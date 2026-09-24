"""End-to-end smoke coverage for Inspectra's core product journey."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.server import create_product_app


@pytest.fixture
def smoke_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Run the top-level ASGI entry point with disposable local storage."""
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "inspectra_smoke.db"
    artifacts_dir = tmp_path / "artifacts"

    # Keep the supported `qa_ai.server:app` entry point while replacing its
    # process-wide instance with one whose database and artifacts are isolated.
    from qa_ai import server as server_module

    monkeypatch.setattr(
        server_module,
        "app",
        create_product_app(
            artifacts_dir=str(artifacts_dir),
            db_path=str(db_path),
        ),
    )

    with TestClient(server_module.app) as client:
        yield client

        # Let the daemon runner finish its final bookkeeping before lifespan
        # shutdown closes SQLite.
        deadline = time.monotonic() + 5
        manager = client.app.state.run_manager
        run_ids = [run["id"] for run in client.get("/api/runs").json()]
        while any(manager.is_running(run_id) for run_id in run_ids):
            if time.monotonic() >= deadline:
                pytest.fail("Smoke run worker did not stop during fixture teardown")
            time.sleep(0.05)

    for candidate in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        candidate.unlink(missing_ok=True)


def _json(response, operation: str) -> dict:
    assert response.is_success, (
        f"{operation} failed with HTTP {response.status_code}: {response.text}"
    )
    return response.json()


def test_full_journey_creates_app_runs_check_and_generates_report(
    smoke_client: TestClient,
) -> None:
    project = _json(
        smoke_client.post("/api/projects", json={"name": "Smoke Project"}),
        "create project",
    )

    app = _json(
        smoke_client.post(
            "/api/apps",
            json={
                "project_id": project["id"],
                "name": "Smoke App",
                "app_type": "web",
                "base_url": "https://example.com",
            },
        ),
        "create app",
    )

    pack = _json(
        smoke_client.post(
            "/api/validation-packs",
            json={
                "project_id": project["id"],
                "app_id": app["id"],
                "name": "Smoke Pack",
                "steps": [
                    {
                        "description": "https://example.com returns status 200",
                        "action_type": "api_request",
                        "method": "GET",
                        "url": "https://example.com",
                        "expected_status": 200,
                        "timeout_seconds": 30,
                    }
                ],
            },
        ),
        "create validation pack",
    )

    run = _json(
        smoke_client.post(
            f"/api/validation-packs/{pack['id']}/run",
            json={"app_target_id": app["id"]},
        ),
        "start validation pack",
    )

    deadline = time.monotonic() + 60
    while True:
        run = _json(smoke_client.get(f"/api/runs/{run['id']}"), "poll run")
        if run["status"].upper() in {"COMPLETED", "PASSED", "FAILED", "CANCELLED"}:
            break
        if time.monotonic() >= deadline:
            pytest.fail(f"Run {run['id']} did not complete within 60 seconds")
        time.sleep(2)

    assert run["status"].upper() in {"COMPLETED", "PASSED"}, run
    assert run["provenance"] == "REAL_EXECUTION"
    assert len(run["step_results"]) == 1
    assert run["step_results"][0]["status"] == "passed"
    assert run["step_results"][0]["provenance"] == "REAL_EXECUTION"
    assert run["step_results"][0]["status_code"] == 200

    generated_report = _json(
        smoke_client.post(f"/api/runs/{run['id']}/report/generate"),
        "generate report",
    )
    report = _json(
        smoke_client.get(f"/api/reports/{generated_report['id']}"),
        "fetch report",
    )

    assert report["run_id"] == run["id"]
    assert report["relative_path"]
