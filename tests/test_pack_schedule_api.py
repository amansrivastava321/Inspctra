"""Saving a pack's schedule returns the next run time the scheduler just stored."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.server import create_product_app


@pytest.fixture
def api(tmp_path: Path):
    app = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(tmp_path / "api.db"))
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "P", "description": ""}).json()
        pack = client.post(
            "/api/validation-packs", json={"project_id": project["id"], "name": "Pack", "description": ""}
        ).json()
        yield client, pack


def _next_run(payload: dict) -> datetime:
    return datetime.fromisoformat(payload["next_run_at"])


@pytest.mark.parametrize("schedule", ["hourly", "daily", "nightly", "weekdays"])
def test_enabling_a_schedule_returns_its_next_run_in_the_response(api, schedule: str) -> None:
    client, pack = api

    response = client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule": schedule, "schedule_enabled": True})

    assert response.status_code == 200
    assert _next_run(response.json()) > datetime.now(timezone.utc)


def test_the_response_matches_what_a_later_read_returns(api) -> None:
    client, pack = api

    saved = client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule": "hourly", "schedule_enabled": True}).json()
    fetched = client.get(f"/api/validation-packs/{pack['id']}").json()

    assert saved["next_run_at"] == fetched["next_run_at"] is not None


def test_turning_the_schedule_off_clears_the_next_run(api) -> None:
    client, pack = api
    client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule": "hourly", "schedule_enabled": True})

    response = client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule_enabled": False})

    assert response.json()["next_run_at"] is None


def test_an_unrelated_edit_leaves_the_next_run_alone(api) -> None:
    client, pack = api
    first = client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule": "hourly", "schedule_enabled": True}).json()

    renamed = client.patch(f"/api/validation-packs/{pack['id']}", json={"name": "Renamed"}).json()

    assert renamed["name"] == "Renamed"
    assert renamed["next_run_at"] == first["next_run_at"]
