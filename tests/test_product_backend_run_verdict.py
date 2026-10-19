"""Run records expose a deterministic verdict derived from step results."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.run_verdict import count_steps, derive_verdict, verdict_for_run
from qa_ai.product_backend.server import create_product_app


def _steps(*statuses: str) -> list[dict]:
    return [{"status": status} for status in statuses]


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([], "pending"),
        (["passed", "passed"], "pass"),
        (["passed", "skipped"], "pass"),
        (["passed", "failed"], "fail"),
        (["passed", "error"], "fail"),
        (["passed", "inconclusive"], "fail"),
        (["passed", "blocked"], "fail"),
        (["dry_run_only", "dry_run_only"], "dry_run"),
        (["passed", "dry_run_only"], "unclear"),
        (["passed", "something_else"], "unclear"),
    ],
    ids=lambda value: "-".join(value) if isinstance(value, list) else value,
)
def test_derive_verdict_from_step_statuses(statuses: list[str], expected: str) -> None:
    assert derive_verdict(count_steps(_steps(*statuses))) == expected


@pytest.mark.parametrize("status", ["pending", "running"])
def test_unfinished_runs_have_no_verdict(status: str) -> None:
    assert verdict_for_run({"status": status, "step_results": _steps("passed")}) is None


def test_finished_run_verdict_follows_step_results() -> None:
    assert verdict_for_run({"status": "completed", "step_results": _steps("passed", "passed")}) == "pass"
    assert verdict_for_run({"status": "completed", "step_results": _steps("passed", "failed")}) == "fail"
    assert verdict_for_run({"status": "failed", "step_results": _steps("failed")}) == "fail"


def test_run_that_failed_without_any_step_result_is_a_failure() -> None:
    assert verdict_for_run({"status": "failed", "step_results": []}) == "fail"
    assert verdict_for_run({"status": "completed", "step_results": []}) is None
    assert verdict_for_run({"status": "cancelled", "step_results": []}) is None


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(tmp_path / "verdict.db"))
    with TestClient(app) as test_client:
        yield test_client


def test_api_run_verdict_matches_generated_report(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "P"}).json()
    app = client.post("/api/apps", json={"name": "A", "app_type": "web", "project_id": project["id"]}).json()
    pack = client.post("/api/validation-packs", json={
        "project_id": project["id"],
        "name": "Pack",
        "steps": [{"description": "Load homepage", "action_type": "navigate", "target": "/", "timeout_seconds": 10}],
    }).json()
    run_id = client.post(
        f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": app["id"]}
    ).json()["id"]

    run = {}
    for _ in range(100):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.1)
    assert run["status"] in ("completed", "failed", "cancelled")

    report = client.post(f"/api/runs/{run_id}/report/generate").json()
    listed = next(item for item in client.get("/api/runs").json() if item["id"] == run_id)
    live = client.get(f"/api/live-runs/{run_id}").json()

    assert run["verdict"] == report["verdict"]
    assert listed["verdict"] == report["verdict"]
    assert live["verdict"] == report["verdict"]
    assert run["verdict"] is not None
