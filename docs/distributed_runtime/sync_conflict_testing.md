# Sync Conflict Testing

Sync/offline behavior is modeled through:

1. `OfflineRuntime` (queue replay and stale-state detection)
2. `SyncConflictEngine` (parallel edit conflict, divergence, orphan records, mapping anomalies)

## Multi-session orchestration context

`DistributedRuntimeRunner` seeds actor actions, runs offline/sync analyzers, and correlates outputs into `distributed_runtime_report`.

## Key artifacts

1. `offline_recovery_report`
2. `sync_conflict_report`
3. `distributed_evidence_graph`

This enables deterministic testing of conflict and replay semantics without requiring destructive environment manipulation.
