"""Real Android emulator (CI: INSPECTRA_NATIVE_E2E=android, with the emulator already running)."""
from __future__ import annotations

from pathlib import Path

import pytest

from _product import PNG_SIGNATURE, enabled, run_pack_on_device, save_artifact
from qa_ai.native_execution import AppSpec
from qa_ai.native_execution.android import AndroidEngine

pytestmark = pytest.mark.skipif(not enabled("android"), reason="needs a real Android emulator (INSPECTRA_NATIVE_E2E=android)")

SETTINGS = "com.android.settings"


def test_the_engine_drives_the_settings_app_on_a_real_emulator() -> None:
    engine = AndroidEngine()
    assert engine.missing() == [], [r.to_dict() for r in engine.requirements()]

    engine.start(AppSpec(identifier=SETTINGS), timeout=180)
    try:
        assert engine.wait_for_text("Network", timeout=60), engine.visible_text()
        save_artifact("android-1-settings.png", engine.screenshot() or b"")

        engine.tap("Search settings", timeout=20)
        engine.type_text("display")
        assert engine.wait_for_text("display", timeout=20), engine.visible_text()
        shot = engine.screenshot()
        assert shot and shot.startswith(PNG_SIGNATURE)
        save_artifact("android-2-typed-search.png", shot)

        engine.press("back")
        engine.press("back")
        assert engine.wait_for_text("Network", timeout=30), engine.visible_text()
    finally:
        engine.stop()


def test_a_pack_runs_on_the_emulator_through_the_product_api(tmp_path: Path) -> None:
    row = run_pack_on_device(
        tmp_path,
        {"app_type": "android", "app_identifier": SETTINGS},
        [
            {"action_type": "app_launch", "timeout_ms": 180000},
            {"action_type": "app_assert_text", "value": "Network", "timeout_ms": 60000},
            {"action_type": "app_tap", "target": "Search settings", "timeout_ms": 20000},
            {"action_type": "app_type", "value": "battery", "timeout_ms": 20000},
            {"action_type": "app_assert_text", "value": "battery", "timeout_ms": 20000},
            {"action_type": "app_press", "value": "back", "timeout_ms": 10000},
        ],
    )

    results = sorted(row["step_results"], key=lambda r: r["step"])
    assert row["status"] == "completed", [(r["status"], r.get("notes")) for r in results]
    assert all(r["evidence_ids"] for r in results), "every app step keeps a screenshot"
