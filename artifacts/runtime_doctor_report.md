# Runtime Environment Doctor Report

Generated: 2026-08-30T06:24:16.605879+00:00  
Platform: `macos`  
Python: `3.11.15` at `/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/venv/bin/python`  
Venv: ✅ /Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/venv

## Readiness Score: 79/100 (USABLE)

## Packages

| Package | Installed |
|---|:---:|
| playwright | ✅ |
| playwright browsers | ✅ |
| Appium-Python-Client | ❌ |

## OS Capabilities

| Capability | Status |
|---|:---:|
| macOS Accessibility | ✅ |
| screencapture | ✅ |

## Appium Ecosystem

| Component | Status |
|---|:---:|
| npm | ✅ |
| appium command | ✅ |
| uiautomator2 driver | ❌ |
| xcuitest driver | ❌ |

## Services

| Service | Status |
|---|:---:|
| Appium server (http://localhost:4723) | ❌ |
| Ollama (localhost:11434) | ✅ |

Ollama models: gemma4:12b, qwen2.5-coder:7b, bge-m3:latest, phi4-mini:latest, qwen2.5vl:7b, deepseek-r1:7b, qwen3.5:9b, gemma4:e4b

Configured vision model: `qwen2.5vl:7b` ✅ available

## Driver Readiness

| App Type | Driver | Status | Missing |
|---|---|:---:|---|
| flutter_web | WebPlaywrightDriver | ✅ ready | — |
| android | AndroidAppiumDriver | ❌ missing_deps | Appium-Python-Client, appium-server-not-running |
| flutter_macos | MacOSAccessibilityDriver | ✅ ready | — |
| native_macos | MacOSAccessibilityDriver | ✅ ready | — |
| ios | IOSAppiumDriver | ❌ missing_deps | Appium-Python-Client, appium-server-not-running |
| web | WebPlaywrightDriver | ✅ ready | — |

## Missing Items

- ❌ Appium-Python-Client not installed
- ❌ Appium server not running
- ❌ Appium uiautomator2 driver not installed
- ❌ Appium xcuitest driver not installed

## Recommended Actions

- Install Appium client: pip install Appium-Python-Client
- Start Appium server: appium --address 127.0.0.1 --port 4723
- Install Android driver: appium driver install uiautomator2

---
_Run `python -m qa_ai.cli runtime-doctor --auto-setup` to fix automatically._