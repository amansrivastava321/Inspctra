# Mobile Runtime Overview

Mobile runtime is a planning-first orchestration layer for Android/iOS/Flutter execution readiness, network simulation, session mapping, and evidence correlation.

## Core orchestration

`MobileRuntimeRunner` coordinates:

1. device/tool discovery
2. emulator/simulator planning
3. Flutter/Appium/Maestro execution planning
4. distributed actor-device session planning (optional)
5. mobile network simulation planning
6. runtime monitoring/log indexing/evidence graph generation

It persists `mobile_runtime_report` plus per-phase artifacts.

## Safety posture

1. default dry-run planning
2. no automatic package installs
3. no automatic destructive device/network controls
4. permission-aware control methods for emulator/simulator operations
