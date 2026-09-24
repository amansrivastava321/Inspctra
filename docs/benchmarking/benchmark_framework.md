# Benchmark Framework

QA-AI benchmarking executes controlled audit workflows against sample apps and computes detection quality metrics.

## Execution

`BenchmarkRunner`:

1. discovers sample apps
2. runs safe benchmark phase set via `WorkflowEngine`
3. aggregates per-app findings/runtime/replay/regression results

## Reporting pipeline

1. `DetectionMetrics` computes coverage/false-positive/duplicate/runtime/evidence metrics.
2. `BenchmarkReport` persists `benchmark_summary`, `benchmark_metrics`, and HTML report.

## Runtime extensions

`AuditCommand.run_benchmark` can route benchmark through runtime-lab live mode, distributed runtime, mobile runtime, and optional AI reasoning summaries.
