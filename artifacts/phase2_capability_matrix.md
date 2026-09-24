# Phase 2 Capability Matrix

Platform: `Darwin`

| Feature | Supported | Tested | Passed | Partial | Cap Gap | Setup Req | Notes |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| web | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | Playwright required |
| flutter_web | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Playwright required |
| native_macos | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | macOS only; Accessibility permission required |
| flutter_macos | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | macOS only; Flutter accessibility tree may be weak |
| native_windows | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Windows only; pywinauto required |
| flutter_windows | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Windows only; pywinauto required |
| native_linux | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Linux only; AT-SPI + xdotool required |
| flutter_linux | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Linux only; AT-SPI required |
| android | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Appium-Python-Client + server required; opt-in |
| ios | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | macOS + XCUITest + Appium required; opt-in |
| vision_fallback | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Screenshot-only; all clicks require approval; local_ollama default |
| screenshots | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | Platform-native capture |
| live_guided | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Step narrative + trace files |
| ai_guided | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Local AI oracle; no cloud without approval |
| logs | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Process stdout capture; secret redaction enabled |