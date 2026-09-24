"""
dependency_installer.py - Execute approved package installation actions.

Security rules:
- All subprocess calls use list form. No shell=True.
- Use sys.executable for pip — ensures correct venv.
- Package names validated against safe whitelist before install.
- No sudo.
- No silent global installs.
- Capture stdout/stderr; redact any secrets before logging.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time
from typing import List, Optional, Tuple

from qa_ai.interactive_runtime.setup.setup_models import (
    ActionStatus,
    ActionType,
    SetupAction,
    SetupActionResult,
)

logger = logging.getLogger(__name__)

# Allowlist of pip packages we will ever install
_SAFE_PACKAGES: set[str] = {
    "playwright",
    "Appium-Python-Client",
    "pywinauto",
    "pyatspi",
}

# Allowlist of Appium drivers we will ever install
_SAFE_APPIUM_DRIVERS: set[str] = {
    "uiautomator2",
    "xcuitest",
}

# Allowlist of npm global packages we will ever install
_SAFE_NPM_PACKAGES: set[str] = {
    "appium",
}


class DependencyInstaller:
    """
    Execute setup actions that install Python packages or run CLI tools.

    dry_run=True: simulate but do not execute.
    """

    def __init__(self, dry_run: bool = False) -> None:
        self._dry_run = dry_run

    def execute(self, action: SetupAction) -> SetupActionResult:
        """Execute one approved SetupAction. Returns result."""
        t0 = time.monotonic()

        if self._dry_run:
            return SetupActionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ActionStatus.SKIPPED,
                output=f"[DRY-RUN] Would run: {action.command}",
                duration_seconds=0.0,
            )

        if action.action_type == ActionType.INSTALL_PYTHON_PACKAGE:
            return self._run_pip_install(action, t0)
        if action.action_type == ActionType.RUN_PLAYWRIGHT_INSTALL:
            return self._run_playwright_install(action, t0)
        if action.action_type == ActionType.CREATE_VENV:
            return self._run_create_venv(action, t0)
        if action.action_type == ActionType.INSTALL_NPM_PACKAGE:
            return self._run_npm_install(action, t0)
        if action.action_type == ActionType.INSTALL_APPIUM_DRIVER:
            return self._run_appium_driver_install(action, t0)
        if action.action_type == ActionType.PULL_OLLAMA_MODEL:
            return self._run_ollama_pull(action, t0)
        if action.action_type in (ActionType.SHOW_MANUAL_STEPS, ActionType.CHECK_APPIUM_SERVER):
            return SetupActionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ActionStatus.SKIPPED,
                output="Manual step — no automated execution.",
                duration_seconds=0.0,
            )
        if action.action_type == ActionType.OPEN_SYSTEM_SETTINGS:
            return self._run_open_settings(action, t0)

        return SetupActionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ActionStatus.SKIPPED,
            output=f"No executor for action_type={action.action_type}",
            duration_seconds=time.monotonic() - t0,
        )

    def execute_all(
        self, actions: List[SetupAction]
    ) -> List[SetupActionResult]:
        return [self.execute(a) for a in actions]

    # ── internal executors ────────────────────────────────────────────────────

    def _run_pip_install(self, action: SetupAction, t0: float) -> SetupActionResult:
        if not action.command or len(action.command) < 5:
            return self._error_result(action, t0, "Invalid pip install command.")

        package = action.command[-1]  # last arg is the package name
        if package not in _SAFE_PACKAGES:
            return self._error_result(
                action, t0,
                f"Package '{package}' not in safe allowlist. Manual install required."
            )

        # command is already [sys.executable, "-m", "pip", "install", package]
        # but re-build to ensure sys.executable is current process
        cmd: List[str] = [sys.executable, "-m", "pip", "install", package]
        return self._run_subprocess(action, cmd, t0)

    def _run_playwright_install(self, action: SetupAction, t0: float) -> SetupActionResult:
        cmd: List[str] = [sys.executable, "-m", "playwright", "install", "chromium"]
        return self._run_subprocess(action, cmd, t0)

    def _run_create_venv(self, action: SetupAction, t0: float) -> SetupActionResult:
        if not action.command or len(action.command) < 4:
            return self._error_result(action, t0, "Invalid venv command.")
        venv_path = action.command[-1]
        # Validate: path must be a simple relative or absolute path, no shell metacharacters
        if any(c in venv_path for c in (";", "&", "|", "$", "`", " ")):
            return self._error_result(action, t0, "Unsafe venv path rejected.")
        cmd: List[str] = [sys.executable, "-m", "venv", venv_path]
        return self._run_subprocess(action, cmd, t0)

    def _run_open_settings(self, action: SetupAction, t0: float) -> SetupActionResult:
        if not action.command:
            return self._error_result(action, t0, "No command for open_system_settings.")
        # Only allow "open" on macOS with known safe URL schemes
        if action.command[0] != "open":
            return self._error_result(action, t0, "open_system_settings: only 'open' allowed.")
        url = action.command[-1] if len(action.command) > 1 else ""
        if not url.startswith("x-apple.systempreferences:"):
            return self._error_result(action, t0, f"Unsafe URL rejected: {url}")
        return self._run_subprocess(action, action.command, t0)

    def _run_npm_install(self, action: SetupAction, t0: float) -> SetupActionResult:
        """
        npm install -g <package> — global npm install.
        Only runs if explicitly approved (risk=HIGH, can_auto_run=False).
        Package must be in _SAFE_NPM_PACKAGES allowlist.
        No shell=True. No sudo.
        """
        if not action.command or len(action.command) < 4:
            return self._error_result(action, t0, "Invalid npm install command.")

        # Expected: ["npm", "install", "-g", "appium"]
        if action.command[0] != "npm":
            return self._error_result(action, t0, "npm install: command must start with 'npm'.")

        package = action.command[-1]
        if package not in _SAFE_NPM_PACKAGES:
            return self._error_result(
                action, t0,
                f"npm package '{package}' not in safe allowlist. Manual install required."
            )

        # Verify npm exists on PATH before attempting
        import shutil
        if not shutil.which("npm"):
            return self._error_result(action, t0, "npm not found on PATH. Install Node.js first.")

        cmd: List[str] = ["npm", "install", "-g", package]
        return self._run_subprocess(action, cmd, t0)

    def _run_appium_driver_install(self, action: SetupAction, t0: float) -> SetupActionResult:
        """
        appium driver install <driver> — install an Appium driver.
        Driver must be in _SAFE_APPIUM_DRIVERS allowlist.
        No shell=True.
        """
        if not action.command or len(action.command) < 4:
            return self._error_result(action, t0, "Invalid appium driver install command.")

        # Expected: ["appium", "driver", "install", "uiautomator2"]
        if action.command[0] != "appium":
            return self._error_result(action, t0, "appium driver install: must start with 'appium'.")

        driver_name = action.command[-1]
        if driver_name not in _SAFE_APPIUM_DRIVERS:
            return self._error_result(
                action, t0,
                f"Appium driver '{driver_name}' not in safe allowlist."
            )

        import shutil
        if not shutil.which("appium"):
            return self._error_result(action, t0, "appium command not found. Install Appium first.")

        cmd: List[str] = ["appium", "driver", "install", driver_name]
        return self._run_subprocess(action, cmd, t0, timeout=120)

    def _run_ollama_pull(self, action: SetupAction, t0: float) -> SetupActionResult:
        """
        ollama pull <model> — download a local AI model.
        Requires explicit approval (can_auto_run=False, risk=MEDIUM).
        Model name must be non-empty and not contain shell metacharacters.
        No shell=True.
        """
        if not action.command or len(action.command) < 3:
            return self._error_result(action, t0, "Invalid ollama pull command.")

        if action.command[0] != "ollama" or action.command[1] != "pull":
            return self._error_result(action, t0, "ollama pull: command must be ['ollama', 'pull', model].")

        model_name = action.command[2]
        # Validate model name: only alphanumeric, hyphens, dots, colons, underscores
        import re
        if not model_name or not re.match(r'^[a-zA-Z0-9:._/-]+$', model_name):
            return self._error_result(action, t0, f"Unsafe model name rejected: {model_name!r}")

        import shutil
        if not shutil.which("ollama"):
            return self._error_result(action, t0, "ollama command not found. Install Ollama first.")

        cmd: List[str] = ["ollama", "pull", model_name]
        # Models can be large — allow up to 30 min
        return self._run_subprocess(action, cmd, t0, timeout=1800)

    def _run_subprocess(
        self, action: SetupAction, cmd: List[str], t0: float, timeout: int = 300
    ) -> SetupActionResult:
        logger.info("Running: %s", cmd)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                # shell=False is the default — explicit for clarity
                shell=False,
            )
            dur = time.monotonic() - t0
            status = ActionStatus.COMPLETED if result.returncode == 0 else ActionStatus.FAILED
            output = _redact(result.stdout.strip())
            error = _redact(result.stderr.strip()) if result.returncode != 0 else None
            return SetupActionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=status,
                output=output[:2000],
                error=error[:2000] if error else None,
                duration_seconds=round(dur, 3),
            )
        except subprocess.TimeoutExpired:
            return self._error_result(action, t0, f"Command timed out after {timeout}s.")
        except Exception as exc:
            return self._error_result(action, t0, str(exc))

    def _error_result(
        self, action: SetupAction, t0: float, msg: str
    ) -> SetupActionResult:
        return SetupActionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ActionStatus.FAILED,
            error=msg,
            duration_seconds=round(time.monotonic() - t0, 3),
        )


def _redact(text: str) -> str:
    """Basic redaction of common secret patterns."""
    import re
    # Redact anything that looks like a token/key
    text = re.sub(r"(?i)(key|token|secret|password|api_key)\s*[=:]\s*\S+", r"\1=[REDACTED]", text)
    return text
