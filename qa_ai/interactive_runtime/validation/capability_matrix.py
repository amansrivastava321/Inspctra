"""
capability_matrix.py - Platform/feature capability matrix for Phase 2 validation.

Rows: platform/driver types
Columns: supported | tested | passed | partial | capability_gap | setup_required | notes

Output: phase2_capability_matrix.json and phase2_capability_matrix.md
"""
from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.validation.validation_result import (
    TargetValidationStatus,
    ValidationResult,
)

_ROWS = [
    "web",
    "flutter_web",
    "native_macos",
    "flutter_macos",
    "native_windows",
    "flutter_windows",
    "native_linux",
    "flutter_linux",
    "android",
    "ios",
    "vision_fallback",
    "screenshots",
    "live_guided",
    "ai_guided",
    "logs",
]

_STATIC_SUPPORT: Dict[str, Dict[str, Any]] = {
    "web": {"supported": True, "notes": "Playwright required"},
    "flutter_web": {"supported": True, "notes": "Playwright required"},
    "native_macos": {"supported": True, "notes": "macOS only; Accessibility permission required"},
    "flutter_macos": {"supported": True, "notes": "macOS only; Flutter accessibility tree may be weak"},
    "native_windows": {"supported": True, "notes": "Windows only; pywinauto required"},
    "flutter_windows": {"supported": True, "notes": "Windows only; pywinauto required"},
    "native_linux": {"supported": True, "notes": "Linux only; AT-SPI + xdotool required"},
    "flutter_linux": {"supported": True, "notes": "Linux only; AT-SPI required"},
    "android": {"supported": True, "notes": "Appium-Python-Client + server required; opt-in"},
    "ios": {"supported": True, "notes": "macOS + XCUITest + Appium required; opt-in"},
    "vision_fallback": {"supported": True, "notes": "Screenshot-only; all clicks require approval; local_ollama default"},
    "screenshots": {"supported": True, "notes": "Platform-native capture"},
    "live_guided": {"supported": True, "notes": "Step narrative + trace files"},
    "ai_guided": {"supported": True, "notes": "Local AI oracle; no cloud without approval"},
    "logs": {"supported": True, "notes": "Process stdout capture; secret redaction enabled"},
}


class CapabilityMatrix:
    """
    Build and write a capability matrix from dry-run results.
    """

    def __init__(self) -> None:
        self._rows: Dict[str, Dict[str, Any]] = {}
        for row in _ROWS:
            self._rows[row] = {
                **_STATIC_SUPPORT.get(row, {}),
                "tested": False,
                "passed": False,
                "partial": False,
                "capability_gap": False,
                "setup_required": False,
                "notes": _STATIC_SUPPORT.get(row, {}).get("notes", ""),
            }

    def ingest_results(self, results: List[ValidationResult]) -> None:
        """Update matrix from validation results."""
        for r in results:
            row_key = r.app_type.lower()
            if row_key not in self._rows:
                self._rows[row_key] = {
                    "supported": True,
                    "tested": False,
                    "passed": False,
                    "partial": False,
                    "capability_gap": False,
                    "setup_required": False,
                    "notes": "",
                }

            row = self._rows[row_key]
            row["tested"] = True

            status = r.status
            if status == TargetValidationStatus.LIVE_PASSED:
                row["passed"] = True
            elif status == TargetValidationStatus.LIVE_UNCLEAR:
                row["partial"] = True
            elif status == TargetValidationStatus.BLOCKED_CAPABILITY:
                row["capability_gap"] = True
            elif status == TargetValidationStatus.BLOCKED_PLATFORM:
                row["capability_gap"] = True
                row["notes"] = r.notes or row.get("notes", "")
            elif status == TargetValidationStatus.DRY_RUN_ONLY:
                row["partial"] = True

            if r.setup_instructions:
                row["setup_required"] = True

            # feature rows
            if r.dry_run_caps:
                caps = r.dry_run_caps
                if caps.get("can_screenshot"):
                    self._rows["screenshots"]["tested"] = True
                    self._rows["screenshots"]["passed"] = True

    def build(self) -> Dict[str, Any]:
        return {
            "platform": platform.system().lower(),
            "matrix": self._rows,
        }

    def write_json(self, path: str) -> None:
        data = self.build()
        Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def write_markdown(self, path: str) -> None:
        lines = ["# Phase 2 Capability Matrix\n"]
        lines.append(f"Platform: `{platform.system()}`\n")
        lines.append(
            "| Feature | Supported | Tested | Passed | Partial | Cap Gap | Setup Req | Notes |"
        )
        lines.append("|---|:---:|:---:|:---:|:---:|:---:|:---:|---|")

        def _bool(v: Any) -> str:
            if v is True:
                return "✅"
            if v is False:
                return "❌"
            return "—"

        for name, row in self._rows.items():
            lines.append(
                f"| {name} "
                f"| {_bool(row.get('supported'))} "
                f"| {_bool(row.get('tested'))} "
                f"| {_bool(row.get('passed'))} "
                f"| {_bool(row.get('partial'))} "
                f"| {_bool(row.get('capability_gap'))} "
                f"| {_bool(row.get('setup_required'))} "
                f"| {row.get('notes', '')} |"
            )

        Path(path).write_text("\n".join(lines), encoding="utf-8")
