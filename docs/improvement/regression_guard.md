# Regression Guard

`RegressionGuard` compares before/after quality snapshots and raises regression signals.

## Checks

1. new findings
2. worsened severity for existing findings
3. new test failures

## Output

Result is written to `regression_guard_report` and includes summary counts plus regression_detected boolean.

## Role in loop

Regression guard is part of both improvement quality controls and release/reporting signals, preventing blind acceptance of risky changes.
