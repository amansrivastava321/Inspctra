"""
setup_reporter.py - Generate artifacts from doctor/setup results.

Produces:
  artifacts/runtime_doctor_report.json
  artifacts/runtime_doctor_report.md
  artifacts/setup_plan.json
  artifacts/setup_actions.json
  artifacts/setup_execution_log.json
  artifacts/setup_readiness_after.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from qa_ai.interactive_runtime.setup.setup_models import (
    EnvironmentDoctorReport,
    SetupExecutionLog,
    SetupPlan,
)


class SetupReporter:
    """Write all doctor and setup artifacts."""

    def __init__(self, output_dir: str = "artifacts") -> None:
        self._out = Path(output_dir)
        self._out.mkdir(parents=True, exist_ok=True)

    def write_doctor_report(self, report: EnvironmentDoctorReport) -> None:
        self._write_json("runtime_doctor_report.json", report.model_dump())
        self._write_text("runtime_doctor_report.md", self._doctor_markdown(report))

    def write_setup_plan(self, plan: SetupPlan) -> None:
        self._write_json("setup_plan.json", plan.model_dump())
        actions_data = [a.model_dump() for a in plan.actions]
        self._write_json("setup_actions.json", actions_data)

    def write_execution_log(self, log: SetupExecutionLog) -> None:
        self._write_json("setup_execution_log.json", log.model_dump())

    def write_readiness_after(self, report: EnvironmentDoctorReport) -> None:
        self._write_json("setup_readiness_after.json", report.model_dump())

    def write_driver_requirements(self) -> None:
        """Write driver_requirements.json from the central registry."""
        from qa_ai.interactive_runtime.setup.driver_requirements import registry_to_dict
        self._write_json("driver_requirements.json", registry_to_dict())

    # ── markdown ──────────────────────────────────────────────────────────────

    def _doctor_markdown(self, r: EnvironmentDoctorReport) -> str:
        def tick(v: bool) -> str:
            return "✅" if v else "❌"

        lines = [
            "# Runtime Environment Doctor Report\n",
            f"Generated: {r.generated_at}  ",
            f"Platform: `{r.platform}`  ",
            f"Python: `{r.python_version}` at `{r.python_executable}`  ",
            f"Venv: {tick(r.venv_active)} {r.venv_path or '—'}\n",
            f"## Readiness Score: {r.readiness_score}/100 ({r.readiness_label.upper()})\n",
            "## Packages\n",
            f"| Package | Installed |",
            f"|---|:---:|",
            f"| playwright | {tick(r.playwright_installed)} |",
            f"| playwright browsers | {tick(r.playwright_browsers_installed)} |",
            f"| Appium-Python-Client | {tick(r.appium_client_installed)} |",
        ]

        if r.platform == "windows":
            lines.append(f"| pywinauto | {tick(r.pywinauto_installed)} |")
        if r.platform == "linux":
            lines.append(f"| pyatspi | {tick(r.atspi_installed)} |")

        lines += [
            "\n## OS Capabilities\n",
            f"| Capability | Status |",
            f"|---|:---:|",
        ]
        if r.platform == "macos":
            lines.append(f"| macOS Accessibility | {tick(r.macos_accessibility_granted)} |")
            lines.append(f"| screencapture | {tick(r.screencapture_available)} |")
        if r.platform == "linux":
            lines.append(f"| xdotool | {tick(r.xdotool_available)} |")
            lines.append(f"| scrot | {tick(r.scrot_available)} |")

        lines += [
            "\n## Appium Ecosystem\n",
            f"| Component | Status |",
            f"|---|:---:|",
            f"| npm | {tick(r.npm_available)} |",
            f"| appium command | {tick(r.appium_command_available)} |",
            f"| uiautomator2 driver | {tick(r.appium_uiautomator2_installed)} |",
            f"| xcuitest driver | {tick(r.appium_xcuitest_installed)} |",
            "\n## Services\n",
            f"| Service | Status |",
            f"|---|:---:|",
            f"| Appium server ({r.appium_server_url}) | {tick(r.appium_server_reachable)} |",
            f"| Ollama (localhost:11434) | {tick(r.ollama_reachable)} |",
        ]

        if r.ollama_models:
            lines.append(f"\nOllama models: {', '.join(r.ollama_models)}")
        if r.ollama_configured_model:
            lines.append(
                f"\nConfigured vision model: `{r.ollama_configured_model}` "
                f"{'✅ available' if r.ollama_vision_model_available else '❌ not found'}"
            )

        if r.driver_readiness:
            lines += ["\n## Driver Readiness\n", "| App Type | Driver | Status | Missing |",
                      "|---|---|:---:|---|"]
            for d in r.driver_readiness:
                status_icon = "✅" if d.status == "ready" else "❌"
                missing = ", ".join(d.missing_deps[:2]) or "—"
                lines.append(f"| {d.app_type} | {d.driver_type} | {status_icon} {d.status} | {missing} |")

        if r.missing_items:
            lines += ["\n## Missing Items\n"]
            for item in r.missing_items:
                lines.append(f"- ❌ {item}")

        if r.recommended_actions:
            lines += ["\n## Recommended Actions\n"]
            for action in r.recommended_actions:
                lines.append(f"- {action}")

        lines += [
            "\n---",
            "_Run `python -m qa_ai.cli runtime-doctor --auto-setup` to fix automatically._",
        ]
        return "\n".join(lines)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _write_json(self, filename: str, data: object) -> None:
        path = self._out / filename
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _write_text(self, filename: str, content: str) -> None:
        path = self._out / filename
        path.write_text(content, encoding="utf-8")
