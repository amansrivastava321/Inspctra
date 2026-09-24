# Mobile Safety Model

QA-AI mobile runtime is explicitly safety-gated.

## Default behavior

1. planning/simulation-first (`dry_run=True`)
2. no automatic installs or destructive operations
3. explicit permission required for real emulator/simulator lifecycle control

## Permission-gated operations

1. Android emulator start/stop requires explicit permission when not dry-run.
2. iOS simulator boot/shutdown requires explicit permission when not dry-run.
3. Mobile network real controls require explicit permission; default mode is simulation.

## Operational limitation

Live browser/device availability depends on host environment/tooling. When unavailable, QA-AI still produces validated planning artifacts instead of attempting unsafe fallback execution.
