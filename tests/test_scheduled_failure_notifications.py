"""A scheduled run that fails is reported to the pack's webhook; nothing else is."""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from qa_ai.product_backend import notifier
from qa_ai.product_backend.notifier import (
    build_failure_payload,
    is_valid_webhook_url,
    mask_webhook_url,
    notify_scheduled_failure,
)
from qa_ai.product_backend.run_manager import RunManager, RunOptions
from qa_ai.product_backend.storage import ProductStorage

SECRET = "sk-abcdefghijklmnopqrstuvwxyz123456"


class _Receiver:
    """A real local HTTP server that records what it is sent."""

    def __init__(self, status: int = 200, redirect_to: Optional[str] = None) -> None:
        self.requests: List[Dict[str, Any]] = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                outer.requests.append({"path": self.path, "body": json.loads(self.rfile.read(length) or b"{}")})
                if redirect_to:
                    self.send_response(302)
                    self.send_header("Location", redirect_to)
                else:
                    self.send_response(status)
                self.end_headers()

            def log_message(self, *args: Any) -> None:
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/hook/token-123"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def receiver():
    made: List[_Receiver] = []

    def make(**kwargs: Any) -> _Receiver:
        made.append(_Receiver(**kwargs))
        return made[-1]

    yield make
    for item in made:
        item.close()


def _run(status: str = "failed") -> Dict[str, Any]:
    return {
        "id": "run-1", "status": status, "completed_at": "2026-01-01T00:00:00+00:00", "error": None,
        "step_results": [
            {"step": 2, "status": "failed", "description": "[Login] click #go", "error": f"timeout, key {SECRET}"},
            {"step": 1, "status": "passed", "description": "[Login] navigate /"},
        ],
    }


# ── URL handling ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", ["https://hooks.example.com/a/b", "http://localhost:8080/x", "http://127.0.0.1:9/"])
def test_http_urls_are_accepted(url: str) -> None:
    assert is_valid_webhook_url(url)


@pytest.mark.parametrize(
    "url",
    ["", None, "ftp://example.com/x", "file:///etc/passwd", "javascript:alert(1)", "https://", "no scheme", "http://" + "a" * 600],
    ids=["empty", "none", "ftp", "file", "javascript", "no-host", "no-scheme", "too-long"],
)
def test_other_urls_are_rejected(url) -> None:
    assert not is_valid_webhook_url(url)


def test_only_the_origin_of_a_webhook_is_ever_shown() -> None:
    masked = mask_webhook_url("https://user:pw@hooks.example.com/services/T000/B000/secrettoken?x=1")

    assert masked == "https://hooks.example.com/***"
    assert "secrettoken" not in masked and "pw" not in masked
    assert mask_webhook_url(None) is None and mask_webhook_url("") is None
    assert mask_webhook_url("garbage") == "***"


# ── payload ──────────────────────────────────────────────────────────────────

def test_the_payload_names_the_pack_run_and_failed_steps_without_secrets() -> None:
    payload = build_failure_payload({"id": "pk", "name": "Checkout"}, _run())

    assert payload["event"] == "scheduled_run_failed"
    assert payload["pack"] == {"id": "pk", "name": "Checkout"}
    assert payload["run"]["id"] == "run-1" and payload["run"]["status"] == "failed"
    assert [f["step"] for f in payload["failed_steps"]] == [2]
    assert SECRET not in json.dumps(payload)


def test_at_most_a_handful_of_failures_are_reported() -> None:
    run = _run()
    run["step_results"] = [{"step": i, "status": "failed", "error": "boom"} for i in range(1, 20)]

    assert len(build_failure_payload({"id": "p", "name": "n"}, run)["failed_steps"]) == notifier.MAX_FAILURES_REPORTED


# ── delivery ─────────────────────────────────────────────────────────────────

def test_a_failed_run_is_posted_to_the_webhook(receiver) -> None:
    hook = receiver()

    delivered = notify_scheduled_failure({"id": "pk", "name": "Checkout", "notify_webhook_url": hook.url}, _run())

    assert delivered is True
    assert len(hook.requests) == 1 and hook.requests[0]["path"] == "/hook/token-123"
    assert hook.requests[0]["body"]["run"]["id"] == "run-1"


@pytest.mark.parametrize("status", ["completed", "cancelled", "running"])
def test_runs_that_did_not_fail_send_nothing(receiver, status: str) -> None:
    hook = receiver()

    assert notify_scheduled_failure({"id": "pk", "notify_webhook_url": hook.url}, _run(status)) is False
    assert hook.requests == []


def test_a_pack_without_a_webhook_sends_nothing() -> None:
    assert notify_scheduled_failure({"id": "pk", "notify_webhook_url": None}, _run()) is False
    assert notify_scheduled_failure({"id": "pk", "notify_webhook_url": ""}, _run()) is False


def test_a_server_error_is_reported_as_not_delivered(receiver) -> None:
    hook = receiver(status=500)

    assert notify_scheduled_failure({"id": "pk", "notify_webhook_url": hook.url}, _run()) is False


def test_redirects_are_not_followed(receiver) -> None:
    target = receiver()
    hook = receiver(redirect_to=target.url)

    assert notify_scheduled_failure({"id": "pk", "notify_webhook_url": hook.url}, _run()) is False
    assert target.requests == []


def test_an_unreachable_webhook_does_not_raise_and_does_not_log_the_url(caplog: pytest.LogCaptureFixture) -> None:
    url = "http://127.0.0.1:1/hook/very-secret-token"

    with caplog.at_level("WARNING"):
        assert notify_scheduled_failure({"id": "pk", "notify_webhook_url": url}, _run()) is False

    assert "very-secret-token" not in caplog.text


# ── wiring into the run lifecycle ────────────────────────────────────────────

def _manager(tmp_path: Path, hook_url: Optional[str], run_status: str = "failed"):
    storage = ProductStorage(str(tmp_path / "n.db"))
    storage.create_project({"id": "pr", "name": "P", "description": "", "created_at": "t", "updated_at": "t"})
    storage.create_app_target({
        "id": "ap", "project_id": "pr", "name": "A", "app_type": "web", "base_url": "http://127.0.0.1:1/",
        "created_at": "t", "updated_at": "t",
    })
    storage.create_validation_pack({
        "id": "pk", "project_id": "pr", "app_id": "ap", "name": "Pack", "steps": [], "created_at": "t", "updated_at": "t",
        "notify_webhook_url": hook_url,
    })
    storage.create_run({
        "id": "run-1", "pack_id": "pk", "app_target_id": "ap", "status": run_status, "execution_mode": "automated",
        "created_at": "t",
    })
    return RunManager(event_stream=MagicMock(), storage=storage)


def test_a_scheduled_failed_run_notifies_the_pack_webhook(tmp_path: Path, receiver) -> None:
    hook = receiver()
    manager = _manager(tmp_path, hook.url)

    manager._notify_scheduled_failure("run-1", RunOptions(scheduled=True))

    assert len(hook.requests) == 1
    assert hook.requests[0]["body"]["pack"]["name"] == "Pack"


def test_a_run_started_by_hand_never_notifies(tmp_path: Path, receiver) -> None:
    hook = receiver()
    manager = _manager(tmp_path, hook.url)

    manager._notify_scheduled_failure("run-1", RunOptions())

    assert hook.requests == []


def test_a_scheduled_run_that_passed_never_notifies(tmp_path: Path, receiver) -> None:
    hook = receiver()
    manager = _manager(tmp_path, hook.url, run_status="completed")

    manager._notify_scheduled_failure("run-1", RunOptions(scheduled=True))

    assert hook.requests == []


def test_a_notification_problem_never_breaks_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(tmp_path, "http://127.0.0.1:1/x")
    monkeypatch.setattr("qa_ai.product_backend.run_manager.notify_scheduled_failure", MagicMock(side_effect=RuntimeError("boom")))

    manager._notify_scheduled_failure("run-1", RunOptions(scheduled=True))  # must not raise
