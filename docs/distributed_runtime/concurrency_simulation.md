# Concurrency Simulation

Concurrency simulation is handled by `ConcurrencySimulator`.

## What it simulates

1. simultaneous submissions
2. overlapping edits
3. duplicate clicks/submissions
4. parallel API calls
5. stale writes
6. conflicting role actions

## What it detects

1. ordering anomalies
2. duplicate entity operations
3. final-state divergence

Results are persisted in `concurrency_analysis` and consumed by distributed evidence and reporting flows.
