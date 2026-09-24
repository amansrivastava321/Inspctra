# Flutter Execution Planning

Flutter and mobile bridge planning is generated without auto-execution by default.

## FlutterRunner

`FlutterRunner` detects Flutter project structure and writes `flutter_execution_plan` containing:

1. dependency checks (`pubspec.yaml`, `flutter` binary, test dirs)
2. planned commands (`flutter test`, integration test plan, `flutter drive`)
3. execution flags (`execute=False` by default in planning flow)

## Appium and Maestro bridges

1. `AppiumBridge` writes `appium_plan` with capability metadata and non-executing server/session plans.
2. `MaestroBridge` writes `maestro_plan` by inspecting `.maestro` flow files and generating planned commands.

## Safety constraints

1. no automatic installs
2. no automatic command execution in planning mode
3. permission gating required for non-dry-run operations
