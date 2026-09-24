# Multi-Actor Model

Distributed runtime models concurrent behavior through actors with role-scoped permissions.

## Actor model

`ActorEngine` creates actors (cashier, manager, customer, background_sync, etc.), enforces permission checks on queued actions, and emits `actor_registry`.

## Session mapping

`MultiSessionOrchestrator` maps actors to isolated sessions:

1. browser sessions for interactive roles (planned in dry-run)
2. API sessions for background sync

Output is persisted as `multi_session_report`.

## Why this matters

This model lets QA-AI test authorization boundaries and race/offline/sync behavior in a controlled artifact-driven runtime without hard coupling to a single execution backend.
