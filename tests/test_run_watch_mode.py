"""Watch mode (a visible browser) and continuous flows for automated runs. Both are opt-in."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from qa_ai.live_execution import playwright_engine as engine_module
from qa_ai.live_execution.playwright_engine import PlaywrightEngine
from qa_ai.product_backend import run_manager as run_manager_module
from qa_ai.product_backend.models import LiveRunRecord, StartRunRequest
from qa_ai.product_backend.run_manager import (
    DEFAULT_WATCH_SLOW_MO_MS,
    RunManager,
    RunOptions,
    display_available,
)
from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.storage import ProductStorage


# ── display_available ────────────────────────────────────────────────────────

@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_desktop_platforms_always_have_a_display(monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    monkeypatch.setattr(run_manager_module.sys, "platform", platform)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    assert display_available() is True


@pytest.mark.parametrize(
    ("env", "expected"),
    [({}, False), ({"DISPLAY": ":99"}, True), ({"WAYLAND_DISPLAY": "wayland-0"}, True), ({"DISPLAY": ""}, False)],
)
def test_linux_needs_a_display_variable(monkeypatch: pytest.MonkeyPatch, env: Dict[str, str], expected: bool) -> None:
    monkeypatch.setattr(run_manager_module.sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert display_available() is expected


# ── request model ────────────────────────────────────────────────────────────

def test_a_plain_request_keeps_the_previous_behaviour() -> None:
    request = StartRunRequest(app_target_id="a")

    assert (request.watch, request.slow_mo_ms, request.continuous) == (False, None, False)


@pytest.mark.parametrize("bad", [-1, 5001])
def test_slow_motion_is_bounded(bad: int) -> None:
    with pytest.raises(ValueError):
        StartRunRequest(app_target_id="a", slow_mo_ms=bad)


# ── engine ───────────────────────────────────────────────────────────────────

class _FakeChromium:
    def __init__(self) -> None:
        self.launch_kwargs: Dict[str, Any] = {}
        self.browser = MagicMock()

    def launch(self, **kwargs: Any) -> MagicMock:
        self.launch_kwargs = kwargs
        return self.browser


class _FakePlaywright:
    def __init__(self) -> None:
        self.chromium = _FakeChromium()

    def stop(self) -> None:
        pass


def _launch_with_fake_playwright(monkeypatch: pytest.MonkeyPatch, config: Dict[str, Any]) -> _FakeChromium:
    fake = _FakePlaywright()
    starter = MagicMock()
    starter.start.return_value = fake
    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: starter)
    assert PlaywrightEngine(config=config).launch() is True
    return fake.chromium


def test_slow_motion_reaches_the_browser_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    chromium = _launch_with_fake_playwright(monkeypatch, {"headless": False, "slow_mo": 250})

    assert chromium.launch_kwargs == {"headless": False, "slow_mo": 250}


def test_the_default_launch_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    chromium = _launch_with_fake_playwright(monkeypatch, {"headless": True})

    assert chromium.launch_kwargs == {"headless": True}


def test_continue_context_keeps_the_page_and_clears_per_step_buffers() -> None:
    engine = PlaywrightEngine(config={})
    engine._browser, engine._context, engine._page = MagicMock(), MagicMock(), MagicMock()
    engine._page.is_closed.return_value = False
    engine._console_messages.append({"type": "log", "text": "from the previous step"})
    engine._network_summary.append({"url": "x"})
    page = engine._page

    assert engine.continue_context(timeout_seconds=2.5) is True

    assert engine._page is page and engine._context.close.call_count == 0
    engine._context.set_default_timeout.assert_called_once_with(2500)
    assert engine._console_messages == [] and engine._network_summary == []


def test_continue_context_needs_a_live_page() -> None:
    assert PlaywrightEngine(config={}).continue_context() is False


def test_continue_context_refuses_a_page_that_has_been_closed() -> None:
    engine = PlaywrightEngine(config={})
    engine._browser, engine._context, engine._page = MagicMock(), MagicMock(), MagicMock()
    engine._page.is_closed.return_value = True

    assert engine.continue_context() is False
    engine._context.set_default_timeout.assert_not_called()


# ── launching ────────────────────────────────────────────────────────────────

class _RecordingEngine:
    """Stands in for PlaywrightEngine; `outcomes` decides whether each launch succeeds, raises, or fails."""

    instances: List["_RecordingEngine"] = []
    outcomes: List[Any] = []

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        type(self).instances.append(self)

    def launch(self) -> bool:
        outcome = type(self).outcomes.pop(0) if type(self).outcomes else True
        if isinstance(outcome, Exception):
            raise outcome
        return bool(outcome)


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> RunManager:
    _RecordingEngine.instances, _RecordingEngine.outcomes = [], []
    monkeypatch.setattr(engine_module, "PlaywrightEngine", _RecordingEngine)
    run_manager = RunManager(event_stream=MagicMock(), storage=MagicMock())
    run_manager._publish_event = MagicMock()
    return run_manager


def _events(manager: RunManager) -> List[str]:
    return [call.args[1] for call in manager._publish_event.call_args_list]


def _messages(manager: RunManager) -> List[str]:
    return [call.args[2].get("message", "") for call in manager._publish_event.call_args_list]


def test_default_runs_launch_a_hidden_browser_exactly_as_before(manager: RunManager) -> None:
    engine = manager._launch_browser("run", RunOptions())

    assert engine is _RecordingEngine.instances[0]
    assert [i.config for i in _RecordingEngine.instances] == [{"headless": True}]
    assert _messages(manager) == ["Launching headless Chromium..."]


def test_watch_launches_a_visible_slowed_browser_when_there_is_a_display(
    manager: RunManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_manager_module, "display_available", lambda: True)

    engine = manager._launch_browser("run", RunOptions(watch=True, slow_mo_ms=420))

    assert engine is _RecordingEngine.instances[0]
    assert [i.config for i in _RecordingEngine.instances] == [{"headless": False, "slow_mo": 420}]
    assert _messages(manager) == ["Launching visible Chromium (watch mode)..."]


def test_watch_without_a_display_falls_back_to_hidden_and_says_so(
    manager: RunManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_manager_module, "display_available", lambda: False)

    engine = manager._launch_browser("run", RunOptions(watch=True, slow_mo_ms=420))

    assert engine is not None
    assert [i.config for i in _RecordingEngine.instances] == [{"headless": True}]  # one attempt, no slow motion
    assert _events(manager) == ["watch_unavailable", "browser_started"]


@pytest.mark.parametrize("failure", [False, RuntimeError("no window server")])
def test_a_visible_browser_that_cannot_open_falls_back_to_hidden(
    manager: RunManager, monkeypatch: pytest.MonkeyPatch, failure: Any
) -> None:
    monkeypatch.setattr(run_manager_module, "display_available", lambda: True)
    _RecordingEngine.outcomes = [failure, True]

    engine = manager._launch_browser("run", RunOptions(watch=True, slow_mo_ms=100))

    assert engine is _RecordingEngine.instances[1]
    assert [i.config for i in _RecordingEngine.instances] == [{"headless": False, "slow_mo": 100}, {"headless": True}]
    assert "watch_unavailable" in _events(manager)


def test_the_fallback_notice_is_stored_with_the_run_but_the_launch_line_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A "watch" run that ended up hidden must say so after it has finished, not only on the live stream."""
    _RecordingEngine.instances, _RecordingEngine.outcomes = [], []
    monkeypatch.setattr(engine_module, "PlaywrightEngine", _RecordingEngine)
    monkeypatch.setattr(run_manager_module, "display_available", lambda: False)
    recorder = MagicMock()
    run_manager = RunManager(event_stream=MagicMock(), storage=MagicMock(), event_recorder=recorder)

    run_manager._launch_browser("run-1", RunOptions(watch=True, slow_mo_ms=100))

    stored = [call.args[0] for call in recorder.record.call_args_list]
    assert [(e["event_type"], e["run_id"]) for e in stored] == [("notice", "run-1")]
    assert "hidden browser" in stored[0]["message"]


def test_the_live_copy_of_the_notice_uses_the_same_type_so_it_is_not_shown_twice(
    manager: RunManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_manager_module, "display_available", lambda: False)

    manager._launch_browser("run", RunOptions(watch=True))

    notice = next(call for call in manager._publish_event.call_args_list if call.args[1] == "watch_unavailable")
    assert notice.args[3] == "notice"


def test_no_browser_at_all_returns_none(manager: RunManager) -> None:
    _RecordingEngine.outcomes = [False]

    assert manager._launch_browser("run", RunOptions()) is None


# ── flows ────────────────────────────────────────────────────────────────────

class _FakePage:
    def __init__(self, log: List[str]) -> None:
        self.log = log

    def goto(self, url: str, **_kwargs: Any) -> None:
        self.log.append("goto")


class _FakeFlowEngine:
    def __init__(self) -> None:
        self.log: List[str] = []
        self.page = _FakePage(self.log)

    def reset_context(self, timeout_seconds: float = 30) -> bool:
        self.log.append("reset")
        return True

    def continue_context(self, timeout_seconds: float = 30) -> bool:
        self.log.append("continue")
        return True

    def close(self) -> None:
        self.log.append("close")


def _step(action: str, step_id: str) -> Dict[str, Any]:
    return {"step_id": step_id, "action_type": action, "target": "#x", "description": step_id, "timeout_seconds": 5}


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, steps: List[Dict[str, Any]], options: RunOptions) -> List[str]:
    storage = ProductStorage(str(tmp_path / "flows.db"))
    run = LiveRunRecord(pack_id="p", app_target_id="a")
    storage.create_run(run.model_dump())
    run_manager = RunManager(event_stream=MagicMock(), storage=storage)
    run_manager._publish_event = MagicMock()
    run_manager._ingest_memory = MagicMock()  # never write the memory store from a unit test
    fake = _FakeFlowEngine()
    run_manager._launch_browser = lambda *_a, **_k: fake  # type: ignore[method-assign]
    run_manager._run_step_real = lambda *_a, **_k: {"status": "passed", "notes": ""}  # type: ignore[method-assign]

    run_manager._execute(run.id, steps, {"base_url": "http://127.0.0.1:1/"}, threading.Event(), options)

    assert storage.get_run(run.id)["status"] == "completed"
    return fake.log


FLOW = [_step("click", "s1"), _step("type", "s2"), _step("assert_visible", "s3"), _step("click", "t1"), _step("type", "t2")]
CASES = ("case-a", "case-a", "case-a", "case-b", "case-b")


def test_isolated_runs_reset_before_every_step_as_before(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _run(tmp_path, monkeypatch, FLOW, RunOptions())

    assert log == ["reset", "goto"] * 5 + ["close"]


def test_continuous_runs_keep_the_session_within_a_test_case_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _run(tmp_path, monkeypatch, FLOW, RunOptions(continuous=True, case_ids=CASES))

    # case-a: fresh start then two continuations; case-b: a fresh start (and reload) then one continuation.
    assert log == ["reset", "goto", "continue", "continue", "reset", "goto", "continue", "close"]


def test_continuous_without_case_information_stays_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    unknown = _run(tmp_path, monkeypatch, FLOW, RunOptions(continuous=True))
    mismatched = _run(tmp_path, monkeypatch, FLOW, RunOptions(continuous=True, case_ids=("case-a",)))
    no_case = _run(tmp_path, monkeypatch, FLOW, RunOptions(continuous=True, case_ids=(None,) * 5))

    for log in (unknown, mismatched, no_case):
        assert log == ["reset", "goto"] * 5 + ["close"]


def test_a_failed_continue_falls_back_to_a_fresh_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Flaky(_FakeFlowEngine):
        def continue_context(self, timeout_seconds: float = 30) -> bool:
            self.log.append("continue-failed")
            return False

    storage = ProductStorage(str(tmp_path / "flaky.db"))
    run = LiveRunRecord(pack_id="p", app_target_id="a")
    storage.create_run(run.model_dump())
    run_manager = RunManager(event_stream=MagicMock(), storage=storage)
    run_manager._publish_event = MagicMock()
    run_manager._ingest_memory = MagicMock()
    fake = Flaky()
    run_manager._launch_browser = lambda *_a, **_k: fake  # type: ignore[method-assign]
    run_manager._run_step_real = lambda *_a, **_k: {"status": "passed", "notes": ""}  # type: ignore[method-assign]

    run_manager._execute(
        run.id, FLOW[:2], {"base_url": "http://127.0.0.1:1/"}, threading.Event(),
        RunOptions(continuous=True, case_ids=("c", "c")),
    )

    assert fake.log == ["reset", "goto", "continue-failed", "reset", "goto", "close"]


def test_an_api_step_inside_a_test_case_does_not_disturb_the_browser(tmp_path: Path) -> None:
    storage = ProductStorage(str(tmp_path / "mixed.db"))
    run = LiveRunRecord(pack_id="p", app_target_id="a")
    storage.create_run(run.model_dump())
    run_manager = RunManager(event_stream=MagicMock(), storage=storage)
    run_manager._publish_event = MagicMock()
    run_manager._ingest_memory = MagicMock()
    fake = _FakeFlowEngine()
    run_manager._launch_browser = lambda *_a, **_k: fake  # type: ignore[method-assign]
    run_manager._run_step_real = lambda *_a, **_k: {"status": "passed", "notes": ""}  # type: ignore[method-assign]
    run_manager._run_api_step = lambda *_a, **_k: {"status": "passed", "notes": ""}  # type: ignore[method-assign]
    steps = [_step("click", "b1"), _step("api_request", "a1"), _step("click", "b2")]

    run_manager._execute(
        run.id, steps, {"base_url": "http://127.0.0.1:1/"}, threading.Event(),
        RunOptions(continuous=True, case_ids=("c", "c", "c")),
    )

    assert fake.log == ["reset", "goto", "continue", "close"]


def test_scheduled_runs_start_with_the_default_hidden_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = ProductStorage(str(tmp_path / "scheduled.db"))
    storage.create_project({"id": "pr", "name": "P", "description": "", "created_at": "t", "updated_at": "t"})
    storage.create_app_target({
        "id": "ap", "project_id": "pr", "name": "A", "app_type": "web", "base_url": "http://127.0.0.1:1/",
        "created_at": "t", "updated_at": "t",
    })
    storage.create_validation_pack({
        "id": "pk", "project_id": "pr", "app_id": "ap", "name": "Pack", "steps": [], "created_at": "t", "updated_at": "t",
    })
    run_manager = RunManager(event_stream=MagicMock(), storage=storage)
    captured: List[Any] = []
    monkeypatch.setattr(RunManager, "start_run", lambda self, *args, **kwargs: captured.append((args, kwargs)))

    assert run_manager.schedule_run("pk") is not None

    args, kwargs = captured[0]
    assert len(args) == 3 and kwargs == {}  # no options: a scheduled run is unattended, so it stays hidden


# ── the API ──────────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path: Path):
    app = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(tmp_path / "api.db"))
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "P", "description": ""}).json()
        target = client.post(
            "/api/apps", json={"name": "A", "app_type": "web", "project_id": project["id"], "base_url": "http://127.0.0.1:1/"}
        ).json()
        pack = client.post("/api/validation-packs", json={"project_id": project["id"], "name": "Pack", "description": ""}).json()
        yield client, app, pack, target


def _add_case(client: TestClient, pack_id: str, title: str, enabled: bool = True) -> str:
    response = client.post(
        f"/api/validation-packs/{pack_id}/test-cases",
        json={"title": title, "enabled": enabled, "steps": ["Click the go button", "Press the submit button"]},
    )
    assert response.status_code == 201, response.text
    return response.json()["test_case_id"]


def _capture_start_run(monkeypatch: pytest.MonkeyPatch) -> List[Dict[str, Any]]:
    seen: List[Dict[str, Any]] = []

    def fake_start_run(self, run_id, steps, app_target, options=None):  # noqa: ANN001
        seen.append({"steps": steps, "options": options})

    monkeypatch.setattr(RunManager, "start_run", fake_start_run)
    return seen


def test_a_default_run_request_passes_default_options(api, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _app, pack, target = api
    seen = _capture_start_run(monkeypatch)

    response = client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]})

    assert response.status_code == 202
    options = seen[0]["options"]
    assert (options.watch, options.continuous, options.slow_mo_ms) == (False, False, DEFAULT_WATCH_SLOW_MO_MS)


def test_watch_and_continuous_reach_the_run_manager_with_case_grouping(api, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _app, pack, target = api
    first = _add_case(client, pack["id"], "First")
    second = _add_case(client, pack["id"], "Second")
    _add_case(client, pack["id"], "Disabled", enabled=False)
    seen = _capture_start_run(monkeypatch)

    response = client.post(
        f"/api/validation-packs/{pack['id']}/run",
        json={"app_target_id": target["id"], "watch": True, "slow_mo_ms": 0, "continuous": True},
    )

    assert response.status_code == 202
    options, steps = seen[0]["options"], seen[0]["steps"]
    assert (options.watch, options.continuous, options.slow_mo_ms) == (True, True, 0)  # an explicit 0 is respected
    assert len(options.case_ids) == len(steps) == 4  # the disabled case contributes no steps
    assert sorted(set(options.case_ids)) == sorted([first, second])
    assert options.case_ids[0] == options.case_ids[1] != options.case_ids[2] == options.case_ids[3]


@pytest.mark.parametrize("extra", [{"watch": True}, {"continuous": True}, {"slow_mo_ms": 100}])
def test_manual_runs_reject_the_automated_only_options(api, extra: Dict[str, Any]) -> None:
    client, _app, pack, target = api

    response = client.post(
        f"/api/validation-packs/{pack['id']}/runs",
        json={"app_target_id": target["id"], "execution_mode": "manual", **extra},
    )

    assert response.status_code == 400
    assert "automated runs only" in response.json()["detail"]


def test_out_of_range_slow_motion_is_rejected_by_the_api(api) -> None:
    client, _app, pack, target = api

    response = client.post(
        f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"], "slow_mo_ms": 99999}
    )

    assert response.status_code == 422


# ── a real browser ───────────────────────────────────────────────────────────

import http.server  # noqa: E402
import socketserver  # noqa: E402

PAGE = b"""<!doctype html><title>Greeter</title>
<input id="name"><button id="go" onclick="document.getElementById('greeting').textContent='Hello, '+document.getElementById('name').value">Go</button>
<p id="greeting"></p>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_args: Any) -> None:
        pass


@pytest.fixture(scope="module")
def greeter_url():
    pytest.importorskip("playwright")
    probe = PlaywrightEngine(config={"headless": True})
    if not probe.launch():
        pytest.skip("Chromium is not available in this environment")
    probe.close()

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


GREETING_FLOW = [
    {"step_id": "go", "action_type": "navigate", "target": "/", "description": "open", "timeout_seconds": 10},
    {"step_id": "type", "action_type": "type", "target": "#name", "value": "Aman", "input_value": "Aman",
     "description": "type name", "timeout_seconds": 10},
    {"step_id": "click", "action_type": "click", "target": "#go", "description": "press Go", "timeout_seconds": 10},
    {"step_id": "assert", "action_type": "assert_text_contains", "target": "#greeting", "value": "Hello, Aman",
     "input_value": "Hello, Aman", "description": "greeting shows the typed name", "timeout_seconds": 10},
]


def _run_for_real(tmp_path: Path, url: str, options: RunOptions) -> Dict[str, Any]:
    storage = ProductStorage(str(tmp_path / "real.db"))
    run = LiveRunRecord(pack_id="p", app_target_id="a")
    storage.create_run(run.model_dump())
    run_manager = RunManager(event_stream=MagicMock(), storage=storage)
    run_manager._publish_event = MagicMock()
    run_manager._ingest_memory = MagicMock()

    run_manager._execute(run.id, GREETING_FLOW, {"base_url": url}, threading.Event(), options)

    row = storage.get_run(run.id)
    return {"status": row["status"], "steps": [r["status"] for r in sorted(row["step_results"], key=lambda r: r["step"])]}


def test_a_multi_step_flow_fails_when_every_step_starts_clean(tmp_path: Path, greeter_url: str) -> None:
    """The original behaviour: the typed name is gone by the time the assertion runs."""
    result = _run_for_real(tmp_path, greeter_url, RunOptions())

    assert result["status"] == "failed"
    assert result["steps"][-1] == "failed"


def test_a_multi_step_flow_passes_when_the_session_continues(tmp_path: Path, greeter_url: str) -> None:
    result = _run_for_real(tmp_path, greeter_url, RunOptions(continuous=True, case_ids=("greeting",) * 4))

    assert result == {"status": "completed", "steps": ["passed"] * 4}


def test_continuity_never_crosses_a_test_case_boundary(tmp_path: Path, greeter_url: str) -> None:
    """The assertion is the first step of a different case, so it starts clean and must fail."""
    result = _run_for_real(
        tmp_path, greeter_url, RunOptions(continuous=True, case_ids=("a", "a", "a", "b"))
    )

    assert result["status"] == "failed"
    assert result["steps"] == ["passed", "passed", "passed", "failed"]
