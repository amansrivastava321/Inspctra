from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.event_stream import EventStream
from qa_ai.product_backend.run_manager import RunManager
from qa_ai.product_backend.run_event_recorder import RunEventRecorder
from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.storage import ProductStorage


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path.startswith("/api"):
            payload = json.dumps({"status": "ok", "source": "local-fixture"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", "session=do-not-persist")
            self.end_headers()
            self.wfile.write(payload)
            return

        html = b"""<!doctype html>
<html><head><title>Example Domain</title></head>
<body><h1>Fixture page</h1>
<script>
console.info('informational');
console.warn('fixture warning');
console.error('fixture error');
</script></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture(scope="module")
def local_http_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


def _execute_run(
    tmp_path: Path,
    *,
    run_id: str,
    steps: list[dict],
    app_target: dict,
) -> tuple[dict, list[dict], list[dict], ArtifactIndex]:
    storage = ProductStorage(str(tmp_path / f"{run_id}.db"))
    index = ArtifactIndex(tmp_path / f"{run_id}-artifacts")
    storage.create_run(
        {
            "id": run_id,
            "pack_id": "pack-fixture",
            "app_target_id": app_target["id"],
            "status": "pending",
            "execution_mode": "automated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    recorder = RunEventRecorder(storage)
    manager = RunManager(EventStream(), storage, index, event_recorder=recorder)
    manager._execute(run_id, steps, app_target, threading.Event())
    assert recorder.flush(timeout=2.0)
    run = storage.get_run(run_id)
    evidence = storage.list_evidence(run_id)
    events = storage.list_run_events(run_id)
    recorder.close()
    storage.close()
    return run, evidence, events, index


def test_action_family_contract() -> None:
    from qa_ai.product_backend import run_manager

    assert hasattr(run_manager, "classify_action_family")
    classify = run_manager.classify_action_family
    assert classify("navigate") == "browser"
    assert classify("api_request") == "api"
    assert classify("passive_security_check", app_type="api") == "api"
    assert classify("passive_security_check", app_type="web") == "browser"
    assert classify("mobile_tap") == "unavailable"
    assert classify("chaos_latency") == "unavailable"
    assert classify("enterprise_policy") == "unavailable"


def test_unimplemented_platform_action_is_unavailable_and_not_successful(tmp_path: Path) -> None:
    run, evidence, _, _ = _execute_run(
        tmp_path,
        run_id="mobile-unavailable",
        app_target={
            "id": "app-mobile",
            "project_id": "project-fixture",
            "app_type": "android",
        },
        steps=[
            {
                "step_id": "mobile-step",
                "description": "Tap the native app",
                "action_type": "mobile_tap",
            }
        ],
    )

    assert run["status"] == "failed"
    assert run["provenance"] == "UNAVAILABLE"
    assert run["step_results"][0]["status"] == "capability_gap"
    assert run["step_results"][0]["provenance"] == "UNAVAILABLE"
    assert evidence == []


def test_browser_runtime_failure_is_actionable_and_never_dry_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qa_ai.live_execution.playwright_engine import PlaywrightEngine

    monkeypatch.setattr(PlaywrightEngine, "launch", lambda self: False)
    monkeypatch.setattr(
        RunManager,
        "_run_step_safe",
        MagicMock(side_effect=AssertionError("supported browser step reached dry-run fallback")),
    )
    run, _, _, _ = _execute_run(
        tmp_path,
        run_id="browser-unavailable",
        app_target={
            "id": "app-web",
            "project_id": "project-fixture",
            "app_type": "web",
            "base_url": "https://example.com",
        },
        steps=[
            {
                "step_id": "navigate-step",
                "description": "Open the page",
                "action_type": "navigate",
                "target": "https://example.com",
            }
        ],
    )

    result = run["step_results"][0]
    assert run["status"] == "failed"
    assert result["status"] == "error"
    assert result["provenance"] == "UNAVAILABLE"
    assert "python -m playwright install chromium" in result["notes"]


def test_api_only_run_does_not_initialize_playwright(
    tmp_path: Path,
    local_http_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qa_ai.live_execution.playwright_engine import PlaywrightEngine

    launch = MagicMock(side_effect=AssertionError("API-only run launched Chromium"))
    monkeypatch.setattr(PlaywrightEngine, "launch", launch)
    run, evidence, events, _ = _execute_run(
        tmp_path,
        run_id="api-only",
        app_target={
            "id": "app-api",
            "project_id": "project-fixture",
            "app_type": "web",
            "base_url": local_http_url,
        },
        steps=[
            {
                "step_id": "api-step",
                "description": "Call local API",
                "action_type": "api_request",
                "method": "GET",
                "url": f"{local_http_url}/api",
                "expected_status": 200,
                "timeout_seconds": 1.25,
                "headers": {"Authorization": "Bearer local-secret"},
            }
        ],
    )

    launch.assert_not_called()
    assert run["status"] == "completed"
    assert run["provenance"] == "REAL_EXECUTION"
    assert run["step_results"][0]["status"] == "passed"
    result = run["step_results"][0]
    assert result["started_at"].endswith("+00:00")
    assert result["completed_at"].endswith("+00:00")
    assert result["duration_ms"] >= 0
    assert {event["event_type"] for event in events} >= {
        "step_started", "step_completed", "evidence_captured",
    }
    assert {item["type"] for item in evidence} >= {"api_request", "api_response", "api_assertion"}
    assert {item["provenance"] for item in evidence} == {"REAL_EXECUTION"}
    for item in evidence:
        assert item["metadata_json"]["app_id"] == "app-api"
        assert item["metadata_json"]["project_id"] == "project-fixture"
        assert item["metadata_json"]["step_index"] == 1
    request = next(item for item in evidence if item["type"] == "api_request")
    assert request["metadata_json"]["headers"]["Authorization"] == "Bearer ***REDACTED***"


def test_browser_run_persists_full_page_and_filtered_console_evidence(
    tmp_path: Path,
    local_http_url: str,
) -> None:
    run, evidence, _, index = _execute_run(
        tmp_path,
        run_id="web-pass",
        app_target={
            "id": "app-web",
            "project_id": "project-fixture",
            "app_type": "web",
            "base_url": local_http_url,
        },
        steps=[
            {
                "step_id": "navigate-step",
                "description": "Open fixture",
                "action_type": "navigate",
                "target": local_http_url,
                "timeout_seconds": 5,
            }
        ],
    )

    assert run["status"] == "completed"
    assert run["provenance"] == "REAL_EXECUTION"
    screenshot = next(item for item in evidence if item["type"] == "screenshot")
    console = next(item for item in evidence if item["type"] == "console")
    assert screenshot["mime_type"] == "image/png"
    assert b"PNG" in b"".join(index.stream_file(screenshot["relative_path"]))[:16]
    console_payload = json.loads(b"".join(index.stream_file(console["relative_path"])))
    assert {entry["type"] for entry in console_payload} == {"warning", "error"}


def test_failed_browser_assertion_persists_png_and_html(
    tmp_path: Path,
    local_http_url: str,
) -> None:
    run, evidence, _, index = _execute_run(
        tmp_path,
        run_id="web-fail",
        app_target={
            "id": "app-web",
            "project_id": "project-fixture",
            "app_type": "web",
            "base_url": local_http_url,
        },
        steps=[
            {
                "step_id": "title-step",
                "description": "Reject wrong title",
                "action_type": "assert_title_contains",
                "expected_result": "NonExistentText",
                "timeout_seconds": 5,
            }
        ],
    )

    result = run["step_results"][0]
    assert run["status"] == "failed"
    assert result["status"] == "failed"
    assert result["provenance"] == "REAL_EXECUTION"
    assert result["notes"] == "Expected title to contain 'NonExistentText' but was 'Example Domain'"
    assert {item["type"] for item in evidence} >= {"screenshot", "page_html"}
    html = next(item for item in evidence if item["type"] == "page_html")
    assert b"Example Domain" in b"".join(index.stream_file(html["relative_path"]))


def test_manual_confirmation_updates_pending_evidence_in_place(tmp_path: Path) -> None:
    app = create_product_app(
        artifacts_dir=str(tmp_path / "manual-artifacts"),
        db_path=str(tmp_path / "manual.db"),
    )
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "Manual Project"}).json()
        target = client.post(
            "/api/apps",
            json={"project_id": project["id"], "name": "Manual App", "app_type": "web"},
        ).json()
        pack = client.post(
            "/api/validation-packs",
            json={
                "project_id": project["id"],
                "name": "Manual Pack",
                "steps": [
                    {"step_id": "manual-1", "description": "Check one", "action_type": "verify"},
                    {"step_id": "manual-2", "description": "Check two", "action_type": "verify"},
                ],
            },
        ).json()
        run = client.post(
            f"/api/validation-packs/{pack['id']}/run",
            json={"app_target_id": target["id"], "execution_mode": "manual"},
        ).json()

        assert [item["status"] for item in run["step_results"]] == ["pending", "pending"]
        assert {item["provenance"] for item in run["step_results"]} == {"UNAVAILABLE"}
        before = client.get(f"/api/evidence?run_id={run['id']}").json()
        assert len(before) == 2
        assert {item["evidence_type"] for item in before} == {"manual_confirmation"}
        assert {item["provenance"] for item in before} == {"UNAVAILABLE"}
        first = next(item for item in before if item["step_id"] == "manual-1")

        updated = client.post(
            f"/api/live-runs/{run['id']}/manual-steps/manual-1/result",
            json={"status": "passed", "notes": "Checked", "tester_name": "Smoke Tester"},
        )
        assert updated.status_code == 200
        after = client.get(f"/api/evidence?run_id={run['id']}").json()
        assert len(after) == 2
        confirmed = next(item for item in after if item["id"] == first["id"])
        assert confirmed["provenance"] == "REAL_EXECUTION"
        assert confirmed["metadata_json"]["status"] == "passed"
        assert confirmed["metadata_json"]["tester_name"] == "Smoke Tester"
        assert confirmed["metadata_json"]["app_id"] == target["id"]
        assert confirmed["metadata_json"]["project_id"] == project["id"]

        uploaded = client.post(
            f"/api/live-runs/{run['id']}/manual-steps/manual-1/evidence",
            files={"file": ("../../other-run/overwrite.txt", b"manual proof", "text/plain")},
            data={"name": "Manual note", "evidence_type": "log"},
        )
        assert uploaded.status_code == 200
        uploaded_body = uploaded.json()
        assert uploaded_body["relative_path"].startswith(f"runs/{run['id']}/manual_")
        assert ".." not in uploaded_body["relative_path"]
        assert app.state.run_event_recorder.flush(timeout=2.0)
        events = client.get(f"/api/runs/{run['id']}/events").json()
        assert [event["event_type"] for event in events[-2:]] == [
            "step_completed",
            "evidence_captured",
        ]
        assert events[-1]["step_id"] == "manual-1"
        assert events[-1]["payload"]["evidence_id"] == uploaded_body["id"]
        assert events[-1]["payload"]["evidence_type"] == "log"
        assert events[-1]["payload"]["provenance"] == "REAL_EXECUTION"


def test_artifacts_directory_can_be_configured_by_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "configured-artifacts"
    monkeypatch.setenv("INSPECTRA_ARTIFACTS_DIR", str(configured))
    app = create_product_app(db_path=str(tmp_path / "configured.db"), artifacts_dir=None)
    with TestClient(app):
        assert app.state.artifact_index._base == configured.resolve()
    assert configured.is_dir()


def test_structured_step_timeout_reaches_api_engine_once_converted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qa_ai.live_execution.api_engine import ApiEngine

    observed: list[float] = []

    def fake_execute(self, step, app_target, context):
        observed.append(step["timeout_seconds"])
        return {
            "status": "passed",
            "notes": "fixture response",
            "request_summary": {"method": "GET", "url": step["url"], "headers": {}},
            "response_summary": {"status_code": 200, "response_time_ms": 1, "final_url": step["url"]},
            "bytes_exchanged": True,
            "context": {"last_response": {"status_code": 200}},
        }

    monkeypatch.setattr(ApiEngine, "execute_step", fake_execute)
    app = create_product_app(
        artifacts_dir=str(tmp_path / "timeout-artifacts"),
        db_path=str(tmp_path / "timeout.db"),
    )
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "Timeout Project"}).json()
        target = client.post(
            "/api/apps",
            json={"project_id": project["id"], "name": "Timeout API", "app_type": "api"},
        ).json()
        pack = client.post(
            "/api/validation-packs",
            json={"project_id": project["id"], "name": "Timeout Pack"},
        ).json()
        case = client.post(
            f"/api/validation-packs/{pack['id']}/test-cases",
            json={"title": "Timeout Case"},
        ).json()
        client.post(
            f"/api/test-cases/{case['test_case_id']}/steps",
            json={
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/health",
                "timeout_ms": 1250,
            },
        )
        started = client.post(
            f"/api/validation-packs/{pack['id']}/run",
            json={"app_target_id": target["id"]},
        ).json()
        deadline = time.monotonic() + 5
        while client.get(f"/api/runs/{started['id']}").json()["status"] in {"pending", "running"}:
            assert time.monotonic() < deadline
            time.sleep(0.01)

    assert observed == [1.25]
