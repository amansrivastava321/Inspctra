# Device Registry

`DeviceRegistry` inventories mobile tooling and available devices/simulators.

## Tooling probes

The registry checks:

1. Android SDK
2. adb / emulator
3. xcodebuild / xcrun
4. flutter
5. appium
6. maestro

## Inventory outputs

1. android emulators
2. android devices
3. iOS simulators

## Summary signals

`device_registry` includes readiness indicators (`android_ready`, `ios_ready`, `flutter_ready`, etc.) and counts used by runtime planning and mobile monitoring.
