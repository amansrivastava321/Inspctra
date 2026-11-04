"""The desktop and mobile engines, driven against scripted platform tools."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, List

import pytest

from native_fakes import PNG, FakeRunner, fail, ok
from qa_ai.native_execution import (
    AppSpec,
    ElementNotFound,
    NativeEngineError,
    UIElement,
    engine_for,
    match_element,
    normalize_platform,
)
from qa_ai.native_execution.android import AndroidEngine, escape_input_text, parse_ui_dump
from qa_ai.native_execution.ios import IOSSimulatorEngine, parse_idb_elements, parse_simctl_devices
from qa_ai.native_execution.macos import MacOSEngine, parse_element_list
from qa_ai.native_execution.windows import WindowsEngine, escape_send_keys

UI_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation="0">
<node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.example" content-desc="" clickable="false" bounds="[0,0][1080,2400]">
<node index="1" text="Sign in" resource-id="com.example:id/login" class="android.widget.Button" package="com.example" content-desc="" clickable="true" bounds="[100,200][300,260]" />
<node index="2" text="" resource-id="com.example:id/email" class="android.widget.EditText" package="com.example" content-desc="Email" clickable="true" bounds="[100,300][900,360]" />
<node index="3" text="Welcome back" resource-id="" class="android.widget.TextView" package="com.example" content-desc="" clickable="false" bounds="[0,0][0,0]" />
</node></hierarchy>UI hierchary dumped to: /dev/tty"""


# ── shared ───────────────────────────────────────────────────────────────────

def test_matching_prefers_exact_then_case_insensitive_then_contains() -> None:
    elements = [
        UIElement(label="Sign in later", x=1, y=1),
        UIElement(label="sign in", x=2, y=2),
        UIElement(label="Sign in", x=3, y=3),
        UIElement(label="Sign in", x=None, y=None),  # off screen / no coordinates
    ]
    assert match_element(elements, "Sign in").x == 3
    assert match_element(elements, "SIGN IN").x == 2
    assert match_element(elements, "later").x == 1
    assert match_element(elements, "nothing") is None
    assert match_element(elements, "") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("native_macos", "native_macos"), ("macos", "native_macos"), ("windows", "native_windows"),
     ("android", "android"), ("iOS", "ios"), ("web", None), ("", None), (None, None)],
)
def test_platform_names_are_normalised(value, expected) -> None:
    assert normalize_platform(value) == expected


def test_the_factory_builds_each_engine_and_rejects_others() -> None:
    assert isinstance(engine_for("android"), AndroidEngine)
    assert isinstance(engine_for("ios"), IOSSimulatorEngine)
    assert isinstance(engine_for("native_macos"), MacOSEngine)
    assert isinstance(engine_for("native_windows"), WindowsEngine)
    with pytest.raises(ValueError):
        engine_for("web")


# ── Android ──────────────────────────────────────────────────────────────────

def test_the_android_screen_dump_is_parsed_with_tap_centres() -> None:
    elements = parse_ui_dump(UI_XML)

    sign_in = match_element(elements, "Sign in")
    assert (sign_in.x, sign_in.y) == (200, 230)
    assert match_element(elements, "Email").identifier == "com.example:id/email"
    assert match_element(elements, "email").label == "Email"
    # A zero-size element cannot be tapped, but its text still counts as visible.
    assert match_element(elements, "Welcome back") is None
    assert "Welcome back" in [e.text for e in elements]


def test_a_broken_dump_is_a_clear_error() -> None:
    with pytest.raises(NativeEngineError, match="screen contents"):
        parse_ui_dump("ERROR: could not get idle state.")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("hello world", "hello%sworld"), ("a&b;c", "a\\&b\\;c"), ("it's $5", "it\\'s%s\\$5"), ("user@example.com", "user@example.com")],
)
def test_typed_text_is_escaped_for_the_device_shell(text: str, expected: str) -> None:
    assert escape_input_text(text) == expected


def test_newlines_must_be_sent_as_key_presses() -> None:
    with pytest.raises(NativeEngineError, match="press"):
        escape_input_text("a\nb")


def _android(devices: str = "emulator-5554\tdevice\n", avds: str = "Pixel_8\n", extra=()) -> FakeRunner:
    return FakeRunner(
        rules=[
            *extra,
            ("adb devices", ok("List of devices attached\n" + devices)),
            ("-list-avds", ok(avds)),
            ("uiautomator dump /dev/tty", ok(UI_XML)),
            ("screencap -p", ok(PNG)),
            ("monkey -p", ok("Events injected: 1")),
            ("getprop sys.boot_completed", ok("1\n")),
        ],
        tools=("adb", "emulator"),
    )


def test_android_needs_adb(monkeypatch: pytest.MonkeyPatch) -> None:
    # Machines with the Android SDK installed (GitHub's Linux runners) must not leak it into this test.
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    reqs = {r.id: r for r in AndroidEngine(FakeRunner()).requirements()}

    assert reqs["adb"].status == "missing" and "platform-tools" in reqs["adb"].how_to_fix


def test_android_is_ready_with_a_device_or_an_emulator() -> None:
    with_device = AndroidEngine(_android(avds="")).missing()
    with_emulator = AndroidEngine(_android(devices="")).missing()
    with_neither = AndroidEngine(_android(devices="", avds="")).missing()

    assert with_device == [] and with_emulator == []
    assert {r.id for r in with_neither} == {"device", "emulator"}


def test_android_launches_on_the_connected_device_and_drives_it() -> None:
    runner = _android()
    engine = AndroidEngine(runner)

    engine.start(AppSpec(identifier="com.example"))
    engine.tap("Sign in")
    runner.rules.insert(0, ("uiautomator dump /dev/tty", ok(UI_XML.replace(
        'content-desc="Email" clickable="true"', 'content-desc="Email" clickable="true" focused="true"'))))
    engine.type_into("Email", "me@example.com")
    engine.press("enter")

    assert runner.ran("-s emulator-5554 shell monkey -p com.example -c android.intent.category.LAUNCHER 1")
    assert runner.ran("shell input tap 200 230")
    assert runner.ran("shell input tap 500 330")
    assert runner.ran("shell input text me@example.com")
    assert runner.ran("shell input keyevent 66")
    assert engine.screenshot() == PNG
    assert runner.spawned == []  # no emulator was needed


def test_android_boots_a_headless_emulator_when_no_device_is_connected() -> None:
    state = {"booted": False}

    def devices(_args: List[str]):
        return ok("List of devices attached\n" + ("emulator-5556\tdevice\n" if state["booted"] else ""))

    runner = _android(extra=[("adb devices", devices)])
    original_sleep = runner.sleep

    def sleep(seconds: float) -> None:
        state["booted"] = True
        original_sleep(seconds)

    runner.sleep = sleep  # type: ignore[assignment]
    engine = AndroidEngine(runner)

    engine.start(AppSpec(identifier="com.example", device="Pixel_8", headless=True))
    engine.stop()

    assert runner.spawned and runner.spawned[0][1:4] == ["-avd", "Pixel_8", "-no-snapshot-save"]
    assert "-no-window" in runner.spawned[0]
    assert runner.ran("-s emulator-5556 shell monkey")
    assert runner.ran("-s emulator-5556 emu kill")
    assert runner.processes[0].terminated


def test_android_shows_the_emulator_window_when_watching() -> None:
    runner = _android(devices="", extra=[])
    calls = {"n": 0}

    def devices(_args):
        calls["n"] += 1
        return ok("List of devices attached\n" + ("emulator-5554\tdevice\n" if calls["n"] > 2 else ""))

    runner.rules.insert(0, ("adb devices", devices))
    AndroidEngine(runner).start(AppSpec(identifier="com.example", headless=False))

    assert "-no-window" not in runner.spawned[0]


def test_android_never_stops_a_device_it_did_not_start() -> None:
    runner = _android()
    engine = AndroidEngine(runner)
    engine.start(AppSpec(identifier="com.example"))

    engine.stop()

    assert runner.ran("am force-stop com.example")
    assert not runner.ran("emu kill")


def test_android_requires_a_package_name() -> None:
    with pytest.raises(NativeEngineError, match="package name"):
        AndroidEngine(_android()).start(AppSpec(identifier="Settings; rm -rf /"))


def test_android_reports_an_app_that_is_not_installed() -> None:
    runner = _android(extra=[("monkey -p", ok("** No activities found to run, monkey aborted."))])

    with pytest.raises(NativeEngineError, match="installed"):
        AndroidEngine(runner).start(AppSpec(identifier="com.missing"))


def test_typing_waits_until_a_text_field_has_focus() -> None:
    focused_xml = UI_XML.replace(
        'content-desc="Email" clickable="true"', 'content-desc="Email" clickable="true" focused="true"'
    )
    runner = _android()
    engine = AndroidEngine(runner)
    engine.start(AppSpec(identifier="com.example"))
    dumps = iter([UI_XML, UI_XML, focused_xml])
    runner.rules.insert(0, ("uiautomator dump /dev/tty", lambda _a: ok(next(dumps, focused_xml))))
    before = len(runner.calls)

    engine.type_text("hello")

    calls = runner.calls[before:]
    typed_at = next(i for i, c in enumerate(calls) if "input text" in " ".join(c))
    assert sum("uiautomator dump" in " ".join(c) for c in calls[:typed_at]) == 3  # twice unfocused, then focused


def test_launch_waits_until_the_app_is_on_screen_and_still() -> None:
    other_app = UI_XML.replace('package="com.example"', 'package="com.android.launcher"')
    moving = UI_XML.replace("[100,200][300,260]", "[100,210][300,270]")
    dumps = iter([other_app, moving, UI_XML, UI_XML])
    runner = _android(extra=[("uiautomator dump /dev/tty", lambda _a: ok(next(dumps, UI_XML)))])

    AndroidEngine(runner).start(AppSpec(identifier="com.example"))

    assert sum("uiautomator dump" in " ".join(c) for c in runner.calls) >= 4


def test_typing_with_no_focused_field_fails_instead_of_typing_into_nothing() -> None:
    runner = _android()
    engine = AndroidEngine(runner)
    engine.start(AppSpec(identifier="com.example"))

    with pytest.raises(NativeEngineError, match="No text field has focus"):
        engine.type_text("hello")

    assert not runner.ran("input text")


def test_typing_into_a_field_taps_it_again_when_the_first_tap_is_dropped() -> None:
    focused_xml = UI_XML.replace(
        'content-desc="Email" clickable="true"', 'content-desc="Email" clickable="true" focused="true"'
    )
    state = {"taps": 0}

    def dump(_args):
        return ok(focused_xml if state["taps"] >= 2 else UI_XML)

    def tap(_args):
        state["taps"] += 1
        return ok()

    runner = _android(extra=[("uiautomator dump /dev/tty", dump), ("input tap", tap)])
    engine = AndroidEngine(runner)
    engine.start(AppSpec(identifier="com.example"))

    engine.type_into("Email", "me@example.com")

    assert state["taps"] == 2
    assert runner.ran("input text me@example.com")


def test_typing_into_a_field_that_takes_focus_taps_once() -> None:
    focused_xml = UI_XML.replace(
        'content-desc="Email" clickable="true"', 'content-desc="Email" clickable="true" focused="true"'
    )
    runner = _android(extra=[("uiautomator dump /dev/tty", ok(focused_xml))])
    engine = AndroidEngine(runner)
    engine.start(AppSpec(identifier="com.example"))

    engine.type_into("Email", "x")

    assert sum("input tap" in " ".join(c) for c in runner.calls) == 1


def test_android_tap_waits_for_the_element_then_gives_up() -> None:
    engine = AndroidEngine(_android())
    engine.start(AppSpec(identifier="com.example"))

    with pytest.raises(ElementNotFound, match="Checkout"):
        engine.tap("Checkout", timeout=2)


def test_android_rejects_unknown_keys() -> None:
    engine = AndroidEngine(_android())
    with pytest.raises(NativeEngineError, match="Unknown key"):
        engine.press("hyper")


# ── iOS ──────────────────────────────────────────────────────────────────────

SIMS = json.dumps({"devices": {
    "com.apple.CoreSimulator.SimRuntime.iOS-17-5": [
        {"udid": "IPAD", "name": "iPad Air", "state": "Shutdown", "isAvailable": True},
        {"udid": "IPHONE", "name": "iPhone 15", "state": "Shutdown", "isAvailable": True},
    ],
    "com.apple.CoreSimulator.SimRuntime.watchOS-10-0": [{"udid": "W", "name": "Watch", "state": "Shutdown"}],
}})
IDB = json.dumps([
    {"AXLabel": "Continue", "AXValue": None, "frame": {"x": 20, "y": 700, "width": 100, "height": 44}, "type": "Button"},
    {"AXLabel": "Name", "AXValue": "Aman", "AXUniqueId": "nameField", "frame": {"x": 20, "y": 100, "width": 300, "height": 40}},
])


def _ios(tools=("xcrun", "idb")) -> FakeRunner:
    return FakeRunner(rules=[
        ("simctl list devices", ok(SIMS)),
        ("describe-all", ok(IDB)),
    ], tools=tools)


def test_ios_simulators_are_listed_iphones_first_and_only_ios() -> None:
    names = [d["name"] for d in parse_simctl_devices(SIMS)]

    assert names == ["iPhone 15", "iPad Air"]


def test_ios_elements_are_parsed_from_both_idb_formats() -> None:
    as_array = parse_idb_elements(IDB)
    as_lines = parse_idb_elements("\n".join(json.dumps(e) for e in json.loads(IDB)))

    assert [(e.label, e.x, e.y) for e in as_array] == [(e.label, e.x, e.y) for e in as_lines]
    assert (as_array[0].x, as_array[0].y) == (70, 722)
    assert as_array[1].identifier == "nameField" and as_array[1].text == "Aman"


def test_ios_needs_a_mac() -> None:
    reqs = IOSSimulatorEngine(_ios(), platform_name="linux").requirements()

    assert [r.id for r in reqs] == ["macos"] and reqs[0].status == "missing"
    with pytest.raises(NativeEngineError, match="Mac"):
        IOSSimulatorEngine(_ios(), platform_name="linux").start(AppSpec(identifier="com.example"))


def test_ios_without_idb_says_how_to_install_it() -> None:
    reqs = {r.id: r for r in IOSSimulatorEngine(_ios(tools=("xcrun",)), platform_name="darwin").requirements()}

    assert reqs["xcode"].status == "granted" and reqs["simulator"].status == "granted"
    assert reqs["idb"].status == "missing" and "idb-companion" in reqs["idb"].how_to_fix


def test_ios_boots_the_simulator_headless_and_drives_the_app() -> None:
    runner = _ios()
    engine = IOSSimulatorEngine(runner, platform_name="darwin")

    engine.start(AppSpec(identifier="com.example.app", headless=True))
    engine.tap("Continue")
    engine.type_text("hello")
    engine.press("home")
    engine.stop()

    assert runner.ran("xcrun simctl boot IPHONE")
    assert not runner.ran("open -a Simulator")
    assert runner.ran("xcrun simctl launch IPHONE com.example.app")
    assert runner.ran("idb ui tap 70 722 --udid IPHONE")
    assert runner.ran("idb ui text hello --udid IPHONE")
    assert runner.ran("idb ui button HOME --udid IPHONE")
    assert runner.ran("xcrun simctl shutdown IPHONE")


def test_ios_retries_when_the_accessibility_service_is_busy() -> None:
    answers = iter([
        fail("The simulator's accessibility service did not answer a frontmost request within 5.0s; retry the read."),
        ok(IDB),
    ])
    runner = _ios()
    runner.rules.insert(0, ("describe-all", lambda _a: next(answers)))
    engine = IOSSimulatorEngine(runner, platform_name="darwin")
    engine.start(AppSpec(identifier="com.example.app", headless=True))

    assert [e.label for e in engine.elements()] == ["Continue", "Name"]


def test_ios_does_not_retry_other_idb_errors() -> None:
    runner = _ios()
    runner.rules.insert(0, ("describe-all", fail("No such device")))
    engine = IOSSimulatorEngine(runner, platform_name="darwin")
    engine.start(AppSpec(identifier="com.example.app", headless=True))

    with pytest.raises(NativeEngineError, match="No such device"):
        engine.elements()
    assert sum("describe-all" in " ".join(c) for c in runner.calls) == 1


def test_ios_opens_the_simulator_window_when_watching() -> None:
    runner = _ios()

    IOSSimulatorEngine(runner, platform_name="darwin").start(AppSpec(identifier="com.example.app", device="iPad Air"))

    assert runner.ran("xcrun simctl boot IPAD")
    assert runner.ran("open -a Simulator")


def test_ios_reports_an_unknown_simulator() -> None:
    with pytest.raises(NativeEngineError, match="iPhone 99"):
        IOSSimulatorEngine(_ios(), platform_name="darwin").start(AppSpec(identifier="com.x", device="iPhone 99"))


# ── macOS ────────────────────────────────────────────────────────────────────

class _Perms:
    def __init__(self, accessibility=True, screen=True) -> None:
        self.acc, self.scr = accessibility, screen
        self.asked: List[str] = []

    def accessibility(self, prompt: bool = False):
        if prompt:
            self.asked.append("accessibility")
        return self.acc

    def screen_recording(self, prompt: bool = False):
        if prompt:
            self.asked.append("screen_recording")
        return self.scr


MAC_ELEMENTS = json.dumps([
    {"i": 0, "role": "AXButton", "name": "Save", "desc": "", "value": "", "x": 10, "y": 20},
    {"i": 1, "role": "AXTextArea", "name": "", "desc": "text", "value": "Hello from Inspectra", "x": 50, "y": 60},
])


def _mac(extra=()) -> FakeRunner:
    return FakeRunner(rules=[
        *extra,
        ("entireContents();\n  const out", ok(MAC_ELEMENTS)),
        ("windows.length", ok("1")),
        ("Application(argv[0]).name()", ok("TextEdit\n")),
        ("e.actions.byName", ok("ok\n")),
    ], tools=("osascript",))


def test_mac_permissions_are_reported_and_explained() -> None:
    reqs = {r.id: r for r in MacOSEngine(_mac(), platform_name="darwin", permissions=_Perms(False, False)).requirements()}

    assert reqs["accessibility"].status == "missing" and reqs["accessibility"].can_request
    assert "Accessibility" in reqs["accessibility"].how_to_fix and "Terminal" in reqs["accessibility"].how_to_fix
    assert reqs["screen_recording"].status == "missing" and reqs["screen_recording"].optional
    assert reqs["automation"].status == "granted"


def test_mac_automation_denied_is_detected() -> None:
    runner = _mac(extra=[("processes.length", fail("execution error: Not authorized to send Apple events to System Events. (-1743)"))])

    reqs = {r.id: r for r in MacOSEngine(runner, platform_name="darwin", permissions=_Perms()).requirements()}

    assert reqs["automation"].status == "missing"


def test_requesting_a_mac_permission_shows_the_prompt_and_opens_its_settings() -> None:
    perms = _Perms(False, False)
    runner = _mac()
    engine = MacOSEngine(runner, platform_name="darwin", permissions=perms)

    assert engine.request("accessibility") is True
    assert engine.request("screen_recording") is True
    assert engine.request("bogus") is False

    assert perms.asked == ["accessibility", "screen_recording"]
    assert runner.ran("open x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
    assert runner.ran("Privacy_ScreenCapture")


def test_mac_is_not_available_elsewhere() -> None:
    engine = MacOSEngine(_mac(), platform_name="linux", permissions=_Perms())

    assert [r.id for r in engine.requirements()] == ["macos"]
    assert engine.request("accessibility") is False


def test_mac_labels_come_from_the_accessibility_label_not_the_role_words() -> None:
    # What macOS 15's Calculator really reports: no name, the role in words, and the label in AXDescription.
    payload = json.dumps([
        {"i": 0, "role": "AXButton", "name": "", "desc": "button", "axdesc": "7", "ident": "Seven", "x": 1, "y": 1},
        {"i": 1, "role": "AXButton", "name": "", "desc": "button", "ident": "Add", "x": 2, "y": 2},
        {"i": 2, "role": "AXStaticText", "name": "", "desc": "text", "value": "\u200e9", "x": 3, "y": 3},
    ])

    elements = parse_element_list(payload)

    assert match_element(elements, "7").identifier == "Seven"
    assert match_element(elements, "Seven").label == "7"
    assert match_element(elements, "Add").extra["index"] == 1
    assert match_element(elements, "button") is None  # the role word is not a label
    assert any("9" in t for t in [e.text for e in elements])


def test_mac_elements_come_from_the_accessibility_tree() -> None:
    elements = parse_element_list(MAC_ELEMENTS)

    assert match_element(elements, "Save").extra["index"] == 0
    assert "Hello from Inspectra" in [e.text for e in elements]


def test_mac_opens_an_app_by_bundle_id_and_clicks_by_index() -> None:
    runner = _mac()
    engine = MacOSEngine(runner, platform_name="darwin", permissions=_Perms())

    engine.start(AppSpec(identifier="com.apple.TextEdit"))
    engine.tap("Save")
    engine.press("enter")
    engine.stop()

    assert runner.ran("open -b com.apple.TextEdit")
    click = next(c for c in runner.calls if "e.actions.byName" in " ".join(c))
    assert click[-3:] == ["TextEdit", "0", "Save"]
    assert any(c[-1] == "36" for c in runner.calls)  # Return
    assert runner.ran("quit({saving: 'no'})")


def test_typed_text_goes_to_osascript_as_an_argument_not_code() -> None:
    runner = _mac()
    engine = MacOSEngine(runner, platform_name="darwin", permissions=_Perms())
    engine.start(AppSpec(identifier="TextEdit"))

    engine.type_text("'); doShellScript('rm -rf ~'); ('")

    typed = next(c for c in runner.calls if "keystroke(argv[0])" in " ".join(c))
    assert typed[-1] == "'); doShellScript('rm -rf ~'); ('"


def test_a_blocked_mac_permission_becomes_a_clear_message() -> None:
    runner = _mac(extra=[("entireContents();\n  const out", fail("System Events got an error: osascript is not allowed assistive access. (-25211)"))])
    engine = MacOSEngine(runner, platform_name="darwin", permissions=_Perms())
    engine.start(AppSpec(identifier="TextEdit"))

    with pytest.raises(NativeEngineError, match="Accessibility"):
        engine.elements()


# ── Windows ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("text", "expected"), [("hi there", "hi there"), ("1+1=2", "1{+}1=2"), ("(a)", "{(}a{)}"), ("50%", "50{%}")])
def test_windows_send_keys_specials_are_typed_literally(text: str, expected: str) -> None:
    assert escape_send_keys(text) == expected


class _Wrapper:
    def __init__(self, name: str, value: str = "", x: int = 0, y: int = 0, handle: int = 0, title: str = "") -> None:
        self.element_info = SimpleNamespace(name=name, automation_id=name.lower(), control_type="Button")
        self._value, self._mid, self.handle, self._title = value, SimpleNamespace(x=x, y=y), handle, title
        self.clicked = self.closed = self.focused = False
        self.children: List["_Wrapper"] = []

    def get_value(self) -> str:
        if not self._value:
            raise AttributeError
        return self._value

    def window_text(self) -> str:
        return self._title or self.element_info.name

    def rectangle(self) -> Any:
        return SimpleNamespace(mid_point=lambda: self._mid)

    def descendants(self) -> List["_Wrapper"]:
        return self.children

    def click_input(self) -> None:
        self.clicked = True

    def set_focus(self) -> None:
        self.focused = True

    def exists(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True

    def capture_as_image(self) -> Any:
        return None


def _windows_lib(existing: List[_Wrapper], new_window: _Wrapper, typed: List[str]):
    desktop_windows = list(existing)

    class _App:
        killed = False

        def start(self, cmd: str, timeout: float = 0) -> "_App":
            desktop_windows.append(new_window)
            return self

        def top_window(self) -> _Wrapper:
            raise RuntimeError("handed off to another process")  # like Notepad on Windows 11

        def kill(self) -> None:
            _App.killed = True

    lib = SimpleNamespace(
        Application=lambda backend: _App(),
        Desktop=lambda backend: SimpleNamespace(windows=lambda: list(desktop_windows)),
        keyboard=SimpleNamespace(send_keys=lambda keys, **kw: typed.append(keys)),
        app_class=_App,
    )
    return lib


def test_windows_requirements_name_the_missing_packages() -> None:
    reqs = {r.id: r for r in WindowsEngine(platform_name="win32", module_check=lambda name: False).requirements()}

    assert reqs["pywinauto"].status == "missing" and reqs["pywinauto"].how_to_fix == "pip install pywinauto"
    assert reqs["pillow"].optional
    assert [r.id for r in WindowsEngine(platform_name="darwin").requirements()] == ["windows"]


def test_windows_drives_the_new_window_and_never_the_users_own() -> None:
    users = _Wrapper("Notepad", handle=1, title="notes.txt - Notepad")
    ours = _Wrapper("Notepad", handle=2, title="Untitled - Notepad")
    save = _Wrapper("Save", x=40, y=50)
    ours.children = [save, _Wrapper("Text editor", value="Hello")]
    typed: List[str] = []
    lib = _windows_lib([users], ours, typed)
    engine = WindowsEngine(FakeRunner(), platform_name="win32", loader=lambda: lib)

    engine.start(AppSpec(identifier="notepad.exe"))
    engine.tap("Save")
    engine.type_text("a+b")
    engine.press("enter")
    assert "Hello" in engine.visible_text()
    engine.stop()

    assert save.clicked
    assert typed == ["a{+}b", "{ENTER}"]
    assert ours.closed and not users.closed


def test_windows_explains_when_no_window_appears() -> None:
    lib = _windows_lib([], _Wrapper("Other", handle=5, title="Something else"), [])
    engine = WindowsEngine(FakeRunner(), platform_name="win32", loader=lambda: lib)

    with pytest.raises(NativeEngineError, match="window title"):
        engine.start(AppSpec(identifier="notepad.exe"), timeout=2)
