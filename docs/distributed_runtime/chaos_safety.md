# Chaos Safety Model

Chaos testing is implemented by `ChaosEngine` with safety gates.

## Safety rules

1. Dry-run simulation is default.
2. Disruptive actions are blocked unless explicit permission is provided.
3. Report always distinguishes executed vs blocked actions.

## Related controls

1. `NetworkConditionEngine` uses safe simulation defaults and does not apply destructive host controls.
2. `DistributedRuntimeRunner` invokes chaos with `dry_run=True` and `explicit_permission=False` in default flow.

## Artifact outputs

Primary outputs are:

1. `chaos_execution_report`
2. `network_condition_report`
3. `distributed_runtime_report`
