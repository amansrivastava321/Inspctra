from pathlib import Path


REQUIRED_DOCS = [
    "docs/architecture/overview.md",
    "docs/architecture/orchestration_model.md",
    "docs/architecture/artifact_contracts.md",
    "docs/architecture/workflow_phases.md",
    "docs/architecture/graphify_usage.md",
    "docs/architecture/extension_guidelines.md",
    "docs/runtime/runtime_lab.md",
    "docs/runtime/live_execution.md",
    "docs/runtime/replay_and_tracing.md",
    "docs/runtime/evidence_model.md",
    "docs/distributed_runtime/multi_actor_model.md",
    "docs/distributed_runtime/concurrency_simulation.md",
    "docs/distributed_runtime/sync_conflict_testing.md",
    "docs/distributed_runtime/chaos_safety.md",
    "docs/mobile_runtime/mobile_runtime_overview.md",
    "docs/mobile_runtime/device_registry.md",
    "docs/mobile_runtime/flutter_execution_planning.md",
    "docs/mobile_runtime/mobile_safety_model.md",
    "docs/ai_reasoning/ai_reasoning_overview.md",
    "docs/ai_reasoning/deterministic_first_principle.md",
    "docs/ai_reasoning/evidence_linked_reasoning.md",
    "docs/ai_reasoning/adaptive_audit_planning.md",
    "docs/improvement/continuous_improvement_loop.md",
    "docs/improvement/software_health_model.md",
    "docs/improvement/fix_planning_and_retesting.md",
    "docs/improvement/regression_guard.md",
    "docs/benchmarking/benchmark_framework.md",
    "docs/benchmarking/sample_apps.md",
    "docs/benchmarking/metrics.md",
    "docs/safety/permission_model.md",
    "docs/safety/dry_run_policy.md",
    "docs/safety/destructive_action_policy.md",
    "docs/safety/remediation_safety_principles.md",
    "docs/roadmap/completed_phases.md",
    "docs/roadmap/current_capabilities.md",
    "docs/roadmap/remaining_limitations.md",
    "docs/roadmap/next_phases.md",
]


def test_required_docs_exist() -> None:
    missing = [path for path in REQUIRED_DOCS if not Path(path).exists()]
    assert not missing, f"Missing documentation files: {missing}"
