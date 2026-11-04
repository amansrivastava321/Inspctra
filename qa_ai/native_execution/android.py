"""Android: drives a connected device or an Android emulator through adb (no Appium needed)."""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, List, Optional

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

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
_PACKAGE_RE = re.compile(r"^[A-Za-z][\w]*(\.[A-Za-z_][\w]*)+$")
_KEYCODES = {
    "enter": 66, "return": 66, "tab": 61, "escape": 111, "esc": 111, "backspace": 67, "delete": 67,
    "back": 4, "home": 3, "space": 62, "up": 19, "down": 20, "left": 21, "right": 22, "menu": 82,
}
# Characters the device shell would interpret; `input text` needs them escaped.
_SHELL_SPECIAL = set("\\'\"`$&|;<>()*?!#~[]{}")

SDK_HINT = (
    "Install Android Studio (or the command-line tools), then add <sdk>/platform-tools and <sdk>/emulator "
    "to PATH, or set ANDROID_HOME."
)


def parse_bounds(bounds: str) -> Optional[tuple]:
    m = _BOUNDS_RE.match(bounds or "")
    if not m:
        return None
    x1, y1, x2, y2 = (int(v) for v in m.groups())
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1 + x2) / 2, (y1 + y2) / 2


def parse_ui_dump(xml_text: str) -> List[UIElement]:
    """Elements from `uiautomator dump` output (anything after the closing tag is ignored)."""
    start, end = xml_text.find("<?xml"), xml_text.rfind("</hierarchy>")
    if start == -1:
        start = xml_text.find("<hierarchy")
    if start == -1 or end == -1:
        raise NativeEngineError("The device did not return its screen contents (uiautomator dump failed).")
    root = ET.fromstring(xml_text[start:end + len("</hierarchy>")])
    elements: List[UIElement] = []
    for node in root.iter("node"):
        centre = parse_bounds(node.get("bounds", ""))
        elements.append(UIElement(
            label=node.get("content-desc", "") or "",
            text=node.get("text", "") or "",
            identifier=node.get("resource-id", "") or "",
            role=node.get("class", "") or "",
            x=centre[0] if centre else None,
            y=centre[1] if centre else None,
            extra={
                "clickable": node.get("clickable") == "true",
                "focused": node.get("focused") == "true",
                "editable": "EditText" in (node.get("class") or ""),
                "package": node.get("package", ""),
            },
        ))
    return elements


def escape_input_text(text: str) -> str:
    """Text for `adb shell input text`: spaces become %s and shell characters are escaped."""
    out = []
    for ch in text:
        if ch == " ":
            out.append("%s")
        elif ch in _SHELL_SPECIAL:
            out.append("\\" + ch)
        elif ch in "\n\r\t":
            raise NativeEngineError("Use a separate 'press' step for Enter or Tab instead of typing them.")
        else:
            out.append(ch)
    return "".join(out)


class AndroidEngine(NativeEngine):
    platform = "android"

    def __init__(self, runner: Optional[CommandRunner] = None) -> None:
        super().__init__(runner)
        self._serial: Optional[str] = None
        self._package: str = ""
        self._emulator: Any = None
        self._started_emulator = False

    # ── tools ───────────────────────────────────────────────────────────────
    def _sdk_tool(self, name: str, subdir: str) -> Optional[str]:
        found = self.runner.which(name)
        if found:
            return found
        for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
            root = os.environ.get(env)
            if root:
                candidate = os.path.join(root, subdir, name)
                if os.path.exists(candidate):
                    return candidate
        return None

    def _adb_path(self) -> str:
        adb = self._sdk_tool("adb", "platform-tools")
        if not adb:
            raise NativeEngineError("adb is not installed. " + SDK_HINT)
        return adb

    def _adb(self, *args: str, timeout: float = 60.0, device: bool = True):
        cmd = [self._adb_path()]
        if device and self._serial:
            cmd += ["-s", self._serial]
        return self.runner.run(cmd + list(args), timeout=timeout)

    def connected_devices(self) -> List[str]:
        result = self._adb("devices", device=False, timeout=20)
        serials = []
        for line in result.out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serials.append(parts[0])
        return serials

    def avds(self) -> List[str]:
        emulator = self._sdk_tool("emulator", "emulator")
        if not emulator:
            return []
        result = self.runner.run([emulator, "-list-avds"], timeout=30)
        return [line.strip() for line in result.out.splitlines() if line.strip() and not line.startswith("INFO")]

    # ── readiness ───────────────────────────────────────────────────────────
    def requirements(self) -> List[Requirement]:
        adb = self._sdk_tool("adb", "platform-tools")
        reqs = [Requirement("adb", "Android platform tools (adb)", GRANTED if adb else MISSING, "" if adb else SDK_HINT)]
        devices: List[str] = []
        if adb:
            try:
                devices = self.connected_devices()
            except NativeEngineError:
                devices = []
        emulator = self._sdk_tool("emulator", "emulator")
        avds = self.avds() if emulator else []
        reqs.append(Requirement(
            "device", "A running device or emulator",
            GRANTED if devices else MISSING,
            "" if devices else "Inspectra will start an emulator (below), or plug in a phone with USB debugging on.",
            optional=bool(avds),
        ))
        reqs.append(Requirement(
            "emulator", "An Android emulator (virtual device)",
            GRANTED if avds else MISSING,
            "" if avds else "Create a virtual device in Android Studio > Device Manager (or with avdmanager).",
            optional=bool(devices),
        ))
        return reqs

    # ── app control ─────────────────────────────────────────────────────────
    def start(self, app: AppSpec, timeout: float = 300.0) -> None:
        package = (app.identifier or "").strip()
        if not _PACKAGE_RE.match(package):
            raise NativeEngineError("Set the app's package name (for example com.example.app) on the app target.")
        self._package = package
        devices = self.connected_devices()
        if app.device and app.device in devices:
            self._serial = app.device
        elif devices and not app.device:
            self._serial = devices[0]
        else:
            self._boot_emulator(app.device, app.headless, timeout)
        if app.app_path:
            installed = self._adb("install", "-r", app.app_path, timeout=300)
            if not installed.ok or "Success" not in installed.out:
                raise NativeEngineError(f"Installing {os.path.basename(app.app_path)} failed: {installed.out.strip()[-300:]}")
        launched = self._adb("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1", timeout=60)
        if not launched.ok or "No activities found" in launched.out or "monkey aborted" in launched.out:
            raise NativeEngineError(f"Could not launch {package}; is it installed on the device?")

    def _boot_emulator(self, avd: str, headless: bool, timeout: float) -> None:
        emulator = self._sdk_tool("emulator", "emulator")
        if not emulator:
            raise NativeEngineError("No device is connected and the Android emulator is not installed. " + SDK_HINT)
        avds = self.avds()
        name = avd or (avds[0] if avds else "")
        if not name or name not in avds:
            raise NativeEngineError(
                f"No virtual device named {name!r}. Available: {', '.join(avds) or 'none'}."
            )
        before = set(self.connected_devices())
        args = [emulator, "-avd", name, "-no-snapshot-save", "-no-boot-anim"]
        if headless:
            args += ["-no-window", "-no-audio"]
        self._emulator = self.runner.spawn(args)
        self._started_emulator = True
        deadline = self.runner.now() + timeout
        while self.runner.now() < deadline:
            new = [s for s in self.connected_devices() if s not in before and s.startswith("emulator-")]
            if new:
                self._serial = new[0]
                booted = self._adb("shell", "getprop", "sys.boot_completed", timeout=20)
                if booted.out.strip() == "1":
                    return
            self.runner.sleep(2)
        raise NativeEngineError(f"The emulator {name!r} did not finish booting within {int(timeout)} s.")

    def elements(self) -> List[UIElement]:
        dumped = self._adb("exec-out", "uiautomator", "dump", "/dev/tty", timeout=30)
        text = dumped.out
        if "</hierarchy>" not in text:
            # Some Android versions cannot write the dump to a tty; use a file instead.
            self._adb("shell", "uiautomator", "dump", "/sdcard/inspectra_ui.xml", timeout=30)
            text = self._adb("exec-out", "cat", "/sdcard/inspectra_ui.xml", timeout=30).out
        return parse_ui_dump(text)

    def tap_element(self, element: UIElement) -> None:
        self._adb("shell", "input", "tap", str(int(element.x)), str(int(element.y)), timeout=20)

    def _wait_for_focused_input(self, timeout: float = 5.0) -> bool:
        """`input tap` returns before the screen changes; wait for a focused text field so typing is not lost."""
        deadline = self.runner.now() + timeout
        while True:
            try:
                if any(e.extra.get("focused") and e.extra.get("editable") for e in self.elements()):
                    return True
            except NativeEngineError:
                pass
            if self.runner.now() >= deadline:
                return False
            self.runner.sleep(0.3)

    def type_text(self, text: str) -> None:
        if text:
            self._wait_for_focused_input()
            result = self._adb("shell", "input", "text", escape_input_text(text), timeout=30)
            if not result.ok:
                raise NativeEngineError("Typing on the device failed.")

    def press(self, key: str) -> None:
        code = _KEYCODES.get((key or "").strip().lower())
        if code is None:
            raise NativeEngineError(f"Unknown key {key!r}. Use one of: {', '.join(sorted(_KEYCODES))}.")
        self._adb("shell", "input", "keyevent", str(code), timeout=20)

    def screenshot(self) -> Optional[bytes]:
        result = self._adb("exec-out", "screencap", "-p", timeout=30)
        return result.stdout if result.ok and result.stdout.startswith(b"\x89PNG") else None

    def stop(self) -> None:
        try:
            if self._serial and self._package:
                self._adb("shell", "am", "force-stop", self._package, timeout=20)
            if self._started_emulator and self._serial:
                self._adb("emu", "kill", timeout=30)
        except NativeEngineError:
            pass
        finally:
            if self._emulator is not None:
                try:
                    self._emulator.terminate()
                except Exception:
                    pass
            self._emulator = None
            self._started_emulator = False
