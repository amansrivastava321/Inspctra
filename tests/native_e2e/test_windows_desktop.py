"""Real Windows desktop (CI: INSPECTRA_NATIVE_E2E=windows on a Windows runner)."""
from __future__ import annotations

from pathlib import Path

import pytest

from _product import PNG_SIGNATURE, enabled, run_pack_on_device, save_artifact
from qa_ai.native_execution import AppSpec
from qa_ai.native_execution.windows import WindowsEngine

pytestmark = pytest.mark.skipif(not enabled("windows"), reason="needs a real Windows desktop (INSPECTRA_NATIVE_E2E=windows)")


def test_the_engine_types_into_notepad() -> None:
    engine = WindowsEngine()
    assert engine.missing() == [], [r.to_dict() for r in engine.requirements()]

    engine.start(AppSpec(identifier="notepad.exe"), timeout=60)
    try:
        engine.type_text("Hello from Inspectra (1+1=2) 100%")
        assert engine.wait_for_text("Hello from Inspectra (1+1=2) 100%", timeout=15), engine.visible_text()
        shot = engine.screenshot()
        assert shot and shot.startswith(PNG_SIGNATURE)
        save_artifact("windows-notepad.png", shot)
    finally:
        engine.stop()


def test_a_pack_runs_on_windows_through_the_product_api(tmp_path: Path) -> None:
    row = run_pack_on_device(
        tmp_path,
        {"app_type": "native_windows", "app_identifier": "notepad.exe"},
        [
            {"action_type": "app_launch", "timeout_ms": 60000},
            {"action_type": "app_type", "value": "Typed by an Inspectra run", "timeout_ms": 15000},
            {"action_type": "app_assert_text", "value": "Typed by an Inspectra run", "timeout_ms": 15000},
            {"action_type": "app_assert_text", "value": "text that is not there", "timeout_ms": 3000, "optional": True},
        ],
    )

    results = sorted(row["step_results"], key=lambda r: r["step"])
    assert [r["status"] for r in results] == ["passed", "passed", "passed", "failed"], [r.get("notes") for r in results]
