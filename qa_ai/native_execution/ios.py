"""iOS: the iOS Simulator through xcrun simctl (boot, install, launch, screenshot) and idb (screen contents, taps, typing)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional

from qa_ai.native_execution.base import (
    GRANTED,
    MISSING,
    AppSpec,
    CommandRunner,
    NativeEngine,
    NativeEngineError,
    Requirement,
    UIElement,
)

XCODE_HINT = "Install Xcode from the App Store, open it once, then run: sudo xcode-select -s /Applications/Xcode.app"
IDB_HINT = "Install idb: brew tap facebook/fb && brew install idb-companion, then pip install fb-idb"
# USB HID usage codes, which is what `idb ui key` takes.
_HID_KEYS = {
    "enter": 40, "return": 40, "escape": 41, "esc": 41, "backspace": 42, "delete": 42, "tab": 43, "space": 44,
    "right": 79, "left": 80, "down": 81, "up": 82,
}


def parse_simctl_devices(payload: str) -> List[Dict[str, Any]]:
    """Available simulators from `xcrun simctl list devices available -j`, iPhones first."""
    data = json.loads(payload or "{}")
    devices: List[Dict[str, Any]] = []
    for runtime, entries in (data.get("devices") or {}).items():
        if "iOS" not in runtime:
            continue
        for entry in entries:
            if entry.get("isAvailable", True):
                devices.append({**entry, "runtime": runtime})
    devices.sort(key=lambda d: (0 if d.get("state") == "Booted" else 1, 0 if "iPhone" in d.get("name", "") else 1))
    return devices


def parse_idb_elements(payload: str) -> List[UIElement]:
    """Elements from `idb ui describe-all --json` (one JSON array, or one object per line)."""
    text = (payload or "").strip()
    if not text:
        return []
    try:
        items = json.loads(text)
        if isinstance(items, dict):
            items = [items]
    except json.JSONDecodeError:
        items = [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]
    elements: List[UIElement] = []
    for item in items:
        frame = item.get("frame") or {}
        try:
            x = float(frame["x"]) + float(frame["width"]) / 2
            y = float(frame["y"]) + float(frame["height"]) / 2
        except (KeyError, TypeError, ValueError):
            x = y = None
        elements.append(UIElement(
            label=str(item.get("AXLabel") or ""),
            text=str(item.get("AXValue") or ""),
            identifier=str(item.get("AXUniqueId") or ""),
            role=str(item.get("type") or item.get("role") or ""),
            x=x, y=y,
        ))
    return elements


class IOSSimulatorEngine(NativeEngine):
    platform = "ios"

    def __init__(self, runner: Optional[CommandRunner] = None, platform_name: Optional[str] = None) -> None:
        super().__init__(runner)
        self._platform_name = platform_name or sys.platform
        self._udid: Optional[str] = None
        self._bundle = ""
        self._booted_here = False

    def _simulators(self) -> List[Dict[str, Any]]:
        result = self.runner.run(["xcrun", "simctl", "list", "devices", "available", "-j"], timeout=60)
        if not result.ok:
            raise NativeEngineError("xcrun simctl is not working. " + XCODE_HINT)
        return parse_simctl_devices(result.out)

    def requirements(self) -> List[Requirement]:
        if self._platform_name != "darwin":
            return [Requirement("macos", "A Mac (the iOS Simulator only runs on macOS)", MISSING,
                                "Run Inspectra on a Mac with Xcode to test iOS apps.")]
        reqs: List[Requirement] = []
        has_xcrun = bool(self.runner.which("xcrun"))
        sims: List[Dict[str, Any]] = []
        if has_xcrun:
            try:
                sims = self._simulators()
            except NativeEngineError:
                has_xcrun = False
        reqs.append(Requirement("xcode", "Xcode command-line tools", GRANTED if has_xcrun else MISSING,
                                "" if has_xcrun else XCODE_HINT))
        reqs.append(Requirement("simulator", "An iOS Simulator device", GRANTED if sims else MISSING,
                                "" if sims else "Open Xcode > Settings > Platforms and install an iOS simulator."))
        has_idb = bool(self.runner.which("idb"))
        reqs.append(Requirement("idb", "idb (taps, typing and reading the screen)", GRANTED if has_idb else MISSING,
                                "" if has_idb else IDB_HINT))
        return reqs

    def _idb(self, *args: str, timeout: float = 30.0):
        if not self.runner.which("idb"):
            raise NativeEngineError("idb is not installed. " + IDB_HINT)
        result = self.runner.run(["idb", *args, "--udid", str(self._udid)], timeout=timeout)
        if not result.ok:
            raise NativeEngineError(f"idb {args[0]} {args[1] if len(args) > 1 else ''} failed: {result.err.strip()[-200:]}")
        return result

    def start(self, app: AppSpec, timeout: float = 180.0) -> None:
        if self._platform_name != "darwin":
            raise NativeEngineError("iOS apps can only be tested on a Mac (the iOS Simulator needs macOS).")
        bundle = (app.identifier or "").strip()
        if not bundle:
            raise NativeEngineError("Set the app's bundle id (for example com.example.app) on the app target.")
        self._bundle = bundle
        sims = self._simulators()
        wanted = (app.device or "").strip()
        chosen = next((s for s in sims if wanted and wanted in (s.get("udid"), s.get("name"))), None)
        if chosen is None:
            if wanted:
                raise NativeEngineError(f"No simulator named {wanted!r}. Available: {', '.join(s['name'] for s in sims) or 'none'}.")
            if not sims:
                raise NativeEngineError("No iOS simulator is installed. Open Xcode > Settings > Platforms.")
            chosen = sims[0]
        self._udid = chosen["udid"]
        if chosen.get("state") != "Booted":
            booted = self.runner.run(["xcrun", "simctl", "boot", self._udid], timeout=120)
            if not booted.ok and "current state: Booted" not in booted.err:
                raise NativeEngineError(f"Could not boot the simulator: {booted.err.strip()[-200:]}")
            self._booted_here = True
        self.runner.run(["xcrun", "simctl", "bootstatus", self._udid, "-b"], timeout=timeout)
        if not app.headless:
            self.runner.run(["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", self._udid], timeout=30)
        if app.app_path:
            installed = self.runner.run(["xcrun", "simctl", "install", self._udid, app.app_path], timeout=300)
            if not installed.ok:
                raise NativeEngineError(f"Installing the app failed: {installed.err.strip()[-200:]}")
        launched = self.runner.run(["xcrun", "simctl", "launch", self._udid, bundle], timeout=60)
        if not launched.ok:
            raise NativeEngineError(f"Could not launch {bundle}: {launched.err.strip()[-200:]}")

    def elements(self) -> List[UIElement]:
        return parse_idb_elements(self._idb("ui", "describe-all", "--json").out)

    def tap_element(self, element: UIElement) -> None:
        self._idb("ui", "tap", str(int(round(element.x))), str(int(round(element.y))))

    def type_text(self, text: str) -> None:
        if text:
            self._idb("ui", "text", text)

    def press(self, key: str) -> None:
        name = (key or "").strip().lower()
        if name == "home":
            self._idb("ui", "button", "HOME")
            return
        code = _HID_KEYS.get(name)
        if code is None:
            raise NativeEngineError(f"Unknown key {key!r}. Use one of: home, {', '.join(sorted(_HID_KEYS))}.")
        self._idb("ui", "key", str(code))

    def screenshot(self) -> Optional[bytes]:
        if not self._udid:
            return None
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "screen.png")
            result = self.runner.run(["xcrun", "simctl", "io", self._udid, "screenshot", "--type=png", path], timeout=30)
            if not result.ok or not os.path.exists(path):
                return None
            with open(path, "rb") as fh:
                data = fh.read()
        return data if data.startswith(b"\x89PNG") else None

    def stop(self) -> None:
        if not self._udid:
            return
        try:
            if self._bundle:
                self.runner.run(["xcrun", "simctl", "terminate", self._udid, self._bundle], timeout=30)
            if self._booted_here:
                self.runner.run(["xcrun", "simctl", "shutdown", self._udid], timeout=60)
        except NativeEngineError:
            pass
        finally:
            self._booted_here = False
