# Remaining Limitations

Current limitations (based on implemented behavior):

1. many runtime/distributed/mobile flows are intentionally planning-first or simulation-first.
2. live browser/device execution depends on host environment/toolchain availability.
3. AI reasoning is advisory and does not apply code remediation autonomously.
4. remediation flow currently outputs permission-gated plans, not rollback-applied autonomous changes.
5. some workflow paths still rely on placeholder/default inputs when upstream artifacts are absent.
6. enterprise tenancy, policy partitioning, and large-scale runtime scheduling controls are not yet implemented.
