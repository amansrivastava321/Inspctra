# QA-AI

![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)

QA-AI is a contract-driven autonomous software audit and continuous improvement platform.

## Active frontend

The active frontend is in `apps/inspectra_ui/`.

The old `frontend/` directory has been archived to `archive/frontend-deprecated/`.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

PDF exports use WeasyPrint, which also needs the native Pango runtime. On
macOS, install it with `brew install pango` if it is not already present.

Run CLI:

```bash
python -m qa_ai.cli <command> [options]
```

Main commands:

- `audit`
- `report`
- `doctor`
- `profiles`
- `benchmark`
- `runtime-lab doctor`
- `distributed-runtime`
- `mobile-runtime`
- `ai-reasoning`
- `cicd`
- `performance`
- `ai-audit`
- `self-optimize`

## Architecture Docs

- [Architecture Overview](docs/architecture/overview.md)
- [Orchestration Model](docs/architecture/orchestration_model.md)
- [Artifact Contracts](docs/architecture/artifact_contracts.md)
- [Workflow Phases](docs/architecture/workflow_phases.md)
- [Graphify Usage](docs/architecture/graphify_usage.md)
- [Extension Guidelines](docs/architecture/extension_guidelines.md)

## Subsystem Docs

- [Runtime](docs/runtime/runtime_lab.md)
- [Distributed Runtime](docs/distributed_runtime/multi_actor_model.md)
- [Mobile Runtime](docs/mobile_runtime/mobile_runtime_overview.md)
- [AI Reasoning](docs/ai_reasoning/ai_reasoning_overview.md)
- [Controlled Remediation](docs/safety/remediation_safety_principles.md)
- [Improvement](docs/improvement/continuous_improvement_loop.md)
- [Benchmarking](docs/benchmarking/benchmark_framework.md)
- [Safety](docs/safety/permission_model.md)
- [Roadmap](docs/roadmap/current_capabilities.md)

## Controlled Remediation

Use controlled remediation orchestration (advisory-first, permission-gated):

```bash
python -m qa_ai.cli remediation artifacts/ --dry-run
python -m qa_ai.cli remediation artifacts/ --proposal-only
python -m qa_ai.cli remediation artifacts/ --approve FIX-001
python -m qa_ai.cli remediation artifacts/ --sandbox
```

## Controlled Remediation Runtime

Production-grade controlled remediation runtime (advisory-first, approval workflow, rollback-aware, sandboxed):

```bash
python -m qa_ai.cli remediation-runtime artifacts/ --dry-run
python -m qa_ai.cli remediation-runtime artifacts/ --proposal-only
python -m qa_ai.cli remediation-runtime artifacts/ --simulate
python -m qa_ai.cli remediation-runtime artifacts/ --sandbox
python -m qa_ai.cli remediation-runtime artifacts/ --approve FIX-001
```

Generated runtime artifacts:

- `patch_proposals.json`
- `remediation_change_simulation.json`
- `remediation_rollback_plan.json`
- `remediation_sandbox_report.json`
- `remediation_approval_workflow.json`
- `remediation_retest_scope.json`
- `remediation_validation_report.json`
- `remediation_audit_log.json`
- `remediation_runtime_summary.json`

Safety guarantees:

- advisory-first proposals only (no direct source edit by default)
- explicit approval workflow required before executable state
- rollback plan generated for every proposal
- sandbox simulation is dry-run and non-destructive by default
- retest scope optimization required before final decisioning
- deterministic evidence validation remains source-of-truth

## CI/CD Continuous Audit

Continuous audit and release-gate commands:

```bash
python -m qa_ai.cli cicd doctor
python -m qa_ai.cli cicd plan --provider github --dry-run
python -m qa_ai.cli cicd release-gate artifacts/
python -m qa_ai.cli audit ./target-app --profile full_stack --ci-mode
```

Safety defaults:

- advisory-first workflow plans
- dry-run support
- explicit approval required before overwriting CI files
- release-gate policy blocks critical findings, regressions, and missing evidence

## CI/CD Continuous Audit Runtime

Use runtime-grade CI/CD orchestration for provider detection, advisory workflow planning, incremental audits, policy checks, and PR-focused orchestration:

```bash
python -m qa_ai.cli cicd-runtime doctor
python -m qa_ai.cli cicd-runtime detect
python -m qa_ai.cli cicd-runtime plan --provider github --dry-run
python -m qa_ai.cli cicd-runtime release-gate artifacts/
python -m qa_ai.cli cicd-runtime pr-audit ./target-app
python -m qa_ai.cli audit ./target-app --profile full_stack --ci-mode
```

Supported providers:

- GitHub Actions
- GitLab CI
- Jenkins
- Azure Pipelines
- unknown/manual

Generated artifacts:

- `cicd_provider_report.json`
- `github_actions_plan.json`
- `gitlab_ci_plan.json`
- `jenkins_pipeline_plan.json`
- `incremental_audit_plan.json`
- `baseline_comparison_report.json`
- `release_gate_decision.json`
- `pipeline_policy_report.json`
- `pr_audit_report.json`
- `cicd_runtime_summary.json`
- `cicd_audit_log.json`

Safety guarantees:

- advisory-first CI workflow planning
- no automatic overwrite of existing CI files
- explicit permission required for any write/apply path
- release gates and policy validation block unsafe delivery conditions
- remediation approval gates remain enforced
- deterministic evidence remains source-of-truth

## AI-First Audit Orchestration

Run AI-first orchestration with deterministic safety guarantees:

```bash
python -m qa_ai.cli ai-audit ./target-app --profile full_stack
python -m qa_ai.cli audit ./target-app --profile full_stack --ai-first
python -m qa_ai.cli benchmark sample_apps/ --ai-first
```

Safety defaults:

- AI decisions are logged with source artifacts and confidence
- deterministic engines still execute/validate evidence
- no evidence-backed claim is promoted without references
- no unrestricted remediation is triggered by AI orchestration

## Specialist Cloud-First Model Routing

QA-AI now supports component/function-based specialist routing with deterministic safety fallback.

Routing mode:

- `QA_AI_MODEL_ROUTING_MODE=specialist_cloud_first`
- Chain: specialist OpenRouter model -> local Ollama fallback -> deterministic fallback

Component routing table:

- `master_orchestration`: `nousresearch/hermes-3-llama-3.1-405b:free` -> `qwen3.5:9b`
- `huge_repo_reasoning`: `deepseek/deepseek-v4-flash:free` -> `deepseek-r1:7b` -> `qwen3.5:9b`
- `structured_reasoning`: `openai/gpt-oss-120b:free` -> `qwen3.5:9b`
- `long_strategy`: `arcee-ai/trinity-large-thinking:free` -> `deepseek-r1:7b`
- `report_synthesis`: `google/gemma-4-31b-it:free` -> local gemma
- `visual_analysis`: local `qwen2.5vl:7b` first, optional cloud backup `google/gemma-4-31b-it:free`
- `embeddings`: local `bge-m3` only

OpenRouter configuration:

```bash
export QA_AI_ALLOW_CLOUD_MODELS=true
export QA_AI_OPENROUTER_API_KEY=...
export QA_AI_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
export QA_AI_OPENROUTER_TIMEOUT_SECONDS=45
export QA_AI_OPENROUTER_LONG_TIMEOUT_SECONDS=180
```

Privacy/safety configuration:

```bash
export QA_AI_PRIVATE_CODE_MODE=true
export QA_AI_REDACT_CLOUD_CONTEXT=true
export QA_AI_REQUIRE_CLOUD_PERMISSION_FOR_PRIVATE_CODE=true
```

Model routing CLI:

```bash
python -m qa_ai.cli models doctor
python -m qa_ai.cli models routing artifacts/
python -m qa_ai.cli models test --component master_orchestration --output-dir artifacts/
python -m qa_ai.cli models privacy-check --output-dir artifacts/
```

## Corpus Connection Workflow

Inspectra now uses permission-based Corpus connection requests (no direct auto-register/connect).

1. Detect local runtime.
2. Show `Connect to Corpus` in Settings -> Integrations -> Corpus.
3. Request connection approval from Corpus.
4. Wait for user approval/denial.
5. Persist approved session in `integrations/corpus_session.json`.
6. Start signal/checkpoint communication only after approval.

UI route:

- `/settings/integrations/corpus`

Integration API routes:

- `GET /api/integrations/corpus/status`
- `POST /api/integrations/corpus/request-connection`
- `POST /api/integrations/corpus/check-approval`
- `POST /api/integrations/corpus/reconnect`
- `POST /api/integrations/corpus/disconnect`
- `GET /api/integrations/corpus/signals/consult-next`
- `POST /api/integrations/corpus/signals/interrupt`
- `POST /api/integrations/corpus/checkpoints/{checkpoint_id}/evaluate`

## Scalability and Performance Hardening

Use performance tooling for workflow profiling, artifact lifecycle planning, evidence growth analysis, and scalability reporting:

```bash
python -m qa_ai.cli performance doctor
python -m qa_ai.cli performance profile artifacts/
python -m qa_ai.cli performance lifecycle-plan artifacts/
python -m qa_ai.cli performance evidence-storage artifacts/
python -m qa_ai.cli performance scalability-report
```

Generated artifacts:

- `performance_profile.json`
- `workflow_timing_report.json`
- `artifact_cache_report.json`
- `artifact_lifecycle_plan.json`
- `evidence_storage_report.json`
- `incremental_graph_plan.json`
- `parallel_execution_plan.json`
- `memory_usage_report.json`
- `scalability_report.json`

Safety defaults:

- lifecycle planning does not delete artifacts by default
- evidence storage optimizer is analysis-only (no automatic cleanup)
- parallel execution planning is advisory only and does not change runtime behavior
- incremental graph planning is advisory-only and requires explicit execution approval
- no automatic deletion/compression is performed by performance tooling

## Enterprise Governance Layer

Use local governance runtime for workspace isolation, project/team registries, RBAC decisions, policy validation, and audit history:

```bash
python -m qa_ai.cli enterprise doctor
python -m qa_ai.cli enterprise workspaces
python -m qa_ai.cli enterprise governance-report
python -m qa_ai.cli enterprise audit-history
```

Generated artifacts:

- `workspace_registry.json`
- `project_registry.json`
- `team_registry.json`
- `role_access_report.json`
- `governance_policy_report.json`
- `audit_history_index.json`
- `governance_summary.json`
- `governance_access_log.json`
- `enterprise_runtime_summary.json`

Safety guarantees:

- workspace isolation is local filesystem only
- RBAC is advisory-first and file-backed
- no external auth provider integration
- immutable access audit logs with hash chain
- no destructive governance operations by default

## Benchmark Intelligence Expansion

Use benchmark intelligence runtime for comparative scoring, false-positive tracking, maturity scoring, and trend analysis:

```bash
python -m qa_ai.cli benchmark-intelligence datasets
python -m qa_ai.cli benchmark-intelligence scoring
python -m qa_ai.cli benchmark-intelligence maturity
python -m qa_ai.cli benchmark-intelligence trends
```

Generated artifacts:

- `benchmark_dataset_registry.json`
- `benchmark_scoring_report.json`
- `false_positive_report.json`
- `benchmark_coverage_trend.json`
- `benchmark_comparison_report.json`
- `benchmark_maturity_score.json`
- `benchmark_history_index.json`
- `benchmark_intelligence_summary.json`
- `benchmark_runtime_summary.json`

Safety guarantees:

- benchmark execution and planning remain sandboxed/advisory-first
- no automatic external uploads
- deterministic artifact evidence remains source-of-truth

## Self-Optimizing Audit Intelligence

Run artifact-backed self-optimization across audit memory, strategy adaptation, deduplication, confidence calibration, evidence quality, scenario tuning, risk prediction, remediation learning, and local cross-project learning:

```bash
python -m qa_ai.cli self-optimize artifacts/
python -m qa_ai.cli self-optimize artifacts/ --workspace default
python -m qa_ai.cli self-optimize artifacts/ --cross-project
python -m qa_ai.cli audit ./target-app --profile full_stack --self-optimize
python -m qa_ai.cli benchmark sample_apps/ --self-optimize
```

Generated artifacts:

- `audit_memory_index.json`
- `strategy_adaptation_plan.json`
- `finding_deduplication_report.json`
- `confidence_calibration_report.json`
- `evidence_quality_optimization.json`
- `scenario_optimization_report.json`
- `risk_prediction_report.json`
- `remediation_learning_report.json`
- `cross_project_learning_report.json`
- `self_optimization_summary.json`

Safety guarantees:

- learning is artifact-backed and deterministic-evidence-linked
- outputs are advisory-only by default
- no automatic source code modification
- no external upload or cloud learning
- deterministic validation remains source-of-truth

## Profiles

Default profile mapping is defined at:

- `qa_ai/config/default_profiles.yaml`

## Environment Variables

All runtime settings can be configured via environment variables. The platform uses safe defaults so no variables need to be set for local development.

| Variable | Default | Description |
|----------|---------|-------------|
| `QA_AI_OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL for the Ollama LLM server |
| `QA_AI_APP_BASE_URL` | `http://localhost:3000` | Base URL of the web application under test |
| `QA_AI_API_BASE_URL` | `http://localhost:8000` | Base URL of the API server under test |
| `QA_AI_ARTIFACT_DIR` | `artifacts` | Directory for storing audit artifacts |
| `QA_AI_LLM_TIMEOUT_SECONDS` | `120` | Default LLM request timeout in seconds |
| `QA_AI_LLM_LONG_TIMEOUT_SECONDS` | `300` | Timeout for deep-reasoning LLM requests |
| `QA_AI_LLM_HEALTH_CHECK_TIMEOUT` | `2.0` | Timeout for Ollama availability checks |
| `QA_AI_ENABLE_LIVE_RUNTIME` | `false` | Enable live browser execution (Playwright) |
| `QA_AI_ENABLE_MOBILE_RUNTIME` | `false` | Enable mobile device testing runtime |
| `QA_AI_ENABLE_DISTRIBUTED_RUNTIME` | `false` | Enable distributed execution runtime |
| `QA_AI_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Example

```bash
export QA_AI_OLLAMA_BASE_URL="http://my-llm-server:11434"
export QA_AI_APP_BASE_URL="http://staging.example.com"
export QA_AI_LLM_TIMEOUT_SECONDS="60"
export QA_AI_LOG_LEVEL="DEBUG"
python -m qa_ai audit --url http://staging.example.com
```
