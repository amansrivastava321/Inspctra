"""Real Mac (CI: INSPECTRA_NATIVE_E2E=macos on a macOS runner with Xcode): the Mac permission checks, a Mac app
when the runner grants Accessibility, and the iOS Simulator."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from _product import PNG_SIGNATURE, enabled, run_pack_on_device, save_artifact
from qa_ai.native_execution import AppSpec, ElementNotFound
from qa_ai.native_execution.ios import IOSSimulatorEngine
from qa_ai.native_execution.macos import MacOSEngine

pytestmark = pytest.mark.skipif(not enabled("macos"), reason="needs a real Mac (INSPECTRA_NATIVE_E2E=macos)")

IOS_SETTINGS = "com.apple.Preferences"


def test_the_mac_permission_checks_answer_on_a_real_mac() -> None:
    reqs = {r.id: r for r in MacOSEngine().requirements()}

    print({rid: r.status for rid, r in reqs.items()})
    assert set(reqs) == {"accessibility", "automation", "screen_recording"}
    assert all(r.status in ("granted", "missing", "unknown") for r in reqs.values())


def test_a_mac_app_is_driven_when_accessibility_is_allowed() -> None:
    engine = MacOSEngine()
    missing = [r.id for r in engine.missing()]
    if missing:
        pytest.skip(f"this Mac has not granted: {', '.join(missing)}")

    engine.start(AppSpec(identifier="com.apple.calculator"), timeout=60)
    try:
        elements = engine.elements()
        # Kept as an artifact: what macOS reports for Calculator's controls on this machine.
        save_artifact("macos-calculator-elements.json", json.dumps(
            [{"role": e.role, "label": e.label, "text": e.text, "id": e.identifier} for e in elements], indent=1,
        ).encode())
        save_artifact("macos-calculator-start.png", engine.screenshot() or b"")
        # Calculator's buttons are identified as Seven / Add / Two / Equals (seen on macOS 15 runners).
        for key in ("Seven", "Add", "Two", "Equals"):
            try:
                engine.tap(key, timeout=10)
            except ElementNotFound:
                seen = [(e.role, e.label, e.identifier) for e in engine.elements()][:80]
                raise AssertionError(f"{key!r} not found; Calculator reported: {seen}")
        assert engine.wait_for_text("9", timeout=10), engine.visible_text()
        save_artifact("macos-calculator.png", engine.screenshot() or b"")
    finally:
        engine.stop()


def test_the_ios_simulator_boots_launches_and_screenshots_settings() -> None:
    engine = IOSSimulatorEngine()
    reqs = {r.id: r.status for r in engine.requirements()}
    assert reqs["xcode"] == "granted" and reqs["simulator"] == "granted", reqs

    engine.start(AppSpec(identifier=IOS_SETTINGS, headless=True), timeout=600)
    try:
        shot = engine.screenshot()
        assert shot and shot.startswith(PNG_SIGNATURE)
        save_artifact("ios-settings.png", shot)
        if reqs.get("idb") == "granted":
            assert engine.wait_for_text("General", timeout=60), engine.visible_text()
            engine.tap("General", timeout=20)
            assert engine.wait_for_text("About", timeout=30), engine.visible_text()
            save_artifact("ios-general.png", engine.screenshot() or b"")
    finally:
        engine.stop()


@pytest.mark.skipif(not os.environ.get("INSPECTRA_IDB_READY"), reason="idb could not be installed on this runner")
def test_a_pack_runs_in_the_ios_simulator_through_the_product_api(tmp_path: Path) -> None:
    row = run_pack_on_device(
        tmp_path,
        {"app_type": "ios", "app_identifier": IOS_SETTINGS},
        [
            {"action_type": "app_launch", "timeout_ms": 300000},
            {"action_type": "app_assert_text", "value": "General", "timeout_ms": 60000},
            {"action_type": "app_tap", "target": "General", "timeout_ms": 20000},
            {"action_type": "app_assert_text", "value": "About", "timeout_ms": 30000},
        ],
        timeout=900,
    )

    results = sorted(row["step_results"], key=lambda r: r["step"])
    assert row["status"] == "completed", [(r["status"], r.get("notes")) for r in results]
