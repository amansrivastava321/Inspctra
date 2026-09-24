# Runtime Lab

Runtime Lab is QA-AI’s environment-aware execution layer for live benchmark flows and operational readiness planning.

## Core components

1. `EnvironmentBootstrapper`: creates dependency/bootstrap plans (`bootstrap_plan`) with no automatic installs by default.
2. `DockerRuntime`: detects Docker and creates start/build plans (`docker_runtime_plan`) without auto-run.
3. `LiveBenchmarkRunner`: orchestrates app launch/discovery/monitor/cleanup around benchmark execution.
4. `RuntimeMonitor`: captures process health, crash indicators, and error-rate signals.

## Safety behavior

1. Planning-first by default (`dry_run=True` in major paths).
2. Install and runtime actions are marked `requires_permission`.
3. Runtime cleanup is explicit (`CleanupManager` path in live benchmark flow).

## Current limitations

1. Some runtime operations are planning-first/dry-run.
2. Live app launch and browser execution depend on local tool availability.
3. Docker/container operations are planned but not automatically started.
