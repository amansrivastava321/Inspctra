"""
Shared pieces of the native (desktop and mobile) engines.

Every engine drives one real app on one platform through the platform's own automation tools:

    native_macos   - macOS Accessibility (System Events, via osascript), screencapture
    native_windows - Windows UI Automation (pywinauto), Pillow for screenshots
    android        - adb against a connected device or an Android emulator it can start
    ios            - xcrun simctl for the iOS Simulator, idb for taps, typing and the screen's contents

Nothing here fakes support: when a tool or an OS permission is missing, `requirements()` says exactly what and
how to fix it, and the run reports a capability gap instead of pretending a step passed.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

GRANTED = "granted"
MISSING = "missing"
UNKNOWN = "unknown"


class NativeEngineError(RuntimeError):
    """The platform tool failed; the message is safe to show to the user."""


class ElementNotFound(NativeEngineError):
    """No element with that label is on screen."""


@dataclass
class Requirement:
    """One thing a platform needs before Inspectra can drive apps on it."""

    id: str
    label: str
    status: str  # granted | missing | unknown
    how_to_fix: str = ""
    # True when Inspectra can ask the OS for it directly (shows the system prompt or opens the right settings page).
    can_request: bool = False
    # Only needed for some runs (for example the emulator when a device is already connected).
    optional: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "status": self.status, "how_to_fix": self.how_to_fix,
            "can_request": self.can_request, "optional": self.optional,
        }


@dataclass
class AppSpec:
    """What to launch. Which fields matter depends on the platform."""

    identifier: str = ""            # bundle id / package name / app name / executable
    app_path: str = ""              # .app / .apk / .exe to install or open (optional)
    device: str = ""                # AVD name, simulator name or UDID (mobile); window title (Windows)
    headless: bool = False          # emulators/simulators: run without a window (background)


@dataclass
class UIElement:
    """One element on screen, with its centre in the platform's tap coordinates."""

    label: str = ""
    text: str = ""
    identifier: str = ""
    role: str = ""
    x: Optional[float] = None
    y: Optional[float] = None
    extra: dict = field(default_factory=dict)

    def names(self) -> List[str]:
        return [n for n in (self.label, self.text, self.identifier) if n]


class CommandResult:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def out(self) -> str:
        return self.stdout.decode("utf-8", "replace")

    @property
    def err(self) -> str:
        return self.stderr.decode("utf-8", "replace")

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CommandRunner:
    """Runs platform tools without a shell. Tests replace it with a fake."""

    def which(self, name: str) -> Optional[str]:
        return shutil.which(name)

    def run(self, args: Sequence[str], timeout: float = 60.0) -> CommandResult:
        try:
            done = subprocess.run(list(args), capture_output=True, timeout=timeout, check=False)
        except FileNotFoundError as exc:
            raise NativeEngineError(f"{args[0]} is not installed.") from exc
        except subprocess.TimeoutExpired as exc:
            raise NativeEngineError(f"{_tool(args)} did not finish within {int(timeout)} s.") from exc
        return CommandResult(done.returncode, done.stdout or b"", done.stderr or b"")

    def spawn(self, args: Sequence[str]) -> "subprocess.Popen[bytes]":
        """Start a long-running tool (an emulator) in the background."""
        return subprocess.Popen(list(args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> float:
        return time.monotonic()


def _tool(args: Sequence[str]) -> str:
    return str(args[0]).rsplit("/", 1)[-1] if args else "tool"


def match_element(elements: Sequence[UIElement], label: str) -> Optional[UIElement]:
    """Exact label/text/id first, then case-insensitive, then 'contains'. Elements without coordinates are skipped."""
    wanted = (label or "").strip()
    if not wanted:
        return None
    usable = [e for e in elements if e.x is not None and e.y is not None]
    lowered = wanted.lower()
    for test in (
        lambda n: n == wanted,
        lambda n: n.lower() == lowered,
        lambda n: n.split("/")[-1] == wanted or n.split(":id/")[-1] == wanted,  # Android resource ids
        lambda n: lowered in n.lower(),
    ):
        for element in usable:
            if any(test(n) for n in element.names()):
                return element
    return None


class NativeEngine(ABC):
    """One running app on one platform."""

    platform: str = ""

    def __init__(self, runner: Optional[CommandRunner] = None) -> None:
        self.runner = runner or CommandRunner()

    # ── readiness ───────────────────────────────────────────────────────────
    @abstractmethod
    def requirements(self) -> List[Requirement]:
        """Everything this platform needs, each marked granted / missing / unknown."""

    def request(self, requirement_id: str) -> bool:
        """Ask the OS for a permission (shows its prompt or opens its settings). False if not possible."""
        return False

    def missing(self) -> List[Requirement]:
        return [r for r in self.requirements() if r.status == MISSING and not r.optional]

    # ── app control ─────────────────────────────────────────────────────────
    @abstractmethod
    def start(self, app: AppSpec, timeout: float = 120.0) -> None:
        """Boot the device if needed, install if asked, launch the app and bring it to the front."""

    @abstractmethod
    def elements(self) -> List[UIElement]:
        """What is on screen right now."""

    @abstractmethod
    def tap_element(self, element: UIElement) -> None:
        """Click / tap an element found by `elements()`."""

    @abstractmethod
    def type_text(self, text: str) -> None:
        """Type into whatever has focus."""

    @abstractmethod
    def press(self, key: str) -> None:
        """Press a named key: enter, tab, escape, backspace, back, home, space, up, down, left, right."""

    @abstractmethod
    def screenshot(self) -> Optional[bytes]:
        """A PNG of the screen, or None when the platform will not give one."""

    @abstractmethod
    def stop(self) -> None:
        """Close what this engine started (the app, and an emulator it booted)."""

    # ── shared behaviour built on the primitives ─────────────────────────────
    def visible_text(self) -> List[str]:
        out: List[str] = []
        for element in self.elements():
            for value in (element.label, element.text):
                if value and value not in out:
                    out.append(value)
        return out

    def find(self, label: str, timeout: float = 10.0, poll: float = 0.5) -> UIElement:
        deadline = self.runner.now() + max(0.0, timeout)
        while True:
            found = match_element(self.elements(), label)
            if found is not None:
                return found
            if self.runner.now() >= deadline:
                raise ElementNotFound(f"No element labelled {label!r} appeared within {timeout:g} s.")
            self.runner.sleep(poll)

    def tap(self, label: str, timeout: float = 10.0) -> UIElement:
        element = self.find(label, timeout)
        self.tap_element(element)
        return element

    def wait_for_text(self, text: str, timeout: float = 10.0, poll: float = 0.5) -> bool:
        wanted = (text or "").strip().lower()
        deadline = self.runner.now() + max(0.0, timeout)
        while True:
            if any(wanted in t.lower() for t in self.visible_text()):
                return True
            if self.runner.now() >= deadline:
                return False
            self.runner.sleep(poll)


Clock = Callable[[], float]
