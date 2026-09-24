"""
main.py - QA-AI / Inspectra CLI entrypoint.

Commands:
  version           Show version information
  init              Initialise a new QA-AI project
  audit             Run end-to-end audit
  dashboard         Start local web dashboard
  doctor            Check environment readiness
  report            Regenerate reports from artifacts
  profiles          List audit profiles
  ai-audit          AI-first audit orchestration
  remediation       Controlled remediation planning
  remediation-runtime  Full remediation runtime
  cicd              CI/CD continuous audit operations
  cicd-runtime      CI/CD runtime operations
  self-optimize     Self-optimizing audit intelligence
  ... (run --help for the full list)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from qa_ai.cli.audit_command import AuditCommand
from qa_ai.cli.profile_manager import ProfileManager
from qa_ai.cli.formatter import (
    print_version,
    print_init_result,
    print_audit_summary,
    print_doctor_report,
    print_result,
    print_dashboard_starting,
)

__version__ = "1.0.0"


def _config_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "config"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qa_ai",
        description="Inspectra QA-AI — autonomous software quality platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Quick start:\n"
            "  qa_ai init                         Set up a new project\n"
            "  qa_ai audit ./my-app --profile api  Run an audit\n"
            "  qa_ai dashboard artifacts/          Open the dashboard\n"
            "  qa_ai doctor                        Check environment\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── meta ──────────────────────────────────────────────────────────────────
    subparsers.add_parser("version", help="Show version information")

    init_p = subparsers.add_parser("init", help="Initialise a new QA-AI project in the current directory")
    init_p.add_argument("--dir", default=".", help="Project root directory (default: current directory)")

    dashboard_p = subparsers.add_parser("dashboard", help="Start the local web dashboard")
    dashboard_p.add_argument("artifacts_dir", nargs="?", default="artifacts",
                             help="Artifacts directory to serve (default: artifacts/)")
    dashboard_p.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    dashboard_p.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")

    audit = subparsers.add_parser("audit", help="Run end-to-end audit")
    audit.add_argument("target_path", help="Path to target app/repository")
    audit.add_argument("--profile", default="web", help="Audit profile name")
    audit.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    audit.add_argument("--dry-run", action="store_true", help="Plan-only run without executing workflow")
    audit.add_argument("--ai-reasoning", action="store_true", help="Run AI reasoning layer after deterministic audit")
    audit.add_argument("--ci-mode", action="store_true", help="Enable CI/CD continuous audit phases")
    audit.add_argument("--ai-first", action="store_true", help="Enable AI-first audit orchestration layer")
    audit.add_argument("--self-optimize", action="store_true", help="Run self-optimization intelligence after audit")

    ai_audit = subparsers.add_parser("ai-audit", help="Run AI-first audit orchestration")
    ai_audit.add_argument("target_path", help="Path to target app/repository")
    ai_audit.add_argument("--profile", default="full_stack", help="Audit profile name")
    ai_audit.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    ai_audit.add_argument("--dry-run", action="store_true", help="Plan-only run without executing workflow")

    report = subparsers.add_parser("report", help="Regenerate reports from artifacts")
    report.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")

    doctor = subparsers.add_parser("doctor", help="Check environment readiness")
    doctor.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    benchmark = subparsers.add_parser("benchmark", help="Run sample app benchmarking")
    benchmark.add_argument("sample_root", help="Path to sample_apps/ root")
    benchmark.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    benchmark.add_argument(
        "--execute",
        action="store_true",
        help="Enable execution-oriented benchmark phases when environment allows",
    )
    benchmark.add_argument("--live", action="store_true", help="Run benchmark through runtime lab live flow")
    benchmark.add_argument("--dry-run", action="store_true", help="Plan live runtime-lab flow without launching")
    benchmark.add_argument("--distributed", action="store_true", help="Run distributed runtime layer")
    benchmark.add_argument("--mobile", action="store_true", help="Run mobile runtime layer")
    benchmark.add_argument("--ai-reasoning", action="store_true", help="Run AI reasoning layer after benchmark flow")
    benchmark.add_argument("--ai-first", action="store_true", help="Enable AI-first orchestration during benchmark flow")
    benchmark.add_argument("--self-optimize", action="store_true", help="Run self-optimization intelligence after benchmark flow")

    runtime_lab = subparsers.add_parser("runtime-lab", help="Runtime lab operations")
    runtime_lab_sub = runtime_lab.add_subparsers(dest="runtime_lab_command", required=True)
    runtime_lab_doctor = runtime_lab_sub.add_parser("doctor", help="Check runtime-lab environment readiness")
    runtime_lab_doctor.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    distributed = subparsers.add_parser("distributed-runtime", help="Run distributed runtime simulation")
    distributed.add_argument("sample_path", help="Path to app/sample for distributed runtime")
    distributed.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    distributed.add_argument("--dry-run", action="store_true", help="Run distributed runtime in simulation mode")
    distributed.add_argument(
        "--actors",
        default="",
        help="Comma-separated actor roles (e.g. cashier,manager,background_sync)",
    )

    mobile_runtime = subparsers.add_parser("mobile-runtime", help="Run mobile runtime operations")
    mobile_runtime.add_argument("target", nargs="?", default="doctor", help="doctor or path to mobile sample app")
    mobile_runtime.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    mobile_runtime.add_argument("--dry-run", action="store_true", help="Run mobile runtime in simulation mode")
    mobile_runtime.add_argument("--distributed", action="store_true", help="Enable distributed actor/session flow")

    ai_reasoning = subparsers.add_parser("ai-reasoning", help="Run AI reasoning over existing artifacts")
    ai_reasoning.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")
    ai_reasoning.add_argument("--dry-run", action="store_true", help="Force deterministic fallback mode")

    remediation = subparsers.add_parser("remediation", help="Run controlled remediation planning")
    remediation.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")
    remediation.add_argument("--dry-run", action="store_true", help="Run remediation in non-applying mode")
    remediation.add_argument("--proposal-only", action="store_true", help="Generate patch proposals only")
    remediation.add_argument(
        "--approve",
        action="append",
        default=[],
        help="Approve a fix id for controlled sandbox apply planning (repeatable)",
    )
    remediation.add_argument("--sandbox", action="store_true", help="Enable sandbox materialization mode")

    remediation_runtime = subparsers.add_parser("remediation-runtime", help="Run full controlled remediation runtime")
    remediation_runtime.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")
    remediation_runtime.add_argument("--dry-run", action="store_true", help="Run runtime in non-applying mode")
    remediation_runtime.add_argument("--proposal-only", action="store_true", help="Generate patch proposals only")
    remediation_runtime.add_argument("--simulate", action="store_true", help="Run proposal + simulation + rollback planning only")
    remediation_runtime.add_argument("--sandbox", action="store_true", help="Enable sandbox execution-planning mode")
    remediation_runtime.add_argument(
        "--approve",
        action="append",
        default=[],
        help="Approve a fix id for remediation approval workflow (repeatable)",
    )

    cicd = subparsers.add_parser("cicd", help="Run CI/CD continuous audit operations")
    cicd_sub = cicd.add_subparsers(dest="cicd_command", required=True)
    cicd_doctor = cicd_sub.add_parser("doctor", help="Detect CI provider and readiness")
    cicd_doctor.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    cicd_plan = cicd_sub.add_parser("plan", help="Generate CI workflow plan")
    cicd_plan.add_argument("--provider", choices=["auto", "github", "gitlab", "jenkins"], default="auto")
    cicd_plan.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    cicd_plan.add_argument("--dry-run", action="store_true", help="Plan without writing workflow files")
    cicd_plan.add_argument("--approve-overwrite", action="store_true", help="Explicitly approve overwriting existing CI files")

    cicd_gate = cicd_sub.add_parser("release-gate", help="Compute release gate decision from artifacts")
    cicd_gate.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")

    cicd_runtime = subparsers.add_parser("cicd-runtime", help="Run CI/CD continuous audit runtime operations")
    cicd_runtime_sub = cicd_runtime.add_subparsers(dest="cicd_runtime_command", required=True)
    cicd_runtime_doctor = cicd_runtime_sub.add_parser("doctor", help="Check CI/CD runtime detection readiness")
    cicd_runtime_doctor.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    cicd_runtime_detect = cicd_runtime_sub.add_parser("detect", help="Detect CI provider")
    cicd_runtime_detect.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    cicd_runtime_plan = cicd_runtime_sub.add_parser("plan", help="Generate advisory CI workflow plan")
    cicd_runtime_plan.add_argument("--provider", choices=["auto", "github", "gitlab", "jenkins", "azure"], default="auto")
    cicd_runtime_plan.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    cicd_runtime_plan.add_argument("--dry-run", action="store_true", help="Plan only")

    cicd_runtime_gate = cicd_runtime_sub.add_parser("release-gate", help="Evaluate runtime release gate from artifacts")
    cicd_runtime_gate.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")

    cicd_runtime_pr = cicd_runtime_sub.add_parser("pr-audit", help="Run PR-focused CI runtime audit orchestration")
    cicd_runtime_pr.add_argument("target_path", help="Path to target repo")
    cicd_runtime_pr.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    performance = subparsers.add_parser("performance", help="Run scalability/performance hardening operations")
    perf_sub = performance.add_subparsers(dest="performance_command", required=True)
    perf_doctor = perf_sub.add_parser("doctor", help="Inspect performance/scalability posture")
    perf_doctor.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    perf_profile = perf_sub.add_parser("profile", help="Generate performance profile from artifacts")
    perf_profile.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")
    perf_lifecycle = perf_sub.add_parser("lifecycle-plan", help="Generate artifact lifecycle plan")
    perf_lifecycle.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")
    perf_evidence = perf_sub.add_parser("evidence-storage", help="Generate evidence storage optimization plan")
    perf_evidence.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")
    perf_scalability = perf_sub.add_parser("scalability-report", help="Generate consolidated scalability report")
    perf_scalability.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    enterprise = subparsers.add_parser("enterprise", help="Run enterprise governance operations")
    enterprise_sub = enterprise.add_subparsers(dest="enterprise_command", required=True)
    enterprise_doctor = enterprise_sub.add_parser("doctor", help="Check local enterprise governance readiness")
    enterprise_doctor.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    enterprise_sub.add_parser("workspaces", help="Generate workspace registry")
    enterprise_sub.add_parser("governance-report", help="Generate enterprise governance summary")
    enterprise_sub.add_parser("audit-history", help="Generate enterprise audit history index")

    benchmark_intelligence = subparsers.add_parser("benchmark-intelligence", help="Run benchmark intelligence operations")
    bi_sub = benchmark_intelligence.add_subparsers(dest="benchmark_intelligence_command", required=True)
    bi_sub.add_parser("datasets", help="Generate benchmark dataset registry")
    bi_sub.add_parser("scoring", help="Generate benchmark scoring report")
    bi_sub.add_parser("maturity", help="Generate benchmark maturity score")
    bi_sub.add_parser("trends", help="Generate benchmark trend and comparison reports")

    self_optimize = subparsers.add_parser("self-optimize", help="Run self-optimizing audit intelligence pipeline")
    self_optimize.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")
    self_optimize.add_argument("--workspace", default="default", help="Workspace id/name context")
    self_optimize.add_argument("--cross-project", action="store_true", help="Enable local cross-project learning analysis")

    models = subparsers.add_parser("models", help="Inspect specialist cloud-first model routing")
    models_sub = models.add_subparsers(dest="models_command", required=True)
    models_doctor = models_sub.add_parser("doctor", help="Check model routing readiness")
    models_doctor.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    models_routing = models_sub.add_parser("routing", help="Show latest routing report")
    models_routing.add_argument("artifacts_dir", nargs="?", default="artifacts", help="Artifacts directory")
    models_test = models_sub.add_parser("test", help="Run routing test call for a component")
    models_test.add_argument("--component", required=True, help="Routing component label")
    models_test.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    models_privacy = models_sub.add_parser("privacy-check", help="Run private-code routing policy check")
    models_privacy.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    models_route = models_sub.add_parser("route", help="Show selected model route for a task")
    models_route.add_argument("--task", required=True,
                              help="Task name (e.g. ai_oracle, step_narration, vision_screen_analysis)")

    models_bench = models_sub.add_parser("benchmark", help="Run lightweight local model benchmark")
    models_bench.add_argument("--quick", action="store_true", default=True,
                              help="Quick mode: skip heavy models (default: True)")
    models_bench.add_argument("--allow-cloud", action="store_true", default=False,
                              help="Allow cloud providers in benchmark (default: False)")

    models_sub.add_parser("hardware", help="Detect hardware and show recommended profile")
    models_sub.add_parser("profiles", help="List all adaptive resource profiles")
    models_sub.add_parser("auto-profile", help="Auto-detect hardware and show full routing plan")

    models_disc = models_sub.add_parser("discover", help="Discover locally running LLM providers")
    models_disc.add_argument("--no-lmstudio", action="store_true", default=False)
    models_disc.add_argument("--no-llamacpp", action="store_true", default=False)

    models_apply = models_sub.add_parser("apply-profile", help="Apply a named adaptive profile")
    models_apply.add_argument("--profile", required=True,
                              help="Profile ID: low_ram_8gb|mac_m4_16gb|pro_32gb|workstation_64gb|remote_gpu")

    subparsers.add_parser("profiles", help="List available audit profiles")

    memory = subparsers.add_parser("memory", help="Memory kernel: stats, recall, patterns, retention")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    mem_stats = memory_sub.add_parser("stats", help="Show memory stats for a scope")
    mem_stats.add_argument("--scope", required=True, help="Scope ID")
    mem_report = memory_sub.add_parser("report", help="Generate memory scope report")
    mem_report.add_argument("--scope", required=True, help="Scope ID")
    mem_report.add_argument("--format", default="markdown", choices=["markdown", "json"], help="Output format")
    mem_patterns = memory_sub.add_parser("patterns", help="List patterns for a scope")
    mem_patterns.add_argument("--scope", required=True, help="Scope ID")
    mem_patterns.add_argument("--type", default=None, help="Filter by pattern_type")
    mem_patterns.add_argument("--min-confidence", type=float, default=0.0)
    mem_recall = memory_sub.add_parser("recall", help="Semantic recall for a query")
    mem_recall.add_argument("--scope", required=True, help="Scope ID")
    mem_recall.add_argument("--query", required=True, help="Query text")
    mem_recall.add_argument("--top-k", type=int, default=10)
    mem_retention = memory_sub.add_parser("retention", help="Preview or run retention cycle")
    mem_retention.add_argument("--scope", required=True, help="Scope ID")
    mem_retention.add_argument("--execute", action="store_true", help="Execute (not dry-run)")
    mem_retention.add_argument("--max-delete", type=int, default=500)
    mem_baseline = memory_sub.add_parser("baseline", help="Show active baseline for a scope")
    mem_baseline.add_argument("--scope", required=True, help="Scope ID")

    itest = subparsers.add_parser(
        "interactive-test",
        help="Run live interactive runtime testing against a real app",
    )
    itest.add_argument("--config", default=None, help="Path to interactive_runtime.yaml")
    itest.add_argument("--target", default=None, help="Override working_dir from config")
    itest.add_argument("--profile", default=None, help="App profile hint (flutter-macos, web, etc.)")
    itest.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    itest.add_argument("--dry-run", action="store_true", help="Validate config, show plan, do not launch")
    itest.add_argument("--no-permission", action="store_true", help="Skip permission prompts (CI mode)")
    itest.add_argument(
        "--live-guided",
        action="store_true",
        help="Enable live guided mode: print step narrative and write trace files",
    )
    itest.add_argument(
        "--ai-guided",
        action="store_true",
        help="Enable AI guidance layer: vision analysis, curiosity engine, AI oracle",
    )
    itest.add_argument(
        "--max-actions",
        type=int,
        default=None,
        help="Override max_actions from config",
    )

    # ── validate-runtime ──────────────────────────────────────────────────────
    vrun = subparsers.add_parser(
        "validate-runtime",
        help="Run Phase 2 validation pack against real apps",
    )
    vrun.add_argument(
        "--pack",
        required=True,
        help="Path to phase2_validation_pack.yaml",
    )
    vrun.add_argument("--dry-run", action="store_true", help="Inspect capabilities; do not launch apps")
    vrun.add_argument("--target", default=None, help="Run only this target_id")
    vrun.add_argument("--repeat", type=int, default=1, help="Run each target N times (repeatability)")
    vrun.add_argument("--max-actions", type=int, default=None, help="Override max_actions per target")
    vrun.add_argument("--output-dir", default="artifacts", help="Artifact output directory")
    vrun.add_argument("--require-approval", action="store_true", help="Force ask before every launch")
    vrun.add_argument("--no-external-calls", action="store_true", help="Block external calls for all targets")
    vrun.add_argument("--no-database", action="store_true", help="Disable database checks for all targets")
    vrun.add_argument("--screenshots", action="store_true", help="Override allow_screenshots=always")
    vrun.add_argument("--live-guided", action="store_true", help="Enable live guided mode")
    vrun.add_argument("--ai-guided", action="store_true", help="Enable AI guidance layer")
    vrun.add_argument("--auto-setup", action="store_true", help="Run runtime-doctor and fix issues before validation")
    vrun.add_argument("--setup-only", action="store_true", help="Run setup then stop (don't launch apps)")
    vrun.add_argument("--install-missing", action="store_true", help="Install missing Python packages after approval")
    vrun.add_argument("--install-appium", action="store_true",
                      help="Include Appium server install actions (npm install -g appium)")
    vrun.add_argument("--install-mobile-drivers", action="store_true",
                      help="Include Appium driver install actions (uiautomator2/xcuitest)")
    vrun.add_argument("--install-playwright", action="store_true",
                      help="Include Playwright install actions even if not web-targeted")
    vrun.add_argument("--install-vision-model", action="store_true",
                      help="Include ollama pull action for vision model if missing")
    vrun.add_argument("--create-venv", action="store_true", help="Create venv if none active")
    vrun.add_argument("--open-settings", action="store_true", help="Open OS settings for permission guidance")
    vrun.add_argument("--yes", action="store_true", help="Auto-approve safe (non-destructive) package installs")
    vrun.add_argument("--venv-path", default=".venv", help="Path for venv creation (default: .venv)")

    # ── runtime-doctor ────────────────────────────────────────────────────────
    rdoc = subparsers.add_parser(
        "runtime-doctor",
        help="Diagnose and fix Inspectra runtime environment",
    )
    rdoc.add_argument("--pack", default=None, help="Validate pack path (to check per-target requirements)")
    rdoc.add_argument("--config", default=None, help="Single interactive_runtime.yaml config path")
    rdoc.add_argument("--target", default=None, help="Target ID within pack to check")
    rdoc.add_argument("--auto-setup", action="store_true", help="Generate setup plan and ask for approval")
    rdoc.add_argument("--create-venv", action="store_true", help="Plan venv creation if none active")
    rdoc.add_argument("--venv-path", default=".venv", help="Venv path for creation plan")
    rdoc.add_argument("--install-missing", action="store_true", help="Install missing packages after approval")
    rdoc.add_argument("--install-appium", action="store_true",
                      help="Include Appium server install actions (npm install -g appium)")
    rdoc.add_argument("--install-mobile-drivers", action="store_true",
                      help="Include Appium driver install actions (uiautomator2/xcuitest)")
    rdoc.add_argument("--install-playwright", action="store_true",
                      help="Include Playwright install actions even if not web-targeted")
    rdoc.add_argument("--install-vision-model", action="store_true",
                      help="Include ollama pull action for vision model if missing")
    rdoc.add_argument("--open-settings", action="store_true", help="Open OS settings for permission guidance")
    rdoc.add_argument("--yes", action="store_true", help="Auto-approve safe package installs")
    rdoc.add_argument("--dry-run", action="store_true", help="Show plan only — no changes")
    rdoc.add_argument("--output-dir", default="artifacts", help="Artifact output directory")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = ProfileManager(_config_dir())
    command = AuditCommand(profile_manager=manager)

    if args.command == "version":
        print_version(__version__)
        return 0

    if args.command == "init":
        result = _run_init(getattr(args, "dir", "."))
        print_init_result(result)
        return 0

    if args.command == "dashboard":
        _run_dashboard(
            artifacts_dir=args.artifacts_dir,
            host=args.host,
            port=args.port,
        )
        return 0

    if args.command == "profiles":
        for name in manager.list_profiles():
            print(name)
        return 0

    if args.command == "audit":
        result = command.run(
            target_path=args.target_path,
            profile=args.profile,
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run),
            ai_reasoning=bool(args.ai_reasoning),
            ci_mode=bool(args.ci_mode),
            ai_first=bool(args.ai_first),
        )
        if bool(args.self_optimize) and result.get("status") != "failed":
            result["self_optimization"] = command.run_self_optimize(
                artifacts_dir=args.output_dir,
                workspace="default",
                cross_project=False,
            )
        print_audit_summary(result)
        return 0 if result.get("status") != "failed" else 2

    if args.command == "ai-audit":
        result = command.run_ai_audit(
            target_path=args.target_path,
            profile=args.profile,
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run),
        )
        print_audit_summary(result)
        return 0 if result.get("status") != "failed" else 2

    if args.command == "report":
        result = command.run_report(artifacts_dir=args.artifacts_dir)
        print_result(result, command="report")
        return 0

    if args.command == "doctor":
        result = command.run_doctor(output_dir=args.output_dir)
        print_doctor_report(result)
        return 0 if result.get("status") == "ok" else 1

    if args.command == "benchmark":
        result = command.run_benchmark(
            sample_root=args.sample_root,
            output_dir=args.output_dir,
            execute=bool(args.execute),
            live=bool(args.live),
            dry_run=bool(args.dry_run),
            distributed=bool(args.distributed),
            mobile=bool(args.mobile),
            ai_reasoning=bool(args.ai_reasoning),
            ai_first=bool(args.ai_first),
        )
        if bool(args.self_optimize) and result.get("status") == "ok":
            result["self_optimization"] = command.run_self_optimize(
                artifacts_dir=args.output_dir,
                workspace="default",
                cross_project=False,
            )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "runtime-lab" and args.runtime_lab_command == "doctor":
        result = command.run_runtime_lab_doctor(output_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "distributed-runtime":
        actor_list = [item.strip() for item in str(args.actors).split(",") if item.strip()]
        result = command.run_distributed_runtime(
            sample_path=args.sample_path,
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run),
            actors=actor_list or None,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "mobile-runtime":
        if str(args.target) == "doctor":
            result = command.run_mobile_runtime_doctor(output_dir=args.output_dir)
            print(json.dumps(result, indent=2, default=str))
            return 0 if result.get("status") == "ok" else 1
        result = command.run_mobile_runtime(
            sample_path=args.target,
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run),
            distributed=bool(args.distributed),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "ai-reasoning":
        result = command.run_ai_reasoning(artifacts_dir=args.artifacts_dir, dry_run=bool(args.dry_run))
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "remediation":
        result = command.run_remediation(
            artifacts_dir=args.artifacts_dir,
            dry_run=bool(args.dry_run),
            proposal_only=bool(args.proposal_only),
            approve_fix_ids=list(args.approve or []),
            sandbox=bool(args.sandbox),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "remediation-runtime":
        result = command.run_remediation_runtime(
            artifacts_dir=args.artifacts_dir,
            dry_run=bool(args.dry_run),
            proposal_only=bool(args.proposal_only),
            simulate=bool(args.simulate),
            sandbox=bool(args.sandbox),
            approve_fix_ids=list(args.approve or []),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "cicd" and args.cicd_command == "doctor":
        result = command.run_cicd_doctor(output_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "cicd" and args.cicd_command == "plan":
        result = command.run_cicd_plan(
            provider=args.provider,
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run),
            approve_overwrite=bool(args.approve_overwrite),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "cicd" and args.cicd_command == "release-gate":
        result = command.run_cicd_release_gate(artifacts_dir=args.artifacts_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "cicd-runtime" and args.cicd_runtime_command == "doctor":
        result = command.run_cicd_runtime_doctor(output_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "cicd-runtime" and args.cicd_runtime_command == "detect":
        result = command.run_cicd_runtime_detect(output_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "cicd-runtime" and args.cicd_runtime_command == "plan":
        result = command.run_cicd_runtime_plan(
            provider=args.provider,
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "cicd-runtime" and args.cicd_runtime_command == "release-gate":
        result = command.run_cicd_runtime_release_gate(artifacts_dir=args.artifacts_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "cicd-runtime" and args.cicd_runtime_command == "pr-audit":
        result = command.run_cicd_runtime_pr_audit(
            target_path=args.target_path,
            output_dir=args.output_dir,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "performance" and args.performance_command == "doctor":
        result = command.run_performance_doctor(output_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "performance" and args.performance_command == "profile":
        result = command.run_performance_profile(artifacts_dir=args.artifacts_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "performance" and args.performance_command == "lifecycle-plan":
        result = command.run_performance_lifecycle_plan(artifacts_dir=args.artifacts_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "performance" and args.performance_command == "evidence-storage":
        result = command.run_performance_evidence_storage(artifacts_dir=args.artifacts_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "performance" and args.performance_command == "scalability-report":
        result = command.run_scalability_report(output_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "enterprise" and args.enterprise_command == "doctor":
        result = command.run_enterprise_doctor(output_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "enterprise" and args.enterprise_command == "workspaces":
        result = command.run_enterprise_workspaces()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "enterprise" and args.enterprise_command == "governance-report":
        result = command.run_enterprise_governance_report()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "enterprise" and args.enterprise_command == "audit-history":
        result = command.run_enterprise_audit_history()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "benchmark-intelligence" and args.benchmark_intelligence_command == "datasets":
        result = command.run_benchmark_intelligence_datasets()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "benchmark-intelligence" and args.benchmark_intelligence_command == "scoring":
        result = command.run_benchmark_intelligence_scoring()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "benchmark-intelligence" and args.benchmark_intelligence_command == "maturity":
        result = command.run_benchmark_intelligence_maturity()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "benchmark-intelligence" and args.benchmark_intelligence_command == "trends":
        result = command.run_benchmark_intelligence_trends()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "self-optimize":
        result = command.run_self_optimize(
            artifacts_dir=args.artifacts_dir,
            workspace=args.workspace,
            cross_project=bool(args.cross_project),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "doctor":
        result = command.run_models_doctor(output_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "routing":
        result = command.run_models_routing(artifacts_dir=args.artifacts_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "test":
        result = command.run_models_test(component=args.component, artifacts_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "privacy-check":
        result = command.run_models_privacy_check(artifacts_dir=args.output_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "route":
        result = command.run_models_route(task=args.task)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "benchmark":
        result = command.run_models_benchmark(
            quick=getattr(args, "quick", True),
            allow_cloud=getattr(args, "allow_cloud", False),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "hardware":
        result = command.run_models_hardware()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "profiles":
        result = command.run_models_list_profiles()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "auto-profile":
        result = command.run_models_auto_profile()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "discover":
        result = command.run_models_discover(
            probe_lmstudio=not getattr(args, "no_lmstudio", False),
            probe_llamacpp=not getattr(args, "no_llamacpp", False),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "models" and args.models_command == "apply-profile":
        result = command.run_models_apply_profile(profile_id=args.profile)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "memory":
        result = command.run_memory_command(args)
        if isinstance(result, str):
            print(result)
            return 0
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "ok" else 1

    if args.command == "interactive-test":
        return _run_interactive_test(args)

    if args.command == "validate-runtime":
        return _run_validate_runtime(args)

    if args.command == "runtime-doctor":
        return _run_runtime_doctor(args)

    return 2


# ── helpers ────────────────────────────────────────────────────────────────────

def _run_init(project_dir: str = ".") -> dict:
    """Initialise a new QA-AI project structure."""
    import uuid
    root = Path(project_dir).expanduser().resolve()
    created = []

    dirs = [
        root / "artifacts",
        root / "qa_ai" / "config",
    ]
    for d in dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d.relative_to(root)))

    # Write a minimal .qa_ai config if missing
    config_file = root / ".qa_ai"
    if not config_file.exists():
        import json as _json
        config_file.write_text(
            _json.dumps({
                "project_id": uuid.uuid4().hex[:12],
                "created_at": __import__("datetime").datetime.now().isoformat(),
                "version": __version__,
            }, indent=2),
            encoding="utf-8",
        )
        created.append(".qa_ai")

    return {
        "status": "ok",
        "project_dir": str(root),
        "created": created,
        "version": __version__,
    }


def _run_dashboard(artifacts_dir: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the local web dashboard."""
    try:
        from qa_ai.webapp.server import create_app
        import uvicorn
        artifacts_path = Path(artifacts_dir).expanduser().resolve()
        print_dashboard_starting(host, port, str(artifacts_path))
        app = create_app(artifacts_dir=str(artifacts_path))
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except ImportError as e:
        print(f"Dashboard unavailable: {e}")
        print("Install dependencies: pip install fastapi uvicorn")
        raise SystemExit(1)


def _run_interactive_test(args) -> int:  # type: ignore[no-untyped-def]
    """Handle the interactive-test CLI command."""
    import json as _json
    from qa_ai.interactive_runtime.config_loader import load_config, validate_config

    # Load config
    try:
        config = load_config(getattr(args, "config", None))
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    # Override working_dir from CLI
    if getattr(args, "target", None):
        config.working_dir = args.target

    # Override output dir
    output_dir = getattr(args, "output_dir", "artifacts")
    config.output_dir = output_dir

    dry_run = bool(getattr(args, "dry_run", False))
    interactive = not bool(getattr(args, "no_permission", False))
    live_guided = bool(getattr(args, "live_guided", False))
    ai_guided = bool(getattr(args, "ai_guided", False))
    max_actions_override = getattr(args, "max_actions", None)

    # Apply CLI overrides to config
    if max_actions_override is not None and max_actions_override > 0:
        config.max_actions = max_actions_override

    # Apply live_guided / ai_guided flags to ai_runtime config
    if live_guided or ai_guided:
        from qa_ai.interactive_runtime.schemas import (
            AIRuntimeConfig, AIGuidanceConfig, LiveGuidedConfig, CuriosityConfig,
        )
        ai_cfg = config.ai_runtime or AIRuntimeConfig()
        if live_guided:
            ai_cfg.live_guided = LiveGuidedConfig(
                enabled=True, print_steps=True,
                write_markdown_trace=True, write_json_trace=True,
            )
        if ai_guided:
            ai_cfg.ai_guidance = AIGuidanceConfig(
                enabled=True, allow_cloud=False,
                require_approval_for_ai_calls=True,
            )
            ai_cfg.curiosity = CuriosityConfig(enabled=True, max_actions=config.max_actions)
        config.ai_runtime = ai_cfg

    # Validate config
    validation = validate_config(config)
    if not validation["valid"]:
        print("[ERROR] Config validation failed:")
        for err in validation["errors"]:
            print(f"  - {err}")
        return 1

    if validation["warnings"]:
        for w in validation["warnings"]:
            print(f"[WARN] {w}")

    if dry_run:
        return _dry_run_report(config, validation)

    # Live run
    return _live_interactive_test(config, output_dir, interactive)


def _dry_run_report(config, validation: dict) -> int:  # type: ignore[no-untyped-def]
    """Print dry-run plan without launching anything."""
    from qa_ai.interactive_runtime.app_launcher import AppLauncher
    from qa_ai.interactive_runtime.screen_observer import ScreenObserver

    print("\n" + "=" * 60)
    print("INTERACTIVE TEST DRY-RUN")
    print("=" * 60)
    print(f"  App Name     : {config.app_name}")
    print(f"  App Type     : {config.app_type}")
    print(f"  Working Dir  : {config.working_dir}")
    print(f"  Launch Cmd   : {config.launch_command}")

    # Show automation backend info
    try:
        from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory
        from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector
        from qa_ai.interactive_runtime.schemas import AutomationBackend
        import json as _json
        import os as _os
        import pathlib as _pathlib

        platform_name = CapabilityDetector.current_platform()
        playwright_ok = CapabilityDetector.playwright_available()
        driver = DriverFactory.create(config.app_type.value, config)
        driver_caps = driver.capabilities()

        print(f"  Automation Backend : {driver_caps.backend.value}")
        print(f"  Driver Status      : {driver_caps.status.value}")
        print(f"  Platform           : {platform_name}")
        print(f"  Playwright         : {'available' if playwright_ok else 'not found'}")
        if driver_caps.can_observe_screen:
            print(f"  Screen Observation : supported")
        if driver_caps.can_click:
            print(f"  Click/Type         : supported")
        if driver_caps.can_screenshot:
            print(f"  Screenshots        : supported")
        if driver_caps.missing_dependencies:
            print(f"  Missing deps       : {', '.join(driver_caps.missing_dependencies)}")
        if driver_caps.setup_instructions:
            print("  Setup required:")
            for instr in driver_caps.setup_instructions[:3]:
                print(f"    • {instr}")
        if platform_name == 'macos' and driver_caps.backend == AutomationBackend.MACOS_ACCESSIBILITY:
            perm_ok = CapabilityDetector.macos_accessibility_permission()
            perm = 'granted' if perm_ok else 'DENIED — enable in System Settings → Privacy → Accessibility'
            print(f"  Accessibility Perm : {perm}")

        # Write driver_capabilities.json
        try:
            out_path = _pathlib.Path(config.output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            caps_data = driver_caps.model_dump()
            caps_data["platform"] = platform_name
            caps_data["app_type"] = config.app_type.value if hasattr(config.app_type, "value") else str(config.app_type)
            caps_data["dry_run"] = True
            (out_path / "driver_capabilities.json").write_text(
                _json.dumps(caps_data, indent=2, default=str), encoding="utf-8"
            )
        except Exception:
            pass
    except Exception:
        pass

    print(f"  Max Actions  : {config.max_actions}")
    print(f"  Max Duration : {config.max_duration_seconds}s")
    print(f"  Output Dir   : {config.output_dir}")
    print()

    # AI capability status
    ai_cfg = config.ai_runtime
    print("AI Guidance:")
    if ai_cfg and ai_cfg.ai_guidance.enabled:
        print(f"  AI Guidance     : ENABLED  provider={ai_cfg.ai_guidance.provider}  model={ai_cfg.ai_guidance.model}")
        print(f"  Cloud allowed   : {ai_cfg.ai_guidance.allow_cloud}")
        print(f"  Approval for AI : {ai_cfg.ai_guidance.require_approval_for_ai_calls}")
    else:
        print("  AI Guidance     : DISABLED  (pass --ai-guided to enable)")
    if ai_cfg and ai_cfg.vision_analysis.enabled:
        print(f"  Vision Analyzer : ENABLED  model={ai_cfg.vision_analysis.model}")
        # Check if Ollama is reachable
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
            print("  Ollama          : reachable ✓")
        except Exception:
            print("  Ollama          : NOT REACHABLE — vision analysis will fall back to accessibility tree")
    else:
        print("  Vision Analyzer : DISABLED  (no vision model configured — will use accessibility tree)")
    if ai_cfg and ai_cfg.live_guided.enabled:
        print("  Live Guided     : ENABLED  (step narrative + trace files)")
    else:
        print("  Live Guided     : DISABLED  (pass --live-guided to enable)")
    if ai_cfg and ai_cfg.evidence_grounding.pass_requires_evidence:
        print("  Evidence Ground : ENABLED  (AI-only PASS blocked)")
    else:
        print("  Evidence Ground : DISABLED")
    if ai_cfg and ai_cfg.curiosity.enabled:
        print(f"  Curiosity Engine: ENABLED  max_actions={ai_cfg.curiosity.max_actions}")
    else:
        print("  Curiosity Engine: DISABLED")
    print("  Safety Filter   : ALWAYS ACTIVE  (destructive/payment/publish blocked by default)")
    print()
    print("Permissions required:")
    for field, value in config.permissions.model_dump().items():
        print(f"  {field:35s} {value}")
    print()

    # Capability check
    observer = ScreenObserver(config.app_type)
    gaps = observer.capability_gaps
    if gaps:
        print("Capability Gaps (will be documented, not faked):")
        for g in gaps:
            print(f"  ✗ {g.capability}: {g.reason}")
    else:
        print("Capabilities: Web/Playwright automation available ✓")

    print()
    print("Test objectives:")
    for obj in config.test_objectives or ["(none specified — will test all discovered elements)"]:
        print(f"  • {obj}")
    print()
    print("[DRY-RUN COMPLETE] No app was launched.")
    return 0


def _live_interactive_test(config, output_dir: str, interactive: bool) -> int:  # type: ignore[no-untyped-def]
    """Execute a live interactive test session."""
    import uuid as _uuid
    from qa_ai.interactive_runtime.permission_gate import PermissionGate
    from qa_ai.interactive_runtime.app_launcher import AppLauncher
    from qa_ai.interactive_runtime.runtime_session import RuntimeSession
    from qa_ai.interactive_runtime.screen_observer import ScreenObserver
    from qa_ai.interactive_runtime.ui_action_planner import UIActionPlanner
    from qa_ai.interactive_runtime.ui_controller import UIController
    from qa_ai.interactive_runtime.human_approval_gate import HumanApprovalGate
    from qa_ai.interactive_runtime.result_verifier import ResultVerifier
    from qa_ai.interactive_runtime.runtime_evidence_builder import RuntimeEvidenceBuilder
    from qa_ai.interactive_runtime.function_coverage_tracker import FunctionCoverageTracker
    from qa_ai.interactive_runtime.screenshot_collector import ScreenshotCollector
    from qa_ai.interactive_runtime.log_watcher import LogWatcher
    from qa_ai.interactive_runtime.interaction_executor import InteractionExecutor
    from qa_ai.interactive_runtime.interactive_reporter import InteractiveReporter
    from qa_ai.interactive_runtime.schemas import RiskLevel

    session_id = str(_uuid.uuid4())[:12]

    # Permission gate — ask about launching
    pgate = PermissionGate(config)
    if config.permission_required:
        decision = pgate.request(
            "launch_app",
            f"Launch '{config.app_name}' with: {config.launch_command}",
            RiskLevel.MEDIUM,
            command=config.launch_command,
            interactive=interactive,
        )
        from qa_ai.interactive_runtime.schemas import PermissionDecision
        if decision == PermissionDecision.DENIED:
            print("[BLOCKED] Launch permission denied. Test session blocked.")
            return 1

    # Launch app
    launcher = AppLauncher()
    launch_result = launcher.launch(
        app_name=config.app_name,
        launch_command=config.launch_command,
        working_dir=config.working_dir,
        readiness_url=config.readiness_url,
        readiness_timeout=config.readiness_timeout_seconds,
    )

    if launch_result.status == "failed":
        print(f"[BLOCKED] App launch failed: {launch_result.failure_reason}")
        return 1

    session = RuntimeSession(
        app_name=config.app_name,
        app_type=config.app_type,
        target_path=config.working_dir,
        launch_command=config.launch_command,
        session_id=session_id,
    )
    session.start()

    screenshots = ScreenshotCollector(output_dir, session_id)
    log_watcher = LogWatcher(
        expected_tags=config.logs.expected_tags,
        redact_secrets=True,
    )
    if launch_result.process and launch_result.process.stdout:
        log_watcher.watch_process_stdout(launch_result.process, source="app")

    observer = ScreenObserver(config.app_type)
    controller = UIController(config.app_type, observer, screenshots)
    planner = UIActionPlanner(config.test_objectives)
    approval_gate = HumanApprovalGate()
    verifier = ResultVerifier(log_watcher=log_watcher)
    evidence_builder = RuntimeEvidenceBuilder()
    coverage = FunctionCoverageTracker(output_dir)

    # ── AI runtime module instantiation ──────────────────────────────────────
    ai_vision_analyzer = None
    ai_action_decider = None
    ai_curiosity_engine = None
    ai_oracle = None
    ai_evidence_grounder = None
    ai_narrator = None
    ai_trace_writer = None
    ai_safety_filter = None
    ai_intent_engine = None
    _live_guided = False
    _ai_guided = False

    ai_cfg = config.ai_runtime
    if ai_cfg:
        _live_guided = ai_cfg.live_guided.enabled
        _ai_guided = ai_cfg.ai_guidance.enabled

        from qa_ai.interactive_runtime.ai_runtime.safety_filter import SafetyFilter
        from qa_ai.interactive_runtime.ai_runtime.intent_inference import IntentInferenceEngine
        from qa_ai.interactive_runtime.ai_runtime.evidence_grounder import EvidenceGrounder

        ai_safety_filter = SafetyFilter()
        ai_intent_engine = IntentInferenceEngine()
        ai_evidence_grounder = EvidenceGrounder(config=ai_cfg.evidence_grounding)

        if _ai_guided:
            from qa_ai.interactive_runtime.ai_runtime.vision_screen_analyzer import VisionScreenAnalyzer
            from qa_ai.interactive_runtime.ai_runtime.ai_action_decider import AIActionDecider
            from qa_ai.interactive_runtime.ai_runtime.curiosity_engine import CuriosityEngine
            from qa_ai.interactive_runtime.ai_runtime.ai_oracle import AIOracle

            ai_vision_analyzer = VisionScreenAnalyzer(config=ai_cfg.vision_analysis)
            ai_action_decider = AIActionDecider(
                safety_filter=ai_safety_filter,
                intent_engine=ai_intent_engine,
                curiosity_config=ai_cfg.curiosity,
                vision_config=ai_cfg.vision_analysis,
            )
            ai_curiosity_engine = CuriosityEngine(
                config=ai_cfg.curiosity, intent_engine=ai_intent_engine
            )
            ai_oracle = AIOracle(config=ai_cfg.ai_guidance)

        if _live_guided:
            from qa_ai.interactive_runtime.ai_runtime.step_narrator import StepNarrator
            from qa_ai.interactive_runtime.ai_runtime.guided_trace_writer import GuidedTraceWriter

            ai_narrator = StepNarrator(silent=not ai_cfg.live_guided.print_steps)
            ai_trace_writer = GuidedTraceWriter(
                output_dir=output_dir,
                write_markdown=ai_cfg.live_guided.write_markdown_trace,
                write_json=ai_cfg.live_guided.write_json_trace,
            )

    executor = InteractionExecutor(
        config=config,
        session=session,
        controller=controller,
        observer=observer,
        planner=planner,
        permission_gate=pgate,
        approval_gate=approval_gate,
        verifier=verifier,
        evidence_builder=evidence_builder,
        coverage=coverage,
        screenshots=screenshots,
        log_watcher=log_watcher,
        interactive=interactive,
        ai_vision_analyzer=ai_vision_analyzer,
        ai_action_decider=ai_action_decider,
        ai_curiosity_engine=ai_curiosity_engine,
        ai_oracle=ai_oracle,
        ai_evidence_grounder=ai_evidence_grounder,
        ai_narrator=ai_narrator,
        ai_trace_writer=ai_trace_writer,
        ai_safety_filter=ai_safety_filter,
        ai_intent_engine=ai_intent_engine,
        live_guided=_live_guided,
        ai_guided=_ai_guided,
    )

    try:
        executor.run()
    finally:
        launcher.stop()

    # Save session
    session.save(output_dir)

    # Write driver_capabilities.json artifact
    try:
        import json as _json_live
        from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector as _CD
        _caps = controller._driver.capabilities()
        _caps_data = _caps.model_dump()
        _caps_data["platform"] = _CD.current_platform()
        _caps_data["app_type"] = config.app_type.value if hasattr(config.app_type, "value") else str(config.app_type)
        (Path(output_dir) / "driver_capabilities.json").write_text(
            _json_live.dumps(_caps_data, indent=2, default=str), encoding="utf-8"
        )
    except Exception:
        pass

    # Generate report
    reporter = InteractiveReporter(output_dir)
    report = reporter.generate(session, coverage, approval_gate.audit_trail, executor=executor)

    print(f"\nInteractive test complete.")
    print(f"  Verdict    : {report.final_verdict.upper()}")
    print(f"  Coverage   : {report.coverage_pct:.1f}%  ({report.total_passed} passed / {report.total_failed} failed)")
    print(f"  Duration   : {report.duration_seconds:.1f}s")
    print(f"  Report     : {output_dir}/interactive_runtime_report.html")

    return 0 if report.final_verdict in ("passed", "inconclusive") else 1


def _run_validate_runtime(args) -> int:  # type: ignore[no-untyped-def]
    """Handle validate-runtime CLI command."""
    import json as _json

    from qa_ai.interactive_runtime.validation.validation_pack import load_pack
    from qa_ai.interactive_runtime.validation.validation_runner import ValidationRunner
    from qa_ai.interactive_runtime.validation.repeatability_runner import RepeatabilityRunner
    from qa_ai.interactive_runtime.validation.flake_analyzer import FlakeAnalyzer
    from qa_ai.interactive_runtime.validation.capability_matrix import CapabilityMatrix
    from qa_ai.interactive_runtime.validation.real_world_reporter import RealWorldReporter

    output_dir: str = getattr(args, "output_dir", "artifacts")
    dry_run: bool = getattr(args, "dry_run", False)
    target_filter: str | None = getattr(args, "target", None)
    repeat: int = max(1, getattr(args, "repeat", 1))
    max_actions: int | None = getattr(args, "max_actions", None)
    live_guided: bool = getattr(args, "live_guided", False)
    ai_guided: bool = getattr(args, "ai_guided", False)
    no_external: bool = getattr(args, "no_external_calls", False)
    no_database: bool = getattr(args, "no_database", False)
    force_screenshots: bool = getattr(args, "screenshots", False)
    auto_setup: bool = getattr(args, "auto_setup", False)
    setup_only: bool = getattr(args, "setup_only", False)
    yes_flag: bool = getattr(args, "yes", False)
    venv_path: str = getattr(args, "venv_path", ".venv")
    vrun_install_appium: bool = getattr(args, "install_appium", False)
    vrun_install_mobile_drivers: bool = getattr(args, "install_mobile_drivers", False)
    vrun_install_vision_model: bool = getattr(args, "install_vision_model", False)

    # Load pack
    try:
        pack = load_pack(args.pack)
    except Exception as exc:
        print(f"[ERROR] Failed to load validation pack: {exc}")
        return 1

    targets = pack.targets
    if target_filter:
        targets = [t for t in targets if t.target_id == target_filter]
        if not targets:
            print(f"[ERROR] No target with id '{target_filter}' found in pack.")
            return 1

    # Apply CLI overrides to targets
    import copy
    targets = copy.deepcopy(targets)
    for t in targets:
        if no_external:
            t.allow_external_calls = "never"
        if no_database:
            t.allow_database_checks = False
        if force_screenshots:
            t.allow_screenshots = "always"
        if dry_run:
            t.allow_real_launch = "never"

    print("=" * 60)
    print("VALIDATE-RUNTIME" + (" [DRY-RUN]" if dry_run else ""))
    print("=" * 60)
    print(f"  Pack       : {pack.pack_name}")
    print(f"  Targets    : {len(targets)}")
    print(f"  Repeat     : {repeat}")
    print(f"  Output dir : {output_dir}")
    print()

    # ── auto-setup: run doctor + fix before validation ─────────────────────
    if auto_setup or setup_only:
        from qa_ai.interactive_runtime.setup import (
            EnvironmentDoctor, SetupPlanner, SetupRunner, SetupReporter,
        )
        app_types = list({t.app_type for t in targets})
        print("[AUTO-SETUP] Running environment doctor...")
        doctor = EnvironmentDoctor()
        dr = doctor.diagnose(app_types=app_types)
        setup_reporter = SetupReporter(output_dir=output_dir)
        setup_reporter.write_doctor_report(dr)
        _print_doctor_summary(dr)

        planner = SetupPlanner()
        plan = planner.build(
            dr,
            venv_path=venv_path,
            target_app_types=app_types,
            install_appium=vrun_install_appium,
            install_mobile_drivers=vrun_install_mobile_drivers,
            install_vision_model=vrun_install_vision_model,
        )
        setup_reporter.write_setup_plan(plan)

        if plan.actions:
            srunner = SetupRunner(
                auto_approve_safe=yes_flag,
                interactive=not dry_run,
                dry_run=dry_run,
            )
            log = srunner.run(plan)
            setup_reporter.write_execution_log(log)
            dr2 = doctor.diagnose(app_types=app_types)
            setup_reporter.write_readiness_after(dr2)
            print(f"\n[POST-SETUP] Readiness: {dr2.readiness_score}/100 ({dr2.readiness_label.upper()})")

        if setup_only:
            print("\n[SETUP-ONLY] Stopping before app launch.")
            return 0
        # Ask before continuing to live validation
        if not dry_run:
            try:
                cont = input("\n[VALIDATE] Continue to live validation? [y/N] ").strip().lower()
                if cont not in ("y", "yes"):
                    print("Stopped.")
                    return 0
            except (EOFError, KeyboardInterrupt):
                return 0

    runner = ValidationRunner(output_dir=output_dir, interactive=not dry_run)

    if dry_run:
        print("Dry-run mode — no apps will be launched.\n")
        results = runner.run_pack_dry(targets)
        for r in results:
            _print_dry_result(r)

        matrix = CapabilityMatrix()
        matrix.ingest_results(results)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        matrix.write_json(f"{output_dir}/phase2_capability_matrix.json")
        matrix.write_markdown(f"{output_dir}/phase2_capability_matrix.md")
        print(f"\nCapability matrix written to {output_dir}/phase2_capability_matrix.md")
        print("[DRY-RUN COMPLETE] No apps were launched.")
        return 0

    # Live runs
    from qa_ai.interactive_runtime.validation.validation_result import RepeatabilityResult
    all_results = []
    all_repeatability: list[RepeatabilityResult] = []

    for t in targets:
        print(f"\n── Target: {t.target_id} ({t.app_name}) ──")
        if repeat > 1:
            rep_runner = RepeatabilityRunner(
                output_dir=output_dir,
                repeat_count=repeat,
                interactive=True,
            )
            rep_result = rep_runner.run(
                t, live_guided=live_guided, ai_guided=ai_guided, max_actions=max_actions
            )
            all_repeatability.append(rep_result)
            # collect per-run results for aggregate report
            for run_m in rep_result.runs:
                all_results.append(_run_metric_to_result(t, run_m))
            print(f"  Repeatability score : {rep_result.repeatability_score:.2f}")
        else:
            result = runner.run_live(
                t, live_guided=live_guided, ai_guided=ai_guided, max_actions=max_actions
            )
            all_results.append(result)
            print(f"  Status  : {result.status.value}")
            print(f"  Verdict : {result.live_verdict or '—'}")
            print(f"  Coverage: {result.coverage_pct:.1f}%")

    # Report
    reporter = RealWorldReporter(output_dir=output_dir)
    known_limitations = [
        "Android/iOS require Appium server — opt-in only.",
        "Windows/Linux drivers require running on target OS.",
        "Flutter accessibility trees may be weak.",
        "AI-only PASS is blocked — evidence required.",
    ]
    summary = reporter.generate(
        results=all_results,
        repeatability=all_repeatability or None,
        pack_name=pack.pack_name,
        known_limitations=known_limitations,
    )

    print("\n" + "=" * 60)
    print(f"OVERALL VERDICT : {summary['overall_verdict'].upper()}")
    print(f"Live passed     : {summary['live_passed']}")
    print(f"Live failed     : {summary['live_failed']}")
    print(f"Blocked         : {summary['blocked']}")
    print(f"Flake blockers  : {summary['flake_blockers']}")
    print(f"Report          : {output_dir}/phase2_validation_report.html")
    return 0 if summary["overall_verdict"] in ("passed", "partial") else 1


def _print_dry_result(result) -> None:  # type: ignore[no-untyped-def]
    from qa_ai.interactive_runtime.validation.validation_result import TargetValidationStatus
    print(f"  [{result.target_id}] {result.app_name} ({result.app_type})")
    print(f"    Status  : {result.status.value}")
    print(f"    Driver  : {result.driver_backend} / {result.driver_status}")
    if result.capability_gaps:
        for g in result.capability_gaps[:3]:
            print(f"    Gap     : {g}")
    if result.setup_instructions:
        for s in result.setup_instructions[:3]:
            print(f"    Setup   : {s}")
    if result.notes:
        print(f"    Notes   : {result.notes}")
    # Show connector dry-run results if present
    connector_results = (result.dry_run_caps or {}).get("connector_dry_results", [])
    if connector_results:
        print(f"    Connectors ({len(connector_results)}):")
        for cr in connector_results[:4]:
            cid = cr.get("connector_id", "?")
            ctype = cr.get("type", "?")
            status = cr.get("status", "?")
            gaps = cr.get("gaps", [])
            gap_str = f" gaps:{gaps[:2]}" if gaps else ""
            print(f"      {cid} ({ctype}) → {status}{gap_str}")
    print()


def _run_metric_to_result(target, run_metric):  # type: ignore[no-untyped-def]
    from qa_ai.interactive_runtime.validation.validation_result import ValidationResult
    return ValidationResult(
        target_id=target.target_id,
        app_name=target.app_name,
        app_type=target.app_type,
        status=run_metric.status,
        live_verdict=run_metric.live_verdict,
        coverage_pct=run_metric.coverage_pct,
        duration_seconds=run_metric.duration_seconds,
        capability_gaps=run_metric.capability_gaps,
        error=run_metric.error,
    )


def _run_runtime_doctor(args) -> int:  # type: ignore[no-untyped-def]
    """Handle runtime-doctor CLI command."""
    from qa_ai.interactive_runtime.setup import (
        EnvironmentDoctor,
        SetupPlanner,
        SetupRunner,
        SetupReporter,
    )

    output_dir: str = getattr(args, "output_dir", "artifacts")
    dry_run: bool = getattr(args, "dry_run", False)
    auto_setup: bool = getattr(args, "auto_setup", False)
    create_venv: bool = getattr(args, "create_venv", False)
    venv_path: str = getattr(args, "venv_path", ".venv")
    yes: bool = getattr(args, "yes", False)
    open_settings: bool = getattr(args, "open_settings", False)
    install_appium: bool = getattr(args, "install_appium", False)
    install_mobile_drivers: bool = getattr(args, "install_mobile_drivers", False)
    install_vision_model: bool = getattr(args, "install_vision_model", False)
    pack_path: str | None = getattr(args, "pack", None)
    config_path: str | None = getattr(args, "config", None)

    # Collect app_types from pack or config if provided
    app_types = None
    if pack_path:
        try:
            from qa_ai.interactive_runtime.validation.validation_pack import load_pack
            pack = load_pack(pack_path)
            app_types = list({t.app_type for t in pack.targets})
        except Exception as exc:
            print(f"[WARN] Could not load pack for app_type hints: {exc}")

    print("=" * 60)
    print("RUNTIME ENVIRONMENT DOCTOR" + (" [DRY-RUN]" if dry_run else ""))
    print("=" * 60)

    doctor = EnvironmentDoctor()
    report = doctor.diagnose(app_types=app_types)
    reporter = SetupReporter(output_dir=output_dir)
    reporter.write_doctor_report(report)
    reporter.write_driver_requirements()

    _print_doctor_summary(report)
    _print_appium_summary(report)
    _print_connector_requirements(pack_path)

    print(f"\nReport written to {output_dir}/runtime_doctor_report.md")
    print(f"Driver requirements: {output_dir}/driver_requirements.json")

    if not auto_setup and not dry_run:
        if report.readiness_score < 100:
            print(
                "\nRun with --auto-setup to generate a setup plan and fix issues."
            )
        return 0 if report.readiness_score >= 40 else 1

    # Build setup plan
    planner = SetupPlanner()
    plan = planner.build(
        report,
        venv_path=venv_path,
        create_venv_if_missing=create_venv,
        target_app_types=app_types,
        install_appium=install_appium,
        install_mobile_drivers=install_mobile_drivers,
        install_vision_model=install_vision_model,
    )
    reporter.write_setup_plan(plan)

    if plan.actions:
        print(f"\n[SETUP PLAN] {len(plan.actions)} actions planned")
        for a in plan.actions:
            auto_tag = " [auto]" if a.can_auto_run else " [manual]"
            print(f"  {a.action_id[:16]} {a.title}{auto_tag}")
        print(f"\n  Safe auto-actions : {len(plan.safe_auto_actions)}")
        print(f"  User-required     : {len(plan.user_required_actions)}")
        print(f"  Blocked (manual)  : {len(plan.blocked_actions)}")
        print(f"  Est. score after  : {plan.estimated_readiness_after_setup}/100")
    else:
        print("\n[OK] No setup actions needed.")

    if dry_run:
        print("\n[DRY-RUN COMPLETE] No changes made.")
        return 0

    if not plan.actions:
        return 0

    # Run approved actions
    runner = SetupRunner(
        auto_approve_safe=yes,
        interactive=True,
        dry_run=False,
    )
    log = runner.run(plan)
    reporter.write_execution_log(log)

    # Re-check after setup
    print("\n[RE-CHECK] Running environment doctor after setup...")
    report_after = doctor.diagnose(app_types=app_types)
    reporter.write_readiness_after(report_after)
    _print_doctor_summary(report_after)

    print(f"\nSetup log: {output_dir}/setup_execution_log.json")
    print(f"Readiness after: {output_dir}/setup_readiness_after.json")

    return 0 if report_after.readiness_score >= 40 else 1


def _print_connector_requirements(pack_path: str | None) -> None:
    """Show connector requirements from pack (runtime-doctor integration)."""
    if not pack_path:
        return
    try:
        from qa_ai.interactive_runtime.validation.validation_pack import load_pack
        from qa_ai.interactive_runtime.config_loader import load_config
        from qa_ai.interactive_runtime.connectors.connector_factory import ConnectorFactory
        pack = load_pack(pack_path)
        connector_counts: dict[str, int] = {}
        for target in pack.targets:
            try:
                cfg = load_config(target.config_path)
                connectors_cfg = getattr(cfg, "runtime_connectors", None)
                if connectors_cfg and getattr(connectors_cfg, "connectors", None):
                    for c in connectors_cfg.connectors:
                        if c.enabled:
                            ctype = c.connector_type.value
                            connector_counts[ctype] = connector_counts.get(ctype, 0) + 1
            except Exception:
                pass
        if connector_counts:
            print("\n  Connector requirements from pack:")
            for ctype, count in connector_counts.items():
                print(f"    {ctype}: {count} connector(s)")
    except Exception as exc:
        pass  # non-fatal; connector info is supplemental


def _print_connector_dry_summary(results: list) -> None:
    """Print connector dry-run results in CLI output."""
    if not results:
        return
    print("\n  Connectors (dry-run):")
    for r in results:
        status_str = {
            "pending": "⏳ dry-run",
            "ready": "✅ ready",
            "failed": "❌ failed",
            "blocked": "🚫 blocked",
            "capability_gap": "⚠️  gap",
            "skipped": "⏭  skipped",
        }.get(r.status.value if hasattr(r, "status") else str(r), str(r))
        cid = r.connector_id if hasattr(r, "connector_id") else r.get("connector_id", "?")
        ctype = (r.connector_type.value if hasattr(r, "connector_type") else r.get("type", "?"))
        print(f"    {cid} ({ctype}) → {status_str}")
        gaps = r.capability_gaps if hasattr(r, "capability_gaps") else r.get("gaps", [])
        for g in gaps[:2]:
            gid = g.gap_id if hasattr(g, "gap_id") else g
            print(f"      ⚠️  gap: {gid}")


def _print_appium_summary(report) -> None:  # type: ignore[no-untyped-def]
    """Print Appium ecosystem status (only if any Appium field is non-default)."""
    def tick(v: bool) -> str:
        return "✅" if v else "❌"

    if not (report.npm_available or report.appium_command_available
            or report.appium_uiautomator2_installed or report.appium_xcuitest_installed
            or report.appium_server_reachable):
        return  # all false — no need to show
    print(f"  npm        : {tick(report.npm_available)}")
    print(f"  appium cmd : {tick(report.appium_command_available)}")
    print(f"  uiautomator2: {tick(report.appium_uiautomator2_installed)}")
    print(f"  xcuitest   : {tick(report.appium_xcuitest_installed)}")
    if report.ollama_configured_model:
        tick_model = tick(report.ollama_vision_model_available)
        print(f"  Vision model: {report.ollama_configured_model} {tick_model}")


def _print_doctor_summary(report) -> None:  # type: ignore[no-untyped-def]
    def tick(v: bool) -> str:
        return "✅" if v else "❌"

    p = report.platform
    print(f"\n  Platform   : {p}")
    print(f"  Python     : {report.python_version} @ {report.python_executable}")
    print(f"  Venv       : {tick(report.venv_active)} {report.venv_path or '(none)'}")
    print(f"  Playwright : {tick(report.playwright_installed)} (browsers: {tick(report.playwright_browsers_installed)})")
    if p == "macos":
        print(f"  Accessibility: {tick(report.macos_accessibility_granted)}")
    if p == "windows":
        print(f"  pywinauto  : {tick(report.pywinauto_installed)}")
    if p == "linux":
        print(f"  AT-SPI     : {tick(report.atspi_installed)}")
        print(f"  xdotool    : {tick(report.xdotool_available)}")
    print(f"  Appium     : client={tick(report.appium_client_installed)} server={tick(report.appium_server_reachable)}")
    print(f"  Ollama     : {tick(report.ollama_reachable)}")
    score_bar = "▓" * (report.readiness_score // 10) + "░" * (10 - report.readiness_score // 10)
    print(f"\n  Readiness  : {report.readiness_score}/100 [{score_bar}] {report.readiness_label.upper()}")
    if report.missing_items:
        print("\n  Missing:")
        for item in report.missing_items[:5]:
            print(f"    ❌ {item}")


if __name__ == "__main__":
    raise SystemExit(main())
