"""
step_narrator.py - Produce Codex-style live guided output for each step.

Prints structured live commentary:
  - What Inspectra sees
  - What it plans to do and why
  - What permission is needed
  - What action was taken
  - What evidence was checked and found
  - Step verdict with confidence

No secrets in output. Redacts known secret patterns.
"""
from __future__ import annotations

import re
import sys
from typing import List, Optional

from qa_ai.interactive_runtime.schemas import (
    AIVerdict,
    GuidedStep,
    GroundedVerdict,
)

_SECRET_PATTERNS = [
    re.compile(r"sk-or-[\w\-]+", re.I),
    re.compile(r"Bearer [\w\-\.]+", re.I),
    re.compile(r"eyJ[\w\-\.]+"),  # JWT tokens
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),  # long base64 (potential key)
]

_VERDICT_COLORS = {
    AIVerdict.PASS: "\033[92m",    # green
    AIVerdict.FAIL: "\033[91m",    # red
    AIVerdict.UNCLEAR: "\033[93m", # yellow
}
_RESET = "\033[0m"


def _redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def _strip_ansi(text: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", text)


class StepNarrator:
    """
    Emit structured live narrative for each test step.

    Can write to stdout or any file-like object.
    ANSI color is used when writing to a TTY.
    """

    def __init__(self, silent: bool = False, use_color: Optional[bool] = None):
        self._silent = silent
        self._use_color = use_color if use_color is not None else sys.stdout.isatty()

    def narrate(self, step: GuidedStep) -> str:
        """
        Produce and optionally print narrative for a step.

        Returns the narrative string (always, even if silent=True).
        """
        lines = self._build_lines(step)
        text = "\n".join(lines)
        if not self._silent:
            print(text, flush=True)
        return text

    def narrate_start(self, step_number: int, screen_title: str, plan: str) -> None:
        if self._silent:
            return
        self._print(f"\n{'─' * 60}")
        self._print(f"[STEP {step_number:03d}] Screen: {_redact(screen_title)}")
        self._print(f"  Plan : {_redact(plan)}")

    def narrate_action(self, action_taken: str, permission_needed: str) -> None:
        if self._silent:
            return
        if permission_needed:
            self._print(f"  Perm : {permission_needed}")
        self._print(f"  Act  : {_redact(action_taken)}")

    def narrate_evidence(self, evidence_checked: List[str], evidence_found: List[str]) -> None:
        if self._silent:
            return
        if evidence_checked:
            self._print("  Checking evidence:")
            for item in evidence_checked:
                self._print(f"    • {_redact(item)}")
        if evidence_found:
            self._print("  Found:")
            for item in evidence_found:
                self._print(f"    ✓ {_redact(item)}")

    def narrate_verdict(
        self,
        verdict: AIVerdict,
        confidence_pct: float,
        screenshot_path: Optional[str] = None,
    ) -> None:
        if self._silent:
            return
        color = _VERDICT_COLORS.get(verdict, "")
        reset = _RESET if self._use_color else ""
        color = color if self._use_color else ""
        label = verdict.value.upper()
        self._print(f"  {color}Verdict: {label}  confidence {confidence_pct:.0f}%{reset}")
        if screenshot_path:
            self._print(f"  Screenshot: {screenshot_path}")

    def _build_lines(self, step: GuidedStep) -> List[str]:
        lines = [
            "",
            "─" * 60,
            f"[STEP {step.step_number:03d}] {_redact(step.screen_title)}",
        ]

        if step.what_inspectra_sees:
            lines.append(f"  Sees   : {_redact(step.what_inspectra_sees)}")

        if step.plan:
            lines.append(f"  Plan   : {_redact(step.plan)}")

        if step.why:
            lines.append(f"  Why    : {_redact(step.why)}")

        if step.permission_needed:
            lines.append(f"  Perm   : {step.permission_needed}")

        if step.action_taken:
            lines.append(f"  Action : {_redact(step.action_taken)}")

        if step.evidence_checked:
            lines.append("  Checking:")
            for ev in step.evidence_checked[:5]:
                lines.append(f"    • {_redact(ev)}")

        if step.log_matches:
            for match in step.log_matches[:5]:
                lines.append(f"    ✓ Log: {_redact(match[:80])}")

        if step.db_check_result:
            lines.append(f"    ✓ DB : {_redact(step.db_check_result[:80])}")

        if step.backend_check_result:
            lines.append(f"    ✓ API: {_redact(step.backend_check_result[:80])}")

        if step.screenshot_after:
            lines.append(f"  Screenshot: {step.screenshot_after}")

        # Verdict line
        verdict_label = step.final_verdict.value.upper()
        lines.append(f"  Verdict: {verdict_label}  confidence {step.confidence_pct:.0f}%")

        return lines

    def _print(self, text: str) -> None:
        print(text, flush=True)
