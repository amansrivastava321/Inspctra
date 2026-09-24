"""
audit_command.py - End-to-end audit command orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import importlib.util
import json
import platform as py_platform
import subprocess
import shutil
import uuid

from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.cli.profile_manager import ProfileManager
from qa_ai.cli.run_summary import RunSummary
from qa_ai.benchmarking.benchmark_report import BenchmarkReport
from qa_ai.benchmarking.benchmark_runner import BenchmarkRunner
from qa_ai.benchmarking.detection_metrics import DetectionMetrics
from qa_ai.benchmarking.tool_comparison import ToolComparison
from qa_ai.orchestration.workflow_engine import WorkflowEngine, WorkflowPhase
from qa_ai.ai_reasoning.ai_reasoning_orchestrator import AIReasoningOrchestrator
from qa_ai.ai_orchestration.ai_audit_orchestrator import AIAuditOrchestrator
from qa_ai.reporting.audit_summary_builder import AuditSummaryBuilder
from qa_ai.reporting.executive_report_generator import ExecutiveReportGenerator
from qa_ai.reporting.graph_visualizer import GraphVisualizer
from qa_ai.reporting.html_dashboard_builder import HTMLDashboardBuilder
from qa_ai.reporting.report_exporter import ReportExporter
from qa_ai.reporting.risk_visualizer import RiskVisualizer
from qa_ai.reporting.technical_report_generator import TechnicalReportGenerator
from qa_ai.reporting.trace_visualizer import TraceVisualizer
from qa_ai.reporting.workflow_visualizer import WorkflowVisualizer
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.distributed_runtime.distributed_runtime_runner import DistributedRuntimeRunner
from qa_ai.mobile_runtime.device_registry import DeviceRegistry
from qa_ai.mobile_runtime.mobile_runtime_runner import MobileRuntimeRunner
from qa_ai.remediation.remediation_orchestrator import RemediationOrchestrator
from qa_ai.remediation_runtime.remediation_runtime_orchestrator import RemediationRuntimeOrchestrator
from qa_ai.cicd.ci_provider_detector import CIProviderDetector
from qa_ai.cicd.github_actions_generator import GitHubActionsGenerator
from qa_ai.cicd.gitlab_ci_generator import GitLabCIGenerator
from qa_ai.cicd.jenkins_pipeline_generator import JenkinsPipelineGenerator
from qa_ai.cicd.pr_audit_runner import PRAuditRunner
from qa_ai.cicd.baseline_comparator import BaselineComparator
from qa_ai.cicd.release_gate_engine import ReleaseGateEngine
from qa_ai.cicd.cicd_reporter import CICDReporter
from qa_ai.platform_performance.performance_profiler import PerformanceProfiler
from qa_ai.platform_performance.artifact_lifecycle_manager import ArtifactLifecycleManager
from qa_ai.platform_performance.evidence_storage_optimizer import EvidenceStorageOptimizer
from qa_ai.platform_performance.scalability_reporter import ScalabilityReporter
from qa_ai.platform_performance.incremental_graph_manager import IncrementalGraphManager
from qa_ai.platform_performance.parallel_execution_planner import ParallelExecutionPlanner
from qa_ai.platform_performance.memory_usage_tracker import MemoryUsageTracker
from qa_ai.enterprise.workspace_manager import WorkspaceManager
from qa_ai.enterprise.project_registry import ProjectRegistry
from qa_ai.enterprise.team_registry import TeamRegistry
from qa_ai.enterprise.role_engine import RoleEngine
from qa_ai.enterprise.policy_engine import PolicyEngine
from qa_ai.enterprise.audit_history_manager import AuditHistoryManager
from qa_ai.enterprise.governance_reporter import GovernanceReporter
from qa_ai.enterprise.access_audit_logger import AccessAuditLogger
from qa_ai.enterprise.enterprise_runtime_orchestrator import EnterpriseRuntimeOrchestrator
from qa_ai.benchmark_intelligence.benchmark_dataset_manager import BenchmarkDatasetManager
from qa_ai.benchmark_intelligence.benchmark_scoring_engine import BenchmarkScoringEngine
from qa_ai.benchmark_intelligence.false_positive_tracker import FalsePositiveTracker
from qa_ai.benchmark_intelligence.coverage_trend_analyzer import CoverageTrendAnalyzer
from qa_ai.benchmark_intelligence.benchmark_comparison_engine import BenchmarkComparisonEngine
from qa_ai.benchmark_intelligence.maturity_scoring_engine import MaturityScoringEngine
from qa_ai.benchmark_intelligence.benchmark_history_tracker import BenchmarkHistoryTracker
from qa_ai.benchmark_intelligence.benchmark_reporter import BenchmarkReporter
from qa_ai.benchmark_intelligence.benchmark_runtime_orchestrator import BenchmarkRuntimeOrchestrator
from qa_ai.self_optimization.self_optimization_orchestrator import SelfOptimizationOrchestrator
from qa_ai.runtime_lab.docker_runtime import DockerRuntime
from qa_ai.runtime_lab.environment_bootstrapper import EnvironmentBootstrapper
from qa_ai.runtime_lab.live_benchmark_runner import LiveBenchmarkRunner


@dataclass
class AuditCommand:
    """CLI audit command handler."""

    profile_manager: ProfileManager

    def run(
        self,
        target_path: str,
        profile: str,
        output_dir: str = "artifacts",
        dry_run: bool = False,
        ai_reasoning: bool = False,
        ci_mode: bool = False,
        ai_first: bool = False,
    ) -> Dict[str, Any]:
        output_path = Path(output_dir).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        store = ArtifactStore(base_dir=output_path)
        summary_builder = RunSummary(store)

        warnings: List[str] = []
        errors: List[str] = []

        target = Path(target_path).expanduser().resolve()
        if not target.exists():
            errors.append(f"Target path does not exist: {target}")
            summary = summary_builder.build(
                run_id=f"run_{uuid.uuid4().hex[:12]}",
                target_path=str(target),
                profile=profile,
                phases_executed=[],
                status="failed",
                warnings=warnings,
                errors=errors,
                dry_run=dry_run,
            )
            return summary_builder.save(summary)

        if not self.profile_manager.validate_profile(profile):
            errors.append(f"Unknown profile: {profile}")
            summary = summary_builder.build(
                run_id=f"run_{uuid.uuid4().hex[:12]}",
                target_path=str(target),
                profile=profile,
                phases_executed=[],
                status="failed",
                warnings=warnings,
                errors=errors,
                dry_run=dry_run,
            )
            return summary_builder.save(summary)

        phases = self.profile_manager.get_workflow_phases(profile)
        platform = self.profile_manager.get_platform(profile)
        if ci_mode:
            ci_phases = [
                WorkflowPhase.CICD_PROVIDER_DETECTION,
                WorkflowPhase.CICD_WORKFLOW_PLANNING,
                WorkflowPhase.INCREMENTAL_AUDIT_ANALYSIS,
                WorkflowPhase.BASELINE_COMPARISON,
                WorkflowPhase.RELEASE_GATE_EVALUATION,
                WorkflowPhase.PIPELINE_POLICY_VALIDATION,
                WorkflowPhase.PR_AUDIT_ORCHESTRATION,
                WorkflowPhase.CICD_AUDIT_LOGGING,
            ]
            existing = {phase.value for phase in phases}
            for phase in ci_phases:
                if phase.value not in existing:
                    phases.append(phase)
                    existing.add(phase.value)

        if ai_first:
            ai_first_phases = [
                WorkflowPhase.AI_SOFTWARE_UNDERSTANDING,
                WorkflowPhase.AI_AUDIT_STRATEGY,
                WorkflowPhase.AI_TEST_INTENT_GENERATION,
                WorkflowPhase.AI_SCENARIO_INTELLIGENCE,
                WorkflowPhase.AI_EVIDENCE_INTERPRETATION,
                WorkflowPhase.AI_RCA_COORDINATION,
                WorkflowPhase.AI_IMPROVEMENT_STRATEGY,
                WorkflowPhase.AI_DECISION_LOGGING,
            ]
            existing = {phase.value for phase in phases}
            for phase in ai_first_phases:
                if phase.value not in existing:
                    phases.append(phase)
                    existing.add(phase.value)

        phase_names = [phase.value for phase in phases]

        if dry_run:
            summary = summary_builder.build(
                run_id=f"run_{uuid.uuid4().hex[:12]}",
                target_path=str(target),
                profile=profile,
                phases_executed=phase_names,
                status="dry_run",
                warnings=warnings,
                errors=errors,
                dry_run=True,
            )
            saved = summary_builder.save(summary)
            saved["ai_first"] = {"enabled": bool(ai_first), "mode": "dry_run" if ai_first else "disabled"}
            return saved

        engine = WorkflowEngine(artifact_store=store)
        workflow_result = engine.run(
            app_path=str(target),
            app_name=target.name,
            platform=platform,
            phases=phases,
        )

        ai_reasoning_result: Dict[str, Any] | None = None
        if ai_reasoning:
            ai_reasoning_result = AIReasoningOrchestrator(store).run(enabled=True, dry_run=False)

        summary = summary_builder.build(
            run_id=workflow_result.run_id,
            target_path=str(target),
            profile=profile,
            phases_executed=[phase.phase.value for phase in workflow_result.phases],
            status=workflow_result.status.value,
            warnings=warnings,
            errors=errors,
            dry_run=False,
        )
        saved = summary_builder.save(summary)
        if ai_first:
            brain = AIAuditOrchestrator(store).run(
                app_path=str(target),
                dry_run=False,
                enabled=True,
            )
            saved["ai_first"] = {
                "enabled": True,
                "mode": brain.get("mode", "deterministic_fallback"),
                "artifact": "ai_audit_brain_summary.json",
                "overall_confidence": brain.get("overall_confidence", 0.0),
            }
        if ci_mode:
            from qa_ai.cicd_runtime.cicd_runtime_orchestrator import CICDRuntimeOrchestrator

            runtime_summary = CICDRuntimeOrchestrator(store).run(
                repo_path=str(target),
                provider="auto",
                changed_files=[],
                dry_run=False,
            )
            saved["ci_mode"] = {
                "enabled": True,
                "artifact": "cicd_runtime_summary.json",
                "release_gate": runtime_summary.get("release_decision", "warning"),
                "provider": runtime_summary.get("provider", "unknown_manual"),
            }
        if ai_reasoning_result is not None:
            saved["ai_reasoning"] = {
                "mode": ai_reasoning_result.get("mode", "unknown"),
                "artifact": "ai_reasoning_summary.json",
            }
        return saved

    def run_ai_audit(
        self,
        target_path: str,
        profile: str = "full_stack",
        output_dir: str = "artifacts",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        return self.run(
            target_path=target_path,
            profile=profile,
            output_dir=output_dir,
            dry_run=dry_run,
            ai_reasoning=False,
            ci_mode=False,
            ai_first=True,
        )

    def run_report(self, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        summary = AuditSummaryBuilder(store).run()
        executive = ExecutiveReportGenerator(store).run(summary=summary)
        technical = TechnicalReportGenerator(store).run()
        dashboard = HTMLDashboardBuilder(store).run()
        risk = RiskVisualizer(store).run()
        workflow = WorkflowVisualizer(store).run()
        trace = TraceVisualizer(store).run()
        graph = GraphVisualizer(store).run()
        exports = ReportExporter(store).run(summary=summary)
        return {
            "status": "ok",
            "executive": executive.get("html_report"),
            "technical": technical.get("html_report"),
            "dashboard": dashboard.get("dashboard_file"),
            "visualizations": {
                "risk": list(risk.keys()),
                "workflow": list(workflow.keys()),
                "trace": list(trace.keys()),
                "graph": list(graph.keys()),
            },
            "exports": exports,
        }

    def run_doctor(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        checks: Dict[str, Any] = {
            "python": {
                "version": py_platform.python_version(),
                "ok": True,
            },
            "pytest": self._check_command(["python", "-m", "pytest", "--version"]),
            "playwright": self._check_module("playwright"),
            "graphify_outputs": self._check_graphify_outputs(),
            "artifact_directory": {
                "path": str(store.base_dir),
                "exists": store.base_dir.exists(),
                "writable": store.base_dir.exists(),
            },
            "required_packages": {
                pkg: self._check_module(pkg)["ok"]
                for pkg in ["yaml", "pydantic", "requests", "rich"]
            },
        }
        overall_ok = all(
            value.get("ok", True) if isinstance(value, dict) else bool(value)
            for value in checks.values()
            if isinstance(value, dict)
        )
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok" if overall_ok else "degraded",
            "checks": checks,
        }
        store.save_artifact("doctor_report", report, agent="DoctorCommand")
        return report

    def run_benchmark(
        self,
        sample_root: str,
        output_dir: str = "artifacts",
        execute: bool = False,
        live: bool = False,
        dry_run: bool = False,
        distributed: bool = False,
        mobile: bool = False,
        ai_reasoning: bool = False,
        ai_first: bool = False,
    ) -> Dict[str, Any]:
        output_path = Path(output_dir).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        store = ArtifactStore(base_dir=output_path)

        if mobile:
            mobile_result = self.run_mobile_runtime(
                sample_path=sample_root,
                output_dir=str(output_path),
                dry_run=(dry_run or not execute),
                distributed=distributed,
            )
            result = {
                "status": "ok",
                "mobile": True,
                "distributed": bool(distributed),
                "benchmark_root": mobile_result.get("app_path", sample_root),
                "apps_benchmarked": 1,
                "findings_total": mobile_result.get("summary", {}).get("critical_mobile_signals", 0),
                "artifacts": mobile_result.get("artifacts", {}),
            }
            if ai_reasoning:
                reasoning = AIReasoningOrchestrator(store).run(enabled=True, dry_run=(dry_run or not execute))
                result["ai_reasoning"] = {"mode": reasoning.get("mode", "unknown"), "artifact": "ai_reasoning_summary.json"}
            if ai_first:
                brain = AIAuditOrchestrator(store).run(app_path=sample_root, dry_run=(dry_run or not execute), enabled=True)
                result["ai_first"] = {
                    "enabled": True,
                    "mode": brain.get("mode", "deterministic_fallback"),
                    "artifact": "ai_audit_brain_summary.json",
                }
            return result

        if distributed:
            distributed_result = self.run_distributed_runtime(
                sample_path=sample_root,
                output_dir=str(output_path),
                dry_run=dry_run or True,
                actors=None,
            )
            result = {
                "status": "ok",
                "distributed": True,
                "benchmark_root": distributed_result.get("app_path", sample_root),
                "apps_benchmarked": 1,
                "findings_total": distributed_result.get("summary", {}).get("anomaly_count", 0),
                "artifacts": distributed_result.get("artifacts", {}),
            }
            if ai_reasoning:
                reasoning = AIReasoningOrchestrator(store).run(enabled=True, dry_run=(dry_run or not execute))
                result["ai_reasoning"] = {"mode": reasoning.get("mode", "unknown"), "artifact": "ai_reasoning_summary.json"}
            if ai_first:
                brain = AIAuditOrchestrator(store).run(app_path=sample_root, dry_run=(dry_run or not execute), enabled=True)
                result["ai_first"] = {
                    "enabled": True,
                    "mode": brain.get("mode", "deterministic_fallback"),
                    "artifact": "ai_audit_brain_summary.json",
                }
            return result

        if live:
            live_result = LiveBenchmarkRunner(store).run(
                sample_root=sample_root,
                output_dir=str(output_path),
                dry_run=dry_run,
            )
            if ai_reasoning:
                reasoning = AIReasoningOrchestrator(store).run(enabled=True, dry_run=(dry_run or not execute))
                live_result["ai_reasoning"] = {"mode": reasoning.get("mode", "unknown"), "artifact": "ai_reasoning_summary.json"}
            if ai_first:
                brain = AIAuditOrchestrator(store).run(app_path=sample_root, dry_run=(dry_run or not execute), enabled=True)
                live_result["ai_first"] = {
                    "enabled": True,
                    "mode": brain.get("mode", "deterministic_fallback"),
                    "artifact": "ai_audit_brain_summary.json",
                }
            return live_result

        runner = BenchmarkRunner()
        benchmark_summary = runner.run(
            sample_root=sample_root,
            output_dir=str(output_path),
            execute=execute,
        )
        benchmark_metrics = DetectionMetrics().run(benchmark_summary)
        comparison = ToolComparison().run(benchmark_summary, benchmark_metrics)
        exports = BenchmarkReport(store).run(
            benchmark_summary=benchmark_summary,
            benchmark_metrics=benchmark_metrics,
            comparison=comparison,
        )

        totals = benchmark_summary.get("totals", {}) if isinstance(benchmark_summary.get("totals"), dict) else {}
        result = {
            "status": "ok",
            "benchmark_root": benchmark_summary.get("benchmark_root", ""),
            "apps_benchmarked": totals.get("apps_total", 0),
            "findings_total": totals.get("findings_total", 0),
            "artifacts": exports,
        }
        if ai_reasoning:
            reasoning = AIReasoningOrchestrator(store).run(enabled=True, dry_run=(dry_run or not execute))
            result["ai_reasoning"] = {"mode": reasoning.get("mode", "unknown"), "artifact": "ai_reasoning_summary.json"}
        if ai_first:
            brain = AIAuditOrchestrator(store).run(app_path=sample_root, dry_run=(dry_run or not execute), enabled=True)
            result["ai_first"] = {
                "enabled": True,
                "mode": brain.get("mode", "deterministic_fallback"),
                "artifact": "ai_audit_brain_summary.json",
            }
        return result

    def run_runtime_lab_doctor(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        bootstrapper = EnvironmentBootstrapper(store)
        docker_runtime = DockerRuntime(store)
        sample_app = Path("sample_apps/vulnerable_fastapi_app").resolve()
        bootstrap_plan = bootstrapper.prepare(
            app_path=str(sample_app),
            dry_run=True,
            allow_auto_install=False,
        )
        docker_plan = docker_runtime.plan(
            app_path=str(sample_app),
            app_type="fastapi_python",
            start_requested=False,
        )

        checks: Dict[str, Any] = {
            "python": {"ok": True, "version": py_platform.python_version()},
            "node": {"ok": shutil.which("node") is not None},
            "npm": {"ok": shutil.which("npm") is not None},
            "docker": docker_runtime.detect_docker(),
            "playwright": self._check_module("playwright"),
            "graphify_outputs": self._check_graphify_outputs(),
            "bootstrap_plan_ready": bool(bootstrap_plan.get("environment_ready", False)),
            "docker_plan_can_start": bool(docker_plan.get("can_start", False)),
        }
        overall_ok = bool(checks["python"]["ok"] and checks["graphify_outputs"]["ok"])
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok" if overall_ok else "degraded",
            "checks": checks,
            "artifacts": {
                "bootstrap_plan": "bootstrap_plan.json",
                "docker_runtime_plan": "docker_runtime_plan.json",
            },
        }
        store.save_artifact("runtime_lab_doctor_report", report, agent="RuntimeLabDoctor")
        return report

    def run_distributed_runtime(
        self,
        sample_path: str,
        output_dir: str = "artifacts",
        dry_run: bool = True,
        actors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        output_path = Path(output_dir).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        store = ArtifactStore(base_dir=output_path)

        runner = DistributedRuntimeRunner(store)
        report = runner.run(
            app_path=sample_path,
            actors=actors,
            dry_run=dry_run,
            mode="parallel",
        )

        return {
            "status": "ok",
            "app_path": report.get("app_path"),
            "dry_run": report.get("dry_run", True),
            "summary": report.get("summary", {}),
            "artifacts": {
                "distributed_runtime_report": "distributed_runtime_report.json",
                "actor_registry": "actor_registry.json",
                "multi_session_report": "multi_session_report.json",
                "concurrency_analysis": "concurrency_analysis.json",
                "network_condition_report": "network_condition_report.json",
                "offline_recovery_report": "offline_recovery_report.json",
                "sync_conflict_report": "sync_conflict_report.json",
                "chaos_execution_report": "chaos_execution_report.json",
                "distributed_evidence_graph": "distributed_evidence_graph.json",
            },
        }

    def run_mobile_runtime_doctor(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        registry = DeviceRegistry(store).run()
        checks: Dict[str, Any] = {
            "python": {"ok": True, "version": py_platform.python_version()},
            "android_sdk": registry.get("tooling", {}).get("android_sdk", {}),
            "adb": registry.get("tooling", {}).get("adb", {}),
            "emulator": registry.get("tooling", {}).get("emulator", {}),
            "xcodebuild": registry.get("tooling", {}).get("xcodebuild", {}),
            "flutter": registry.get("tooling", {}).get("flutter", {}),
            "appium": registry.get("tooling", {}).get("appium", {}),
            "maestro": registry.get("tooling", {}).get("maestro", {}),
        }
        overall_ok = bool(checks["python"]["ok"])
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok" if overall_ok else "degraded",
            "checks": checks,
            "summary": registry.get("summary", {}),
            "artifact": "device_registry.json",
        }
        store.save_artifact("mobile_runtime_doctor_report", report, agent="MobileRuntimeDoctor")
        return report

    def run_mobile_runtime(
        self,
        sample_path: str,
        output_dir: str = "artifacts",
        dry_run: bool = True,
        distributed: bool = False,
    ) -> Dict[str, Any]:
        output_path = Path(output_dir).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        store = ArtifactStore(base_dir=output_path)

        runner = MobileRuntimeRunner(store)
        report = runner.run(
            app_path=sample_path,
            dry_run=dry_run,
            distributed=distributed,
            actors=None,
        )
        return {
            "status": "ok",
            "app_path": report.get("app_path"),
            "dry_run": report.get("dry_run", True),
            "distributed": report.get("distributed", False),
            "summary": report.get("summary", {}),
            "artifacts": {
                "mobile_runtime_report": "mobile_runtime_report.json",
                "device_registry": "device_registry.json",
                "android_emulator_report": "android_emulator_report.json",
                "ios_simulator_report": "ios_simulator_report.json",
                "flutter_execution_plan": "flutter_execution_plan.json",
                "appium_plan": "appium_plan.json",
                "maestro_plan": "maestro_plan.json",
                "device_session_report": "device_session_report.json",
                "mobile_network_report": "mobile_network_report.json",
                "mobile_runtime_monitor_report": "mobile_runtime_monitor_report.json",
                "mobile_logs_index": "mobile_logs_index.json",
                "mobile_evidence_graph": "mobile_evidence_graph.json",
            },
        }

    def run_ai_reasoning(self, artifacts_dir: str = "artifacts", dry_run: bool = True) -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        result = AIReasoningOrchestrator(store).run(enabled=True, dry_run=dry_run)
        return {
            "status": "ok",
            "mode": result.get("mode", "unknown"),
            "model_available": result.get("model_available", False),
            "artifact": "ai_reasoning_summary.json",
            "artifacts": result.get("artifacts", {}),
        }

    def run_remediation(
        self,
        artifacts_dir: str = "artifacts",
        dry_run: bool = True,
        proposal_only: bool = False,
        approve_fix_ids: Optional[List[str]] = None,
        sandbox: bool = False,
    ) -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        summary = RemediationOrchestrator(store).run(
            dry_run=dry_run,
            proposal_only=proposal_only,
            approve_fix_ids=approve_fix_ids or [],
            sandbox=sandbox,
        )
        return {
            "status": "ok",
            "mode": summary.get("mode", "unknown"),
            "dry_run": bool(summary.get("dry_run", dry_run)),
            "proposal_only": bool(proposal_only),
            "approved_fix_ids": list(approve_fix_ids or []),
            "artifact": "remediation_summary.json",
            "artifacts": summary.get("artifacts", {}),
            "counts": summary.get("counts", {}),
            "safety": summary.get("safety", {}),
        }

    def run_remediation_runtime(
        self,
        artifacts_dir: str = "artifacts",
        dry_run: bool = True,
        proposal_only: bool = False,
        simulate: bool = False,
        sandbox: bool = False,
        approve_fix_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        summary = RemediationRuntimeOrchestrator(store).run(
            dry_run=dry_run,
            proposal_only=proposal_only,
            simulate=simulate,
            sandbox=sandbox,
            approve_fix_ids=approve_fix_ids or [],
        )
        return {
            "status": "ok",
            "mode": summary.get("mode", "unknown"),
            "dry_run": bool(summary.get("dry_run", dry_run)),
            "proposal_only": bool(proposal_only),
            "simulate": bool(simulate),
            "sandbox": bool(sandbox),
            "approved_fix_ids": list(approve_fix_ids or []),
            "artifact": "remediation_runtime_summary.json",
            "artifacts": summary.get("artifacts", {}),
            "counts": summary.get("counts", {}),
            "safety": summary.get("safety", {}),
        }

    def run_cicd_doctor(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        provider = CIProviderDetector(store).run(repo_path=".")
        return {
            "status": "ok",
            "provider": provider.get("provider", "unknown_manual"),
            "known_provider": bool(provider.get("known_provider", False)),
            "artifact": "cicd_provider_report.json",
            "evidence": provider.get("evidence", []),
        }

    def run_cicd_plan(
        self,
        provider: str = "auto",
        output_dir: str = "artifacts",
        dry_run: bool = True,
        approve_overwrite: bool = False,
    ) -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        detected = CIProviderDetector(store).run(repo_path=".")
        selected = provider if provider != "auto" else str(detected.get("provider", "unknown_manual"))
        if selected == "github":
            plan = GitHubActionsGenerator().plan(repo_path=".", dry_run=dry_run, explicit_approval=approve_overwrite)
        elif selected == "gitlab":
            plan = GitLabCIGenerator().plan(repo_path=".", dry_run=dry_run, explicit_approval=approve_overwrite)
        elif selected == "jenkins":
            plan = JenkinsPipelineGenerator().plan(repo_path=".", dry_run=dry_run, explicit_approval=approve_overwrite)
        else:
            plan = {
                "provider": "unknown_manual",
                "dry_run": bool(dry_run),
                "explicit_approval": bool(approve_overwrite),
                "approval_required_for_overwrite": True,
                "apply_by_default": False,
                "file_plan": {
                    "path": "",
                    "exists": False,
                    "action": "manual_provider_selection_required",
                    "written": False,
                    "content_preview": "",
                },
                "summary": {"note": "No known CI provider selected."},
            }
        store.save_artifact("ci_workflow_plan", plan, agent="CICDPlan")
        return {
            "status": "ok",
            "provider": plan.get("provider", "unknown_manual"),
            "dry_run": bool(plan.get("dry_run", True)),
            "approval_required_for_overwrite": bool(plan.get("approval_required_for_overwrite", True)),
            "artifact": "ci_workflow_plan.json",
            "file_plan": plan.get("file_plan", {}),
        }

    def run_cicd_release_gate(self, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        current_report = store.load_artifact("cicd_audit_report")
        if not isinstance(current_report, dict):
            current_report = PRAuditRunner(store).run(changed_files=[])
        baseline = BaselineComparator(store).run(current=current_report)
        decision = ReleaseGateEngine(store).run(audit_report=current_report, baseline_comparison=baseline)
        report = CICDReporter(store).run()
        return {
            "status": "ok",
            "decision": decision.get("decision", "warning"),
            "artifacts": {
                "baseline_comparison": "baseline_comparison.json",
                "release_gate_decision": "release_gate_decision.json",
                "cicd_audit_report": "cicd_audit_report.json",
            },
            "provider": report.get("provider", "unknown_manual"),
        }

    def run_cicd_runtime_doctor(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        return self.run_cicd_runtime_detect(output_dir=output_dir)

    def run_cicd_runtime_detect(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        from qa_ai.cicd_runtime.ci_provider_detector import CIProviderDetector as RuntimeProviderDetector

        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        provider = RuntimeProviderDetector(store).run(repo_path=".")
        return {
            "status": "ok",
            "provider": provider.get("provider", "unknown_manual"),
            "known_provider": bool(provider.get("known_provider", False)),
            "artifact": "cicd_provider_report.json",
            "evidence": provider.get("evidence", []),
        }

    def run_cicd_runtime_plan(
        self,
        provider: str = "auto",
        output_dir: str = "artifacts",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        from qa_ai.cicd_runtime.ci_provider_detector import CIProviderDetector as RuntimeProviderDetector
        from qa_ai.cicd_runtime.github_actions_planner import GitHubActionsPlanner
        from qa_ai.cicd_runtime.gitlab_ci_planner import GitLabCIPlanner
        from qa_ai.cicd_runtime.jenkins_pipeline_planner import JenkinsPipelinePlanner

        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        detected = RuntimeProviderDetector(store).run(repo_path=".")
        selected = provider if provider != "auto" else str(detected.get("provider", "unknown_manual"))

        if selected == "github":
            plan = GitHubActionsPlanner(store).run(repo_path=".", dry_run=dry_run)
            artifact = "github_actions_plan.json"
        elif selected == "gitlab":
            plan = GitLabCIPlanner(store).run(repo_path=".", dry_run=dry_run)
            artifact = "gitlab_ci_plan.json"
        elif selected == "jenkins":
            plan = JenkinsPipelinePlanner(store).run(repo_path=".", dry_run=dry_run)
            artifact = "jenkins_pipeline_plan.json"
        else:
            plan = {
                "provider": selected,
                "dry_run": bool(dry_run),
                "advisory_only": True,
                "summary": {"note": "manual_provider_selection_required"},
            }
            artifact = "cicd_provider_report.json"

        return {
            "status": "ok",
            "provider": plan.get("provider", selected),
            "dry_run": bool(plan.get("dry_run", dry_run)),
            "advisory_only": bool(plan.get("advisory_only", True)),
            "artifact": artifact,
            "summary": plan.get("summary", {}),
        }

    def run_cicd_runtime_release_gate(self, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        from qa_ai.cicd_runtime.baseline_comparison_engine import BaselineComparisonEngine as RuntimeBaselineComparisonEngine
        from qa_ai.cicd_runtime.release_gate_engine import ReleaseGateEngine as RuntimeReleaseGateEngine
        from qa_ai.cicd_runtime.pipeline_policy_engine import PipelinePolicyEngine as RuntimePipelinePolicyEngine

        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        baseline = RuntimeBaselineComparisonEngine(store).run()
        decision = RuntimeReleaseGateEngine(store).run(baseline_report=baseline)
        policy = RuntimePipelinePolicyEngine(store).run(release_gate_decision=decision, baseline_report=baseline)
        return {
            "status": "ok",
            "decision": decision.get("decision", "warning"),
            "blocked_rules": policy.get("summary", {}).get("blocked_rules", []),
            "artifacts": {
                "baseline_comparison_report": "baseline_comparison_report.json",
                "release_gate_decision": "release_gate_decision.json",
                "pipeline_policy_report": "pipeline_policy_report.json",
            },
        }

    def run_cicd_runtime_pr_audit(self, target_path: str, output_dir: str = "artifacts") -> Dict[str, Any]:
        from qa_ai.cicd_runtime.pr_audit_orchestrator import PRAuditOrchestrator as RuntimePRAuditOrchestrator

        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        changed = self._discover_changed_files(target_path)
        report = RuntimePRAuditOrchestrator(store).run(changed_files=changed)
        return {
            "status": "ok",
            "artifact": "pr_audit_report.json",
            "changed_file_count": len(report.get("changed_file_audits", []))
            if isinstance(report.get("changed_file_audits"), list)
            else 0,
            "replay_regressions": int(report.get("replay_regressions", 0) or 0),
        }

    def run_performance_doctor(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        profile = PerformanceProfiler(store).run()
        phases = []
        workflow = store.load_artifact("workflow_result")
        if isinstance(workflow, dict):
            phases = [str(item.get("phase", "")) for item in workflow.get("phases", []) if isinstance(item, dict)]
        parallel = ParallelExecutionPlanner(store).run(phases=phases)
        graph_plan = IncrementalGraphManager(store).run(changed_files=[])
        memory = MemoryUsageTracker(store).run()
        return {
            "status": "ok",
            "artifact": "performance_profile.json",
            "slow_phase_count": int(profile.get("workflow_timing", {}).get("slow_phase_count", 0))
            if isinstance(profile.get("workflow_timing"), dict)
            else 0,
            "parallel_plan": parallel.get("summary", {}),
            "graph_plan": graph_plan.get("summary", {}),
            "memory_snapshot": memory.get("metrics", {}),
        }

    def run_performance_profile(self, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        profile = PerformanceProfiler(store).run()
        return {
            "status": "ok",
            "artifact": "performance_profile.json",
            "summary": profile.get("summary", {}),
        }

    def run_performance_lifecycle_plan(self, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        plan = ArtifactLifecycleManager(store).run()
        return {
            "status": "ok",
            "artifact": "artifact_lifecycle_plan.json",
            "summary": plan.get("summary", {}),
        }

    def run_performance_evidence_storage(self, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        report = EvidenceStorageOptimizer(store).run()
        return {
            "status": "ok",
            "artifact": "evidence_storage_report.json",
            "summary": report.get("summary", {}),
        }

    def run_scalability_report(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        report = ScalabilityReporter(store).run()
        return {
            "status": "ok",
            "artifact": "scalability_report.json",
            "summary": report.get("summary", {}),
            "artifacts": report.get("artifacts", {}),
        }

    def run_enterprise_doctor(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        summary = EnterpriseRuntimeOrchestrator(store).run()
        return {
            "status": "ok",
            "artifact": "enterprise_runtime_summary.json",
            "governance_health": summary.get("governance_health", "healthy"),
            "counts": summary.get("counts", {}),
        }

    def run_enterprise_workspaces(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        workspace = WorkspaceManager(store).run()
        project = ProjectRegistry(store).run(
            workspace_id=str((workspace.get("summary") or {}).get("active_workspace_id", "WS-DEFAULT"))
        )
        team = TeamRegistry(store).run()
        return {
            "status": "ok",
            "artifacts": {
                "workspace_registry": "workspace_registry.json",
                "project_registry": "project_registry.json",
                "team_registry": "team_registry.json",
            },
            "workspace_count": len(workspace.get("workspaces", [])) if isinstance(workspace.get("workspaces"), list) else 0,
            "project_count": len(project.get("projects", [])) if isinstance(project.get("projects"), list) else 0,
            "team_size": len(team.get("members", [])) if isinstance(team.get("members"), list) else 0,
        }

    def run_enterprise_governance_report(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        WorkspaceManager(store).run()
        ProjectRegistry(store).run()
        TeamRegistry(store).run()
        RoleEngine(store).run()
        PolicyEngine(store).run()
        AuditHistoryManager(store).run()
        summary = GovernanceReporter(store).run()
        access = AccessAuditLogger(store).run()
        return {
            "status": "ok",
            "artifact": "governance_summary.json",
            "governance_health": summary.get("governance_health", "healthy"),
            "access_log_entries": len(access.get("entries", [])) if isinstance(access.get("entries"), list) else 0,
        }

    def run_enterprise_audit_history(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        history = AuditHistoryManager(store).run()
        return {
            "status": "ok",
            "artifact": "audit_history_index.json",
            "run_count": len(history.get("runs", [])) if isinstance(history.get("runs"), list) else 0,
        }

    def run_benchmark_intelligence_datasets(self, output_dir: str = "artifacts", sample_root: str = "sample_apps") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        registry = BenchmarkDatasetManager(store).run(sample_root=sample_root)
        return {
            "status": "ok",
            "artifact": "benchmark_dataset_registry.json",
            "dataset_count": len(registry.get("datasets", [])) if isinstance(registry.get("datasets"), list) else 0,
        }

    def run_benchmark_intelligence_scoring(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        report = BenchmarkScoringEngine(store).run()
        FalsePositiveTracker(store).run()
        return {
            "status": "ok",
            "artifact": "benchmark_scoring_report.json",
            "overall_score": float(report.get("overall_score", 0.0) or 0.0),
        }

    def run_benchmark_intelligence_maturity(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        score = MaturityScoringEngine(store).run()
        return {
            "status": "ok",
            "artifact": "benchmark_maturity_score.json",
            "maturity_level": score.get("maturity_level", "developing"),
        }

    def run_benchmark_intelligence_trends(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        CoverageTrendAnalyzer(store).run()
        comparison = BenchmarkComparisonEngine(store).run()
        history = BenchmarkHistoryTracker(store).run()
        BenchmarkReporter(store).run()
        runtime = BenchmarkRuntimeOrchestrator(store).run(sample_root="sample_apps")
        return {
            "status": "ok",
            "artifact": "benchmark_runtime_summary.json",
            "signals": runtime.get("signals", {}),
            "history_runs": len(history.get("runs", [])) if isinstance(history.get("runs"), list) else 0,
            "improved_detection": bool(comparison.get("improved_detection", False)),
        }

    def run_self_optimize(
        self,
        artifacts_dir: str = "artifacts",
        workspace: str = "default",
        cross_project: bool = False,
    ) -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        summary = SelfOptimizationOrchestrator(store).run(workspace=workspace, cross_project=cross_project)
        return {
            "status": "ok",
            "artifact": "self_optimization_summary.json",
            "workspace": workspace,
            "cross_project": bool(cross_project),
            "advisory_only": bool(summary.get("advisory_only", True)),
            "artifact_backed_learning_only": bool(summary.get("artifact_backed_learning_only", True)),
            "automatic_source_modification": bool(summary.get("automatic_source_modification", False)),
            "external_upload": bool(summary.get("external_upload", False)),
            "counts": summary.get("counts", {}),
        }

    def run_models_doctor(self, output_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(output_dir).expanduser().resolve())
        router = ModelRouter(artifact_store=store)
        report = router.doctor()
        store.save_artifact("model_routing_report", report, agent="ModelsDoctor")
        return report

    def run_models_routing(self, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        payload = store.load_artifact("model_routing_report")
        if isinstance(payload, dict) and payload:
            return {"status": "ok", "artifact": "model_routing_report.json", "report": payload}
        report = ModelRouter(artifact_store=store).get_routing_report()
        return {"status": "ok", "artifact": "model_routing_report.json", "report": report}

    def run_models_test(self, component: str, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        router = ModelRouter(artifact_store=store)
        comp = RoutingComponent(component)
        result = router.route(
            component=comp,
            prompt="Return a short JSON object with keys status and component.",
            context={"contains_private_code": False},
            require_json=False,
            deterministic_fallback=lambda: "{\"status\":\"deterministic\",\"component\":\"%s\"}" % component,
        )
        return {
            "status": "ok" if result.success else "failed",
            "component": component,
            "provider": result.provider,
            "model": result.model,
            "content_preview": result.content[:200],
            "artifact": "model_usage_log.json",
        }

    def run_models_privacy_check(self, artifacts_dir: str = "artifacts") -> Dict[str, Any]:
        store = ArtifactStore(base_dir=Path(artifacts_dir).expanduser().resolve())
        router = ModelRouter(artifact_store=store)
        result = router.route(
            component=RoutingComponent.MASTER_ORCHESTRATION,
            prompt="private code snippet should not go to cloud",
            context={"contains_private_code": True, "graphify_summary": "graph summary redacted"},
            deterministic_fallback=lambda: "deterministic-privacy-safe",
        )
        safe_provider = result.provider in {"ollama", "deterministic"} or (
            result.provider == "openrouter" and bool(router.settings.redact_cloud_context)
        )
        return {
            "status": "ok" if result.success else "failed",
            "safe": safe_provider,
            "provider": result.provider,
            "model": result.model,
            "artifact": "model_routing_report.json",
        }

    def run_models_route(self, task: str) -> Dict[str, Any]:
        """Show which model/provider would be selected for a given task."""
        try:
            from qa_ai.ai.task_profiles import ModelTask, get_default_task_routes
            from qa_ai.ai.resource_manager import get_resource_manager

            task_enum = ModelTask(task)
            routes = get_default_task_routes()
            route = routes.get(task_enum)
            if not route:
                return {"status": "error", "error": f"No route configured for task: {task!r}"}

            rm = get_resource_manager()
            return {
                "status": "ok",
                "task": task,
                "primary_model": route.model,
                "provider": route.provider,
                "fallback_models": list(route.fallback_models),
                "temperature": route.temperature,
                "timeout_seconds": route.timeout_seconds,
                "estimated_memory_gb": route.estimated_memory_gb,
                "supports_vision": route.supports_vision,
                "local_only": route.local_only,
                "resource_policy": rm.memory_policy_summary(),
            }
        except ValueError:
            valid = [t.value for t in ModelTask]
            return {"status": "error", "error": f"Unknown task: {task!r}. Valid: {valid}"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def run_models_benchmark(self, quick: bool = True, allow_cloud: bool = False) -> Dict[str, Any]:
        """Run lightweight local model benchmark (dry_run=True, approved=False by default)."""
        try:
            from qa_ai.ai.model_benchmarker import run_benchmark
            report = run_benchmark(approved=False, dry_run=True, quick=quick)
            return {
                "status": "ok",
                "generated_at": report.generated_at,
                "dry_run": report.dry_run,
                "quick_mode": report.quick_mode,
                "summary": report.summary,
                "entries": [
                    {
                        "model": e.model,
                        "task": e.task,
                        "latency_ms": e.latency_ms,
                        "status": e.status,
                        "error": e.error,
                        "recommendation": e.recommendation,
                    }
                    for e in report.entries
                ],
                "note": (
                    "Dry run only — no real model calls. "
                    "Use POST /api/models/benchmark?approved=true for live benchmark."
                ),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def run_models_hardware(self) -> Dict[str, Any]:
        """Detect hardware profile and show recommended runtime configuration."""
        try:
            from qa_ai.model_runtime.hardware_detector import detect_hardware

            hw = detect_hardware()
            return {
                "status": "ok",
                "platform": hw.platform,
                "architecture": hw.architecture,
                "total_ram_gb": hw.total_ram_gb,
                "available_ram_gb": hw.available_ram_gb,
                "apple_silicon": hw.apple_silicon,
                "cuda_available": hw.cuda_available,
                "metal_available": hw.metal_available,
                "gpu_label": hw.gpu_label,
                "inside_container": hw.inside_container,
                "recommended_profile": hw.recommended_profile,
                "detection_confidence": hw.detection_confidence,
                "warnings": hw.warnings,
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def run_models_list_profiles(self) -> Dict[str, Any]:
        """List all available adaptive resource profiles."""
        try:
            from qa_ai.model_runtime.adaptive_profiles import get_all_profiles

            profiles_dict = get_all_profiles()
            profiles = list(profiles_dict.values())
            return {
                "status": "ok",
                "profiles": [
                    {
                        "profile_id": p.profile_id,
                        "name": p.name,
                        "description": p.description,
                        "max_parallel_model_calls": p.max_parallel_model_calls,
                        "max_model_memory_gb": p.max_model_memory_gb,
                        "allow_heavy_models": p.allow_heavy_models,
                        "avoid_heavy_models": p.avoid_heavy_models,
                        "vision_enabled_by_default": p.vision_enabled_by_default,
                        "prefer_deterministic_when_low_resource": p.prefer_deterministic_when_low_resource,
                        "recommended_context_tokens": p.recommended_context_tokens,
                        "notes": p.notes,
                    }
                    for p in profiles
                ],
                "count": len(profiles),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def run_models_auto_profile(self) -> Dict[str, Any]:
        """Auto-detect hardware and return full routing plan for this machine."""
        try:
            from qa_ai.model_runtime.profile_selector import select_profile
            from qa_ai.model_runtime.profile_reporter import build_profile_report, format_profile_summary_text

            selected = select_profile()
            report = build_profile_report(selected)
            report["status"] = "ok"
            report["summary_text"] = format_profile_summary_text(selected)
            return report
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def run_models_discover(
        self,
        probe_lmstudio: bool = True,
        probe_llamacpp: bool = True,
    ) -> Dict[str, Any]:
        """Discover locally running LLM providers."""
        try:
            from qa_ai.model_runtime.provider_discovery import discover_providers

            providers = discover_providers(
                probe_lmstudio=probe_lmstudio,
                probe_llamacpp=probe_llamacpp,
            )
            return {
                "status": "ok",
                "providers": [
                    {
                        "provider_id": p.provider_id,
                        "provider_type": p.provider_type,
                        "base_url": p.base_url,
                        "models": p.models,
                        "reachable": p.reachable,
                    }
                    for p in providers
                ],
                "reachable_count": sum(1 for p in providers if p.reachable),
                "total_models": sum(len(p.models) for p in providers if p.reachable),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def run_models_apply_profile(self, profile_id: str) -> Dict[str, Any]:
        """Apply a named adaptive profile and show resulting task routes."""
        try:
            from qa_ai.model_runtime.profile_selector import select_profile
            from qa_ai.model_runtime.profile_reporter import build_profile_report, format_profile_summary_text
            from qa_ai.model_runtime.adaptive_profiles import get_profile_by_id

            profile = get_profile_by_id(profile_id)
            if profile is None:
                from qa_ai.model_runtime.adaptive_profiles import get_all_profiles
                valid_ids = list(get_all_profiles().keys())
                return {
                    "status": "error",
                    "error": f"Unknown profile_id: {profile_id!r}. Valid: {valid_ids}",
                }

            selected = select_profile(profile_override=profile_id)
            report = build_profile_report(selected)
            report["status"] = "ok"
            report["applied_profile_id"] = profile_id
            report["summary_text"] = format_profile_summary_text(selected)
            return report
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _discover_changed_files(self, target_path: str) -> List[str]:
        root = Path(target_path).expanduser().resolve()
        if not root.exists():
            return []
        command = ["git", "-C", str(root), "diff", "--name-only", "HEAD~1", "HEAD"]
        probe = subprocess.run(command, capture_output=True, text=True, check=False)
        if probe.returncode != 0:
            probe = subprocess.run(
                ["git", "-C", str(root), "diff", "--name-only"],
                capture_output=True,
                text=True,
                check=False,
            )
        if probe.returncode != 0:
            return []
        changed = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
        return sorted(set(changed))

    def _check_command(self, command: List[str]) -> Dict[str, Any]:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            return {
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _check_module(self, module_name: str) -> Dict[str, Any]:
        spec = importlib.util.find_spec(module_name)
        return {"ok": spec is not None, "module": module_name}

    def _check_graphify_outputs(self) -> Dict[str, Any]:
        report_path = Path("graphify-out/GRAPH_REPORT.md")
        graph_path = Path("graphify-out/graph.json")
        graph_ok = False
        nodes = 0
        edges = 0
        if graph_path.exists():
            try:
                payload = json.loads(graph_path.read_text(encoding="utf-8"))
                node_list = payload.get("nodes", [])
                edge_list = payload.get("edges") or payload.get("links") or []
                nodes = len(node_list) if isinstance(node_list, list) else 0
                edges = len(edge_list) if isinstance(edge_list, list) else 0
                graph_ok = True
            except (OSError, json.JSONDecodeError):
                graph_ok = False
        return {
            "ok": report_path.exists() and graph_ok,
            "report_exists": report_path.exists(),
            "graph_exists": graph_path.exists(),
            "nodes": nodes,
            "edges": edges,
        }

    # ── Memory kernel CLI commands ─────────────────────────────────────────────

    def run_memory_command(self, args) -> Any:
        """Dispatch memory subcommands."""
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService()
        cmd = args.memory_command

        if cmd == "stats":
            return {"status": "ok", "stats": svc.stats(args.scope)}

        if cmd == "report":
            report = svc.scope_report(scope_id=args.scope, format=args.format)
            if args.format == "markdown":
                return report  # raw string
            return {"status": "ok", "report": report}

        if cmd == "patterns":
            return svc.get_patterns(
                scope_id=args.scope,
                pattern_type=getattr(args, "type", None),
                min_confidence=getattr(args, "min_confidence", 0.0),
                limit=50,
            )

        if cmd == "recall":
            return svc.recall(
                scope_id=args.scope,
                query=args.query,
                top_k=getattr(args, "top_k", 10),
            )

        if cmd == "retention":
            dry_run = not getattr(args, "execute", False)
            return svc.run_retention(
                scope_id=args.scope,
                dry_run=dry_run,
                max_delete_per_run=getattr(args, "max_delete", 500),
            )

        if cmd == "baseline":
            baseline = svc.get_active_baseline(scope_id=args.scope)
            return {"status": "ok", "baseline": baseline}

        return {"status": "error", "error": f"Unknown memory command: {cmd!r}"}
