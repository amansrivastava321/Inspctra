"""
macOS desktop apps through the Accessibility API (System Events, scripted with JavaScript for Automation).

macOS asks the user for three permissions, all granted to the app that runs Inspectra's backend
(Terminal, iTerm, VS Code, ...), not to Inspectra itself:

    Accessibility    - to read the screen's controls and click/type          (required)
    Automation       - to send events to "System Events"                      (required, prompted on first use)
    Screen Recording - so screenshots show the app instead of just wallpaper   (needed for screenshot evidence)
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
from typing import Any, List, Optional

from qa_ai.native_execution.base import (
    GRANTED,
    MISSING,
    UNKNOWN,
    AppSpec,
    CommandRunner,
    NativeEngine,
    NativeEngineError,
    Requirement,
    UIElement,
)

_SETTINGS = {
    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "screen_recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
    "automation": "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation",
}
_KEY_CODES = {
    "enter": 36, "return": 36, "tab": 48, "space": 49, "backspace": 51, "delete": 51, "escape": 53, "esc": 53,
    "left": 123, "right": 124, "down": 125, "up": 126,
}
_WHO = "the app that runs Inspectra (for example Terminal, iTerm or VS Code)"

_LIST_JS = r"""
function run(argv) {
  const se = Application('System Events');
  const proc = se.processes.byName(argv[0]);
  const wins = proc.windows();
  if (!wins.length) return '[]';
  const items = wins[0].entireContents();
  const out = [];
  for (let i = 0; i < items.length; i++) {
    const e = items[i];
    const o = {i: i};
    try { o.role = e.role(); } catch (x) {}
    try { o.name = e.name() || ''; } catch (x) {}
    try { o.desc = e.description() || ''; } catch (x) {}
    try { const v = e.value(); o.value = (v === null || v === undefined) ? '' : String(v); } catch (x) {}
    try { const p = e.position(); const s = e.size(); o.x = p[0] + s[0] / 2; o.y = p[1] + s[1] / 2; } catch (x) {}
    out.push(o);
  }
  return JSON.stringify(out);
}
"""

_CLICK_JS = r"""
function run(argv) {
  const se = Application('System Events');
  const proc = se.processes.byName(argv[0]);
  proc.frontmost = true;
  const items = proc.windows[0].entireContents();
  const e = items[parseInt(argv[1], 10)];
  if (!e) return 'moved';
  let seen = '';
  try { seen = [e.name(), e.description(), String(e.value())].join('|'); } catch (x) {}
  if (argv[2] && seen.indexOf(argv[2]) < 0) return 'moved';
  try { e.actions.byName('AXPress').perform(); } catch (x) { e.click(); }
  return 'ok';
}
"""

_FOCUS_JS = r"""
function run(argv) {
  const se = Application('System Events');
  se.processes.byName(argv[0]).frontmost = true;
  return 'ok';
}
"""

_TYPE_JS = r"""
function run(argv) { Application('System Events').keystroke(argv[0]); return 'ok'; }
"""

_KEY_JS = r"""
function run(argv) { Application('System Events').keyCode(parseInt(argv[0], 10)); return 'ok'; }
"""

_NAME_FOR_BUNDLE_JS = r"""
function run(argv) { return Application(argv[0]).name(); }
"""

_QUIT_JS = r"""
function run(argv) { Application(argv[0]).quit({saving: 'no'}); return 'ok'; }
"""

_AUTOMATION_PROBE_JS = r"""
function run(argv) { return String(Application('System Events').processes.length); }
"""


def parse_element_list(payload: str) -> List[UIElement]:
    items = json.loads(payload or "[]")
    elements: List[UIElement] = []
    for item in items:
        name, desc, value = item.get("name") or "", item.get("desc") or "", item.get("value") or ""
        elements.append(UIElement(
            label=name or desc,
            text=value if value != name else "",
            identifier=desc if name else "",
            role=item.get("role") or "",
            x=item.get("x"), y=item.get("y"),
            extra={"index": item.get("i"), "match": name or desc or value},
        ))
    return elements


class _MacPermissions:
    """Reads and requests the macOS privacy permissions through the system frameworks."""

    def _lib(self, path: str) -> Optional[Any]:
        try:
            return ctypes.cdll.LoadLibrary(path)
        except OSError:
            return None

    def accessibility(self, prompt: bool = False) -> Optional[bool]:
        services = self._lib("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        if services is None:
            return None
        if not prompt:
            services.AXIsProcessTrusted.restype = ctypes.c_bool
            return bool(services.AXIsProcessTrusted())
        cf = self._lib("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        if cf is None:
            return None
        key = ctypes.c_void_p.in_dll(services, "kAXTrustedCheckOptionPrompt")
        true = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue")
        keys = (ctypes.c_void_p * 1)(key.value)
        values = (ctypes.c_void_p * 1)(true.value)
        cf.CFDictionaryCreate.restype = ctypes.c_void_p
        cf.CFDictionaryCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long,
                                          ctypes.c_void_p, ctypes.c_void_p]
        options = cf.CFDictionaryCreate(
            None, keys, values, 1,
            ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")),
            ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryValueCallBacks")),
        )
        services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        try:
            return bool(services.AXIsProcessTrustedWithOptions(options))
        finally:
            cf.CFRelease.argtypes = [ctypes.c_void_p]
            cf.CFRelease(options)

    def screen_recording(self, prompt: bool = False) -> Optional[bool]:
        graphics = self._lib("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        if graphics is None:
            return None
        name = "CGRequestScreenCaptureAccess" if prompt else "CGPreflightScreenCaptureAccess"
        fn = getattr(graphics, name, None)
        if fn is None:  # macOS before 10.15 has no such permission
            return True
        fn.restype = ctypes.c_bool
        return bool(fn())


class MacOSEngine(NativeEngine):
    platform = "native_macos"

    def __init__(
        self,
        runner: Optional[CommandRunner] = None,
        platform_name: Optional[str] = None,
        permissions: Optional[Any] = None,
    ) -> None:
        super().__init__(runner)
        self._platform_name = platform_name or sys.platform
        self._perms = permissions or _MacPermissions()
        self._process = ""
        self._launched = False

    # ── readiness ───────────────────────────────────────────────────────────
    def _automation_status(self) -> str:
        try:
            result = self._js(_AUTOMATION_PROBE_JS, timeout=15, check=False)
        except NativeEngineError:
            return UNKNOWN
        if result.ok:
            return GRANTED
        return MISSING if "-1743" in result.err or "Not authorized" in result.err else UNKNOWN

    def requirements(self) -> List[Requirement]:
        if self._platform_name != "darwin":
            return [Requirement("macos", "A Mac", MISSING, "Run Inspectra on a Mac to test Mac apps.")]
        acc = self._perms.accessibility()
        scr = self._perms.screen_recording()
        return [
            Requirement(
                "accessibility", "Accessibility (read controls, click and type)",
                UNKNOWN if acc is None else (GRANTED if acc else MISSING),
                f"System Settings > Privacy & Security > Accessibility: turn on {_WHO}, then restart it.",
                can_request=True,
            ),
            Requirement(
                "automation", "Automation (control System Events)", self._automation_status(),
                f"System Settings > Privacy & Security > Automation: allow {_WHO} to control System Events.",
                can_request=True,
            ),
            Requirement(
                "screen_recording", "Screen Recording (screenshots of the app)",
                UNKNOWN if scr is None else (GRANTED if scr else MISSING),
                f"System Settings > Privacy & Security > Screen Recording: turn on {_WHO}, then restart it.",
                can_request=True, optional=True,
            ),
        ]

    def request(self, requirement_id: str) -> bool:
        if self._platform_name != "darwin" or requirement_id not in _SETTINGS:
            return False
        if requirement_id == "accessibility":
            self._perms.accessibility(prompt=True)
        elif requirement_id == "screen_recording":
            self._perms.screen_recording(prompt=True)
        elif requirement_id == "automation":
            self._automation_status()  # the first Apple event shows the macOS prompt
        self.runner.run(["open", _SETTINGS[requirement_id]], timeout=15)
        return True

    # ── plumbing ────────────────────────────────────────────────────────────
    def _js(self, script: str, *argv: str, timeout: float = 30.0, check: bool = True):
        result = self.runner.run(["osascript", "-l", "JavaScript", "-e", script, *argv], timeout=timeout)
        if check and not result.ok:
            err = result.err.strip()
            if "-1743" in err or "Not authorized" in err:
                raise NativeEngineError("macOS blocked control of System Events: allow it under Privacy & Security > Automation.")
            if "-25211" in err or "assistive access" in err.lower():
                raise NativeEngineError("macOS blocked accessibility access: turn it on under Privacy & Security > Accessibility.")
            raise NativeEngineError(f"macOS automation failed: {err[-200:]}")
        return result

    # ── app control ─────────────────────────────────────────────────────────
    def start(self, app: AppSpec, timeout: float = 60.0) -> None:
        if self._platform_name != "darwin":
            raise NativeEngineError("Mac apps can only be tested on a Mac.")
        ident = (app.identifier or "").strip()
        path = (app.app_path or "").strip()
        if path:
            opened = self.runner.run(["open", path], timeout=60)
            self._process = os.path.splitext(os.path.basename(path.rstrip("/")))[0]
        elif ident and "." in ident and " " not in ident and "/" not in ident:
            opened = self.runner.run(["open", "-b", ident], timeout=60)
            if opened.ok:
                self._process = self._js(_NAME_FOR_BUNDLE_JS, ident).out.strip()
        elif ident:
            opened = self.runner.run(["open", "-a", ident], timeout=60)
            self._process = ident
        else:
            raise NativeEngineError("Set the app's name (for example TextEdit) or bundle id on the app target.")
        if not opened.ok:
            raise NativeEngineError(f"Could not open the app: {opened.err.strip()[-200:]}")
        self._launched = True
        deadline = self.runner.now() + timeout
        while True:
            try:
                self._js(_FOCUS_JS, self._process, timeout=15)
                if self._window_count() > 0:
                    return
            except NativeEngineError:
                if self.runner.now() >= deadline:
                    raise
            if self.runner.now() >= deadline:
                raise NativeEngineError(f"{self._process} opened no window within {int(timeout)} s.")
            self.runner.sleep(0.5)

    def _window_count(self) -> int:
        result = self._js(
            "function run(argv){return String(Application('System Events').processes.byName(argv[0]).windows.length);}",
            self._process, timeout=15,
        )
        try:
            return int(result.out.strip() or 0)
        except ValueError:
            return 0

    def elements(self) -> List[UIElement]:
        return parse_element_list(self._js(_LIST_JS, self._process, timeout=60).out)

    def tap_element(self, element: UIElement) -> None:
        result = self._js(_CLICK_JS, self._process, str(element.extra.get("index")), str(element.extra.get("match") or ""))
        if result.out.strip() != "ok":
            raise NativeEngineError("The window changed before the click; the element is no longer where it was.")

    def type_text(self, text: str) -> None:
        if text:
            self._js(_FOCUS_JS, self._process)
            self._js(_TYPE_JS, text)

    def press(self, key: str) -> None:
        code = _KEY_CODES.get((key or "").strip().lower())
        if code is None:
            raise NativeEngineError(f"Unknown key {key!r}. Use one of: {', '.join(sorted(_KEY_CODES))}.")
        self._js(_FOCUS_JS, self._process)
        self._js(_KEY_JS, str(code))

    def screenshot(self) -> Optional[bytes]:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "screen.png")
            result = self.runner.run(["screencapture", "-x", "-t", "png", path], timeout=30)
            if not result.ok or not os.path.exists(path):
                return None
            with open(path, "rb") as fh:
                return fh.read()

    def stop(self) -> None:
        if self._launched and self._process:
            try:
                self._js(_QUIT_JS, self._process, timeout=15, check=False)
            except NativeEngineError:
                pass
        self._launched = False
