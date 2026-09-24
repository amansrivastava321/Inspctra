# Sample Apps

Benchmark inputs are resolved from `sample_apps/` and can be run as:

1. single app benchmark root (contains `expected_issues.json`)
2. multi-app directory

Current benchmark profile mapping in `BenchmarkRunner` includes:

1. `vulnerable_fastapi_app` → `api`
2. `react_dashboard_app` → `web`
3. `ecommerce_web_app` → `full_stack`
4. `sync_conflict_demo` → `api`
5. `flutter_offline_app` → `flutter`

Each benchmark run writes per-app artifacts under benchmark output directories and contributes to summary metrics.
