"""Windows desktop apps through Windows UI Automation (pywinauto). Windows needs no privacy prompt for this,
but apps running as administrator can only be controlled when Inspectra also runs as administrator."""
from __future__ import annotations

import io
import os
import re
import sys
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

_KEYS = {
    "enter": "{ENTER}", "return": "{ENTER}", "tab": "{TAB}", "escape": "{ESC}", "esc": "{ESC}",
    "backspace": "{BACKSPACE}", "delete": "{DELETE}", "space": "{SPACE}",
    "up": "{UP}", "down": "{DOWN}", "left": "{LEFT}", "right": "{RIGHT}", "home": "{HOME}",
}
_SEND_KEYS_SPECIAL = set("+^%~(){}[]")


def escape_send_keys(text: str) -> str:
    """pywinauto send_keys treats + ^ % ~ ( ) { } [ ] as commands; wrap them so they are typed literally."""
    out = []
    for ch in text:
        if ch in "\r\n\t":
            raise NativeEngineError("Use a separate 'press' step for Enter or Tab instead of typing them.")
        out.append("{" + ch + "}" if ch in _SEND_KEYS_SPECIAL else ch)
    return "".join(out)


def _load_pywinauto() -> Any:
    import pywinauto  # noqa: F401  (Windows only)
    from pywinauto import Application, Desktop, keyboard

    class _Lib:
        pass

    lib = _Lib()
    lib.Application, lib.Desktop, lib.keyboard = Application, Desktop, keyboard
    return lib


def _has_module(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


class WindowsEngine(NativeEngine):
    platform = "native_windows"

    def __init__(
        self,
        runner: Optional[CommandRunner] = None,
        platform_name: Optional[str] = None,
        loader: Any = None,
        module_check: Any = None,
    ) -> None:
        super().__init__(runner)
        self._platform_name = platform_name or sys.platform
        self._loader = loader or _load_pywinauto
        self._has = module_check or _has_module
        self._lib: Any = None
        self._app: Any = None
        self._window: Any = None
        self._preexisting: set = set()

    def requirements(self) -> List[Requirement]:
        if self._platform_name != "win32":
            return [Requirement("windows", "A Windows PC", MISSING, "Run Inspectra on Windows to test Windows apps.")]
        has_pwa, has_pil = self._has("pywinauto"), self._has("PIL")
        return [
            Requirement("pywinauto", "pywinauto (Windows UI Automation)", GRANTED if has_pwa else MISSING,
                        "" if has_pwa else "pip install pywinauto"),
            Requirement("pillow", "Pillow (screenshots)", GRANTED if has_pil else MISSING,
                        "" if has_pil else "pip install pillow", optional=True),
        ]

    def _pwa(self) -> Any:
        if self._lib is None:
            if self._platform_name != "win32":
                raise NativeEngineError("Windows apps can only be tested on Windows.")
            try:
                self._lib = self._loader()
            except ImportError as exc:
                raise NativeEngineError("pywinauto is not installed: pip install pywinauto") from exc
        return self._lib

    def start(self, app: AppSpec, timeout: float = 60.0) -> None:
        lib = self._pwa()
        command = (app.app_path or app.identifier or "").strip()
        if not command:
            raise NativeEngineError("Set the program to start (for example notepad.exe) on the app target.")
        cmd_line = f'"{command}"' if " " in command and not command.startswith('"') else command
        stem = os.path.splitext(os.path.basename(command.strip('"')))[0]
        title = (app.device or "").strip()
        pattern = re.compile(re.escape(title) if title else re.escape(stem), re.IGNORECASE)
        # Windows of this app that were already open belong to the user: never drive or close those.
        self._preexisting = {self._handle(w) for w in self._matching_desktop_windows(lib, pattern)}
        try:
            self._app = lib.Application(backend="uia").start(cmd_line, timeout=timeout)
        except Exception as exc:
            raise NativeEngineError(f"Could not start {command}: {type(exc).__name__}: {exc}") from exc
        deadline = self.runner.now() + timeout
        while True:
            self._window = self._find_window(lib, pattern)
            if self._window is not None:
                try:
                    self._window.set_focus()
                except Exception:
                    pass
                return
            if self.runner.now() >= deadline:
                raise NativeEngineError(
                    f"No window titled like {title or stem!r} appeared within {int(timeout)} s. "
                    "Set the window title on the app target if it differs from the program name."
                )
            self.runner.sleep(0.5)

    def _find_window(self, lib: Any, pattern: "re.Pattern[str]") -> Any:
        # Prefer the started process's own window; many modern apps (Notepad on Windows 11) hand off to
        # another process, so fall back to any top-level window with a matching title.
        try:
            window = self._app.top_window()
            if pattern.search(window.window_text() or "") and self._handle(window) not in self._preexisting:
                return window
        except Exception:
            pass
        for window in self._matching_desktop_windows(lib, pattern):
            if self._handle(window) not in self._preexisting:
                return window
        return None

    @staticmethod
    def _matching_desktop_windows(lib: Any, pattern: "re.Pattern[str]") -> List[Any]:
        try:
            return [w for w in lib.Desktop(backend="uia").windows() if pattern.search(w.window_text() or "")]
        except Exception:
            return []

    @staticmethod
    def _handle(window: Any) -> Any:
        try:
            return window.handle
        except Exception:
            return id(window)

    def _require_window(self) -> Any:
        if self._window is None:
            raise NativeEngineError("No app window: add an 'app_launch' step first.")
        return self._window

    def elements(self) -> List[UIElement]:
        window = self._require_window()
        elements: List[UIElement] = []
        for wrapper in [window, *window.descendants()]:
            info = wrapper.element_info
            value = ""
            try:
                value = wrapper.get_value() or ""
            except Exception:
                try:
                    text = wrapper.window_text() or ""
                    value = text if text != (info.name or "") else ""
                except Exception:
                    value = ""
            try:
                mid = wrapper.rectangle().mid_point()
                x, y = float(mid.x), float(mid.y)
            except Exception:
                x = y = None
            elements.append(UIElement(
                label=info.name or "", text=str(value), identifier=getattr(info, "automation_id", "") or "",
                role=getattr(info, "control_type", "") or "", x=x, y=y, extra={"wrapper": wrapper},
            ))
        return elements

    def tap_element(self, element: UIElement) -> None:
        wrapper = element.extra.get("wrapper")
        if wrapper is None:
            raise NativeEngineError("That element can no longer be clicked.")
        wrapper.click_input()

    def type_text(self, text: str) -> None:
        if text:
            self._require_window().set_focus()
            self._pwa().keyboard.send_keys(escape_send_keys(text), with_spaces=True, pause=0.01)

    def press(self, key: str) -> None:
        sequence = _KEYS.get((key or "").strip().lower())
        if sequence is None:
            raise NativeEngineError(f"Unknown key {key!r}. Use one of: {', '.join(sorted(_KEYS))}.")
        self._require_window().set_focus()
        self._pwa().keyboard.send_keys(sequence)

    def screenshot(self) -> Optional[bytes]:
        if self._window is None:
            return None
        try:
            image = self._window.capture_as_image()
        except Exception:
            return None
        if image is None:
            return None
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def stop(self) -> None:
        try:
            if self._app is not None:
                self._app.kill()
        except Exception:
            pass
        try:
            # Only a window this run opened (never one the user already had open). An app may still ask
            # whether to save; that dialog is left for the user rather than answered for them.
            if self._window is not None and self._handle(self._window) not in self._preexisting and self._window.exists():
                self._window.close()
        except Exception:
            pass
        self._app = self._window = None
