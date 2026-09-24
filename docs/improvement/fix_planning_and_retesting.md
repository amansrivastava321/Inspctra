# Fix Planning and Retesting

## Fix planning

`FixPlanner` converts findings/root causes into bounded fix plans (`fix_plan`) with:

1. risk level
2. affected files/modules/workflows/APIs
3. recommended tests
4. safe steps
5. permission requirement flag

## Retest orchestration

`RetestOrchestrator` selects targeted tests from fix/test plans and can optionally execute them. Default improvement workflow usage keeps execution disabled (`execute=False`), preserving planning-first behavior.

## Remediation gating

`RemediationEngine` transforms fix plans into `remediation_plan` actions with states like:

1. `blocked_pending_permission`
2. `dry_run_only`
3. `ready_for_approved_apply`
