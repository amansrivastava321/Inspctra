"""A scheduled run executes the same steps as a hand-started one and honours the pack's saved options."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.run_manager import RunManager
from qa_ai.product_backend.server import create_product_app


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A pack with two test cases (one API step carrying JSON-path/budget fields) and a captured start_run."""
    started: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        RunManager, "start_run",
        lambda self, run_id, steps, target, options=None: started.append({"steps": steps, "options": options}),
    )
    app = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(tmp_path / "s.db"))
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "P", "description": ""}).json()
        target = client.post(
            "/api/apps",
            json={"name": "A", "app_type": "web", "project_id": project["id"], "base_url": "http://127.0.0.1:1/"},
        ).json()
        pack = client.post(
            "/api/validation-packs",
            json={"project_id": project["id"], "app_id": target["id"], "name": "Pack", "description": ""},
        ).json()
        for title, steps in [
            ("Login", [{"action_type": "navigate", "target": "/"}, {"action_type": "click", "target": "#go"}]),
            ("Health", [{
                "action_type": "api_request", "method": "GET", "url": "http://127.0.0.1:1/health",
                "expected_status": 200, "expected_json_path": "$.ok", "expected_value": "true",
            }]),
        ]:
            case = client.post(
                f"/api/validation-packs/{pack['id']}/test-cases", json={"title": title, "enabled": True, "steps": []}
            ).json()
            for step in steps:
                assert client.post(f"/api/test-cases/{case['test_case_id']}/steps", json={**step, "timeout_ms": 5000}).status_code == 201
        yield client, pack, target, started


def _manual_steps(client: TestClient, pack: Dict[str, Any], target: Dict[str, Any], started: List[Dict[str, Any]]):
    assert client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]}).status_code == 202
    return started[-1]


def test_a_scheduled_run_has_exactly_the_steps_a_manual_run_has(world) -> None:
    client, pack, target, started = world
    manual = _manual_steps(client, pack, target, started)

    assert client.app.state.run_manager.schedule_run(pack["id"]) is not None

    assert started[-1]["steps"] == manual["steps"]
    api_step = next(s for s in started[-1]["steps"] if s["action_type"] == "api_request")
    assert (api_step["expected_json_path"], api_step["expected_value"]) == ("$.ok", "true")


def test_a_scheduled_run_is_marked_scheduled_and_hidden(world) -> None:
    client, pack, _, started = world

    client.app.state.run_manager.schedule_run(pack["id"])

    options = started[-1]["options"]
    assert options.scheduled is True and options.watch is False and options.slow_mo_ms == 0


def test_one_flow_is_off_for_a_scheduled_run_until_the_pack_asks_for_it(world) -> None:
    client, pack, _, started = world

    client.app.state.run_manager.schedule_run(pack["id"])

    assert started[-1]["options"].continuous is False


def test_a_pack_saved_as_one_flow_runs_its_scheduled_runs_as_one_flow(world) -> None:
    client, pack, _, started = world
    client.patch(f"/api/validation-packs/{pack['id']}", json={"continuous": True})

    client.app.state.run_manager.schedule_run(pack["id"])

    options = started[-1]["options"]
    assert options.continuous is True
    assert len(options.case_ids) == len(started[-1]["steps"]) == 3
    assert len(set(options.case_ids)) == 2  # the steps are grouped under their two test cases
