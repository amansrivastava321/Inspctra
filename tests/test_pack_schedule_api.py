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


# ── intervals, timezone, saved options, webhook ──────────────────────────────

def test_an_interval_schedule_is_accepted_and_fires_that_long_from_now(api) -> None:
    client, pack = api

    response = client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule": "every_15m", "schedule_enabled": True})

    assert response.status_code == 200
    delta = _next_run(response.json()) - datetime.now(timezone.utc)
    assert 14 * 60 < delta.total_seconds() <= 15 * 60


@pytest.mark.parametrize("schedule", ["every_1m", "every_999h", "weekly", "every_5m; rm -rf /"])
def test_an_unknown_schedule_is_a_400_and_changes_nothing(api, schedule: str) -> None:
    client, pack = api

    response = client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule": schedule})

    assert response.status_code == 400
    assert client.get(f"/api/validation-packs/{pack['id']}").json()["schedule"] in (None, "none")


def test_the_timezone_decides_when_a_daily_run_fires(api) -> None:
    client, pack = api

    saved = client.patch(
        f"/api/validation-packs/{pack['id']}",
        json={"schedule": "daily", "schedule_enabled": True, "schedule_timezone": "Asia/Kolkata"},
    ).json()

    from zoneinfo import ZoneInfo
    assert saved["schedule_timezone"] == "Asia/Kolkata"
    assert _next_run(saved).astimezone(ZoneInfo("Asia/Kolkata")).hour == 2


def test_changing_only_the_timezone_recomputes_the_next_run(api) -> None:
    client, pack = api
    client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule": "daily", "schedule_enabled": True})

    moved = client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule_timezone": "America/Los_Angeles"}).json()

    from zoneinfo import ZoneInfo
    assert _next_run(moved).astimezone(ZoneInfo("America/Los_Angeles")).hour == 2


def test_an_unknown_timezone_is_a_400(api) -> None:
    client, pack = api

    response = client.patch(f"/api/validation-packs/{pack['id']}", json={"schedule_timezone": "Mars/Olympus"})

    assert response.status_code == 400
    assert client.get(f"/api/validation-packs/{pack['id']}").json()["schedule_timezone"] == "UTC"


def test_one_flow_is_saved_on_the_pack_and_off_by_default(api) -> None:
    client, pack = api
    assert client.get(f"/api/validation-packs/{pack['id']}").json()["continuous"] is False

    saved = client.patch(f"/api/validation-packs/{pack['id']}", json={"continuous": True}).json()
    assert saved["continuous"] is True
    assert client.get(f"/api/validation-packs/{pack['id']}").json()["continuous"] is True

    assert client.patch(f"/api/validation-packs/{pack['id']}", json={"continuous": False}).json()["continuous"] is False


def test_the_webhook_url_is_saved_but_only_its_origin_is_ever_returned(api) -> None:
    client, pack = api
    url = "https://hooks.example.com/services/T000/B000/topsecrettoken"

    saved = client.patch(f"/api/validation-packs/{pack['id']}", json={"notify_webhook_url": url})

    assert saved.status_code == 200
    for body in (saved.json(), client.get(f"/api/validation-packs/{pack['id']}").json(),
                 client.get("/api/validation-packs").json()[0]):
        assert body["notify_webhook_url"] == "https://hooks.example.com/***"
        assert "topsecrettoken" not in str(body)


def test_the_stored_webhook_url_is_the_real_one(api, tmp_path: Path) -> None:
    client, pack = api
    url = "https://hooks.example.com/services/T000/B000/topsecrettoken"
    client.patch(f"/api/validation-packs/{pack['id']}", json={"notify_webhook_url": url})

    stored = client.app.state.storage.get_validation_pack(pack["id"])

    assert stored["notify_webhook_url"] == url


def test_an_empty_webhook_url_clears_it(api) -> None:
    client, pack = api
    client.patch(f"/api/validation-packs/{pack['id']}", json={"notify_webhook_url": "https://hooks.example.com/x"})

    cleared = client.patch(f"/api/validation-packs/{pack['id']}", json={"notify_webhook_url": ""}).json()

    assert cleared["notify_webhook_url"] is None


@pytest.mark.parametrize("url", ["ftp://example.com/x", "file:///etc/passwd", "not a url"])
def test_a_non_http_webhook_url_is_a_400(api, url: str) -> None:
    client, pack = api

    assert client.patch(f"/api/validation-packs/{pack['id']}", json={"notify_webhook_url": url}).status_code == 400
