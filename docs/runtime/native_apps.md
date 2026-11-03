# Desktop and mobile app testing

Inspectra can drive real apps on four platforms, in addition to websites and APIs:

| App type | What drives it | Runs on | You need |
| --- | --- | --- | --- |
| `native_macos` (Mac app) | macOS Accessibility via System Events (`osascript`) | a Mac | the permissions below |
| `native_windows` (Windows app) | Windows UI Automation (`pywinauto`) | Windows | `pip install pywinauto pillow` |
| `android` | `adb` against an emulator or a connected phone | Mac, Windows, Linux | Android Studio (platform-tools + emulator) |
| `ios` | the iOS Simulator (`xcrun simctl`) and `idb` | a Mac | Xcode, and `idb` for taps/typing |

## Permission first

Inspectra never controls anything until you allow it. Pick a Mac, Windows, Android or iOS app target in **Start
run** and the dialog shows:

1. **What this computer needs**: each tool or system permission, whether it is ready, and how to fix it.
   For the ones the system lets an app ask for, **Ask the system** shows the macOS prompt or opens the right
   page of System Settings. **Check again** re-reads them.
2. **Allow Inspectra to**: open and close the app, click/tap and type in it, take screenshots, and (mobile)
   start an emulator or simulator. All of them must be ticked before **Allow** works. Optionally also allow
   scheduled runs to do this while you are away.

**Start run** stays disabled until the tools are ready and you have allowed the platform. The API enforces the
same rule (`409 native_permission_required`), and every app step checks it again, so a scheduled run never drives
an app unless you allowed unattended runs. **Take back** removes the permission at any time.

API: `GET /api/native/{platform}/readiness`, `POST /api/native/{platform}/permissions/{id}/request`,
`PUT /api/native/{platform}/consent` (`{"scopes": [...], "unattended": false}`), `DELETE /api/native/{platform}/consent`.

### macOS permissions

macOS grants these to the app that runs Inspectra's backend (Terminal, iTerm, VS Code, ...), under
System Settings > Privacy & Security:

- **Accessibility**: read the app's controls, click and type. Required.
- **Automation > System Events**: macOS asks the first time Inspectra sends it an event. Required.
- **Screen Recording**: otherwise screenshots show only the wallpaper. Optional, but needed for screenshot evidence.

After turning one on, quit and reopen that terminal app, then press **Check again**.

## App targets

Add an app with **Add app** and choose Mac, Windows, Android or iOS. Fields:

- **Identifier**: Mac app name or bundle id (`TextEdit`, `com.apple.TextEdit`); Windows program (`notepad.exe`);
  Android package (`com.example.app`); iOS bundle id (`com.example.app`). Required.
- **App file** (optional): a `.app`, `.exe`, `.apk` or simulator `.app` build to open or install first.
- **Device** (optional): Android emulator (AVD) name or device serial; iOS Simulator name; Windows window title
  when it differs from the program name.

## Steps

| Step | Target | Value |
| --- | --- | --- |
| `app_launch` | optional identifier (defaults to the target's) | |
| `app_tap` | the on-screen label (text, accessibility label or id) | |
| `app_type` | optional field label to tap first | the text to type |
| `app_press` | | a key: enter, tab, escape, backspace, space, arrows; back/home on mobile |
| `app_assert_text` / `app_wait_for_text` | | text that must appear (waits up to the step timeout) |
| `app_screenshot` | | |
| `app_close` | | |

Labels match exactly first, then ignoring case, then as a substring. Every app step stores a screenshot as
evidence. Typed text is never written into the step notes. A missing tool or permission makes the step a
**capability gap** with the fix in its notes, never a pass.

## Background or on screen

- **Android and iOS** run without a window (headless emulator / simulator) unless you tick **Watch it run**,
  so you can keep working. Inspectra boots an emulator only when no device is connected, and shuts down only
  what it started.
- **Mac and Windows apps** necessarily use your real screen: Inspectra moves the pointer and types. Leave the
  computer alone until the run finishes. On Windows, windows of the app that were already open are never driven
  or closed.

## Verification

`tests/native_e2e/` runs these engines on real platforms in the **Native devices** GitHub workflow: an Android 14
emulator, a Windows desktop (Notepad) and a Mac with the iOS Simulator; screenshots are uploaded as artifacts.
When a runner has not granted Accessibility, the Mac-app test only checks the permission readout and skips the
driving part; run it on your own Mac after granting the permissions.

## Limits

- Linux desktop apps are not supported yet.
- iOS taps, typing and reading the screen need `idb`; without it the simulator can still be booted, the app
  launched and screenshots taken, and the steps that need `idb` report a capability gap.
- Real iPhones are not supported (only the Simulator). Real Android phones work through `adb` with USB debugging.
- Apps running as administrator on Windows can only be driven when Inspectra also runs as administrator.
