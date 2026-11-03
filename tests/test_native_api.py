"""Desktop/mobile app testing through the product API: readiness, permission, consent, and running app steps."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from native_fakes import PNG
from qa_ai.native_execution import (
    GRANTED,
    MISSING,
    AppSpec,
    ElementNotFound,
    NativeEngine,
    Requirement,
    UIElement,
)
from qa_ai.product_backend.server import create_product_app

ALL_ANDROID = ["start_emulator", "launch_apps", "control_input", "screenshots"]


class FakeDevice(NativeEngine):
    """A fake phone: a screen with a login form that greets the user after Sign in."""

    platform = "android"
    instances: List["FakeDevice"] = []

    def __init__(self, platform: str, missing: Optional[List[str]] = None) -> None:
        super().__init__()
        self.platform = platform
        self._missing = missing or []
        self.started_with: Optional[AppSpec] = None
        self.typed = ""
        self.signed_in = False
        self.stopped = False
        self.requested: List[str] = []
        FakeDevice.instances.append(self)

    def requirements(self) -> List[Requirement]:
        return [
            Requirement(rid, rid.title(), MISSING if rid in self._missing else GRANTED, f"install {rid}", can_request=True)
            for rid in ("adb", "device")
        ]

    def request(self, requirement_id: str) -> bool:
        self.requested.append(requirement_id)
        return True

    def start(self, app: AppSpec, timeout: float = 120.0) -> None:
        self.started_with = app

    def elements(self) -> List[UIElement]:
        items = [UIElement(label="Email", x=10, y=10), UIElement(text="Sign in", x=20, y=20)]
        if self.signed_in:
            items.append(UIElement(text=f"Welcome {self.typed}", x=30, y=30))
        return items

    def tap_element(self, element: UIElement) -> None:
        if element.text == "Sign in":
            self.signed_in = True

    def type_text(self, text: str) -> None:
        self.typed += text

    def press(self, key: str) -> None:
        pass

    def screenshot(self) -> Optional[bytes]:
        return PNG

    def stop(self) -> None:
        self.stopped = True

    def wait_for_text(self, text: str, timeout: float = 10.0, poll: float = 0.5) -> bool:
        return any(text.lower() in t.lower() for t in self.visible_text())

    def find(self, label: str, timeout: float = 10.0, poll: float = 0.5) -> UIElement:
        from qa_ai.native_execution import match_element

        found = match_element(self.elements(), label)
        if found is None:
            raise ElementNotFound(f"No element labelled {label!r}.")
        return found


@pytest.fixture
def api(tmp_path: Path):
    FakeDevice.instances = []
    settings: Dict[str, Any] = {"missing": []}

    def factory(platform: str) -> FakeDevice:
        return FakeDevice(platform, settings["missing"])

    app = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(tmp_path / "n.db"))
    with TestClient(app) as client:
        client.app.state.native_engine_factory = factory
        client.app.state.run_manager._native_engine_factory = factory
        yield client, settings


def _pack(client: TestClient, app_type: str = "android", steps: Optional[List[Dict[str, Any]]] = None):
    project = client.post("/api/projects", json={"name": "P", "description": ""}).json()
    target = client.post("/api/apps", json={
        "name": "Phone app", "app_type": app_type, "project_id": project["id"],
        "app_identifier": "com.example.app", "device_name": "Pixel_8",
    }).json()
    pack = client.post("/api/validation-packs", json={
        "project_id": project["id"], "app_id": target["id"], "name": "Login", "description": "",
    }).json()
    case = client.post(f"/api/validation-packs/{pack['id']}/test-cases", json={"title": "Login", "enabled": True, "steps": []}).json()
    for step in steps or [
        {"action_type": "app_launch"},
        {"action_type": "app_type", "target": "Email", "value": "Aman"},
        {"action_type": "app_tap", "target": "Sign in"},
        {"action_type": "app_assert_text", "value": "Welcome Aman"},
    ]:
        response = client.post(f"/api/test-cases/{case['test_case_id']}/steps", json={**step, "timeout_ms": 2000})
        assert response.status_code == 201, response.text
    return target, pack


def _allow(client: TestClient, platform: str = "android", unattended: bool = False) -> None:
    scopes = [s["id"] for s in client.get(f"/api/native/{platform}/readiness").json()["consent_scopes"]]
    assert client.put(f"/api/native/{platform}/consent", json={"scopes": scopes, "unattended": unattended}).status_code == 200


def _wait(client: TestClient, run_id: str) -> Dict[str, Any]:
    deadline = time.time() + 15
    while time.time() < deadline:
        row = client.get(f"/api/runs/{run_id}").json()
        if row["status"] in ("completed", "failed", "cancelled"):
            return row
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def _statuses(row: Dict[str, Any]) -> List[str]:
    return [r["status"] for r in sorted(row["step_results"], key=lambda r: r["step"])]


# ── app targets ──────────────────────────────────────────────────────────────

def test_a_native_app_target_keeps_its_identifier_path_and_device(api) -> None:
    client, _ = api
    target, _ = _pack(client)

    fetched = client.get(f"/api/apps/{target['id']}").json()

    assert (fetched["app_type"], fetched["app_identifier"], fetched["device_name"]) == ("android", "com.example.app", "Pixel_8")
    updated = client.patch(f"/api/apps/{target['id']}", json={"app_path": "/builds/app.apk"}).json()
    assert updated["app_path"] == "/builds/app.apk"


# ── readiness and permission ─────────────────────────────────────────────────

@pytest.mark.parametrize("platform", ["native_macos", "native_windows", "android", "ios"])
def test_every_platform_lists_what_the_user_is_asked_to_allow(api, platform: str) -> None:
    client, _ = api

    body = client.get(f"/api/native/{platform}/readiness").json()

    assert body["platform"] == platform
    assert {"launch_apps", "control_input", "screenshots"} <= {s["id"] for s in body["consent_scopes"]}
    assert body["consent"] is None and body["ready"] is False


def test_an_unknown_platform_is_a_404(api) -> None:
    client, _ = api

    assert client.get("/api/native/playstation/readiness").status_code == 404


def test_readiness_reports_missing_tools(api) -> None:
    client, settings = api
    settings["missing"] = ["adb"]

    body = client.get("/api/native/android/readiness").json()

    assert body["tools_ready"] is False
    assert next(r for r in body["requirements"] if r["id"] == "adb")["status"] == "missing"


def test_asking_the_os_for_a_permission_goes_through_the_engine(api) -> None:
    client, _ = api

    response = client.post("/api/native/android/permissions/adb/request")

    assert response.status_code == 200 and response.json()["requested"] is True
    assert FakeDevice.instances[0].requested == ["adb"]


def test_consent_must_cover_everything_listed(api) -> None:
    client, _ = api

    partial = client.put("/api/native/android/consent", json={"scopes": ["launch_apps"]})
    unknown = client.put("/api/native/android/consent", json={"scopes": ALL_ANDROID + ["read_contacts"]})

    assert partial.status_code == 400 and "control_input" in partial.json()["detail"]
    assert unknown.status_code == 400
    assert client.get("/api/native/android/readiness").json()["consent"] is None


def test_consent_is_saved_and_can_be_taken_back(api) -> None:
    client, _ = api
    _allow(client)

    body = client.get("/api/native/android/readiness").json()
    assert body["ready"] is True and set(body["consent"]["scopes"]) == set(ALL_ANDROID)
    assert body["consent"]["unattended"] is False

    assert client.delete("/api/native/android/consent").status_code == 204
    assert client.get("/api/native/android/readiness").json()["consent"] is None


def test_consent_for_one_platform_does_not_cover_another(api) -> None:
    client, _ = api
    _allow(client, "android")

    assert client.get("/api/native/ios/readiness").json()["consent"] is None


# ── starting runs ────────────────────────────────────────────────────────────

def test_a_run_with_app_steps_is_refused_until_the_user_allows_it(api) -> None:
    client, _ = api
    target, pack = _pack(client)

    response = client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "native_permission_required"
    assert response.json()["detail"]["platform"] == "android"
    assert FakeDevice.instances == []  # nothing was driven


def test_app_steps_against_a_website_target_are_a_400(api) -> None:
    client, _ = api
    project = client.post("/api/projects", json={"name": "P", "description": ""}).json()
    web = client.post("/api/apps", json={"name": "Site", "app_type": "web", "project_id": project["id"], "base_url": "http://127.0.0.1:1/"}).json()
    _, pack = _pack(client)

    response = client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": web["id"]})

    assert response.status_code == 400


def test_once_allowed_the_app_is_driven_step_by_step_with_screenshots(api) -> None:
    client, _ = api
    target, pack = _pack(client)
    _allow(client)

    run = client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]}).json()
    row = _wait(client, run["id"])

    assert row["status"] == "completed", row
    assert _statuses(row) == ["passed"] * 4
    assert all(r["evidence_ids"] for r in row["step_results"])  # a screenshot for every step
    assert all(r["provenance"] == "REAL_EXECUTION" for r in row["step_results"])
    device = FakeDevice.instances[-1]
    assert device.started_with.identifier == "com.example.app" and device.started_with.device == "Pixel_8"
    assert device.started_with.headless is True  # emulators run in the background unless watching
    assert device.stopped


def test_watching_shows_the_emulator(api) -> None:
    client, _ = api
    target, pack = _pack(client)
    _allow(client)

    run = client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"], "watch": True}).json()
    _wait(client, run["id"])

    assert FakeDevice.instances[-1].started_with.headless is False


def test_text_that_never_appears_fails_and_says_what_was_on_screen(api) -> None:
    client, _ = api
    target, pack = _pack(client, steps=[{"action_type": "app_launch"}, {"action_type": "app_assert_text", "value": "Order placed"}])
    _allow(client)

    row = _wait(client, client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]}).json()["id"])

    assert _statuses(row) == ["passed", "failed"]
    note = row["step_results"][1]["notes"]
    assert "Order placed" in note and "Sign in" in note


def test_tapping_something_that_is_not_there_fails_the_step(api) -> None:
    client, _ = api
    target, pack = _pack(client, steps=[{"action_type": "app_launch"}, {"action_type": "app_tap", "target": "Checkout"}])
    _allow(client)

    row = _wait(client, client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]}).json()["id"])

    assert _statuses(row) == ["passed", "failed"]
    assert "Checkout" in row["step_results"][1]["notes"]


def test_missing_tools_turn_into_a_capability_gap_not_a_fake_pass(api) -> None:
    client, settings = api
    settings["missing"] = ["adb"]
    target, pack = _pack(client)
    _allow(client)

    row = _wait(client, client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]}).json()["id"])

    assert row["status"] == "failed"
    assert set(_statuses(row)) == {"capability_gap"}
    assert "install adb" in row["step_results"][0]["notes"]
    assert FakeDevice.instances[-1].started_with is None  # the app was never started


def test_typed_text_is_not_written_into_the_step_notes(api) -> None:
    client, _ = api
    target, pack = _pack(client, steps=[{"action_type": "app_launch"}, {"action_type": "app_type", "target": "Email", "value": "hunter2-secret"}])
    _allow(client)

    row = _wait(client, client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]}).json()["id"])

    assert "hunter2-secret" not in str(row["step_results"])


# ── scheduled (unattended) runs ──────────────────────────────────────────────

def test_a_scheduled_run_does_not_drive_apps_without_unattended_permission(api) -> None:
    client, _ = api
    target, pack = _pack(client)
    _allow(client, unattended=False)

    run_id = client.app.state.run_manager.schedule_run(pack["id"])
    row = _wait(client, run_id)

    assert set(_statuses(row)) == {"capability_gap"}
    assert "unattended" in row["step_results"][0]["notes"]
    assert all(d.started_with is None for d in FakeDevice.instances)


def test_a_scheduled_run_drives_apps_when_unattended_runs_were_allowed(api) -> None:
    client, _ = api
    target, pack = _pack(client)
    _allow(client, unattended=True)

    row = _wait(client, client.app.state.run_manager.schedule_run(pack["id"]))

    assert _statuses(row) == ["passed"] * 4
    assert FakeDevice.instances[-1].started_with.headless is True
