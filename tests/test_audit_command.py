"""
test_audit_command.py - Tests for audit/report/doctor CLI command handlers.
"""

from types import SimpleNamespace
from pathlib import Path

import qa_ai.cli.audit_command as audit_module
from qa_ai.cli.audit_command import AuditCommand
from qa_ai.cli.profile_manager import ProfileManager


def _manager() -> ProfileManager:
    config_dir = Path(__file__).resolve().parents[1] / "qa_ai" / "config"
    return ProfileManager(config_dir)


class TestAuditCommand:
    def test_audit_dry_run_generates_summary(self, tmp_dir):
        target = tmp_dir / "sample_app"
        target.mkdir(parents=True)
        cmd = AuditCommand(profile_manager=_manager())

        result = cmd.run(
            target_path=str(target),
            profile="web",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=True,
        )

        assert result["status"] == "dry_run"
        assert result["profile"] == "web"
        assert result["dry_run"] is True

    def test_audit_invalid_profile_fails_safely(self, tmp_dir):
        target = tmp_dir / "sample_app"
        target.mkdir(parents=True)
        cmd = AuditCommand(profile_manager=_manager())

        result = cmd.run(
            target_path=str(target),
            profile="missing",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=False,
        )

        assert result["status"] == "failed"
        assert any("Unknown profile" in err for err in result["errors"])

    def test_audit_missing_target_fails_safely(self, tmp_dir):
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run(
            target_path=str(tmp_dir / "does-not-exist"),
            profile="web",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=False,
        )
        assert result["status"] == "failed"
        assert any("Target path does not exist" in err for err in result["errors"])

    def test_audit_executes_workflow_with_profile_phases(self, tmp_dir, monkeypatch):
        target = tmp_dir / "sample_app"
        target.mkdir(parents=True)

        captured = {}

        class FakeWorkflowEngine:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, app_path, app_name, platform, phases):
                captured["app_path"] = app_path
                captured["app_name"] = app_name
                captured["platform"] = platform.value
                captured["phases"] = [p.value for p in phases]
                return SimpleNamespace(
                    run_id="run_fake123",
                    status=SimpleNamespace(value="completed"),
                    phases=[SimpleNamespace(phase=SimpleNamespace(value="discovery"))],
                )

        monkeypatch.setattr(audit_module, "WorkflowEngine", FakeWorkflowEngine)
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run(
            target_path=str(target),
            profile="api",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=False,
        )

        assert result["status"] == "completed"
        assert result["run_id"] == "run_fake123"
        assert captured["app_path"] == str(target.resolve())
        assert "discovery" in captured["phases"]

    def test_audit_ai_reasoning_runs_after_workflow(self, tmp_dir, monkeypatch):
        target = tmp_dir / "sample_app"
        target.mkdir(parents=True)
        captured = {"ai_called": False}

        class FakeWorkflowEngine:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, app_path, app_name, platform, phases):
                return SimpleNamespace(
                    run_id="run_fake123",
                    status=SimpleNamespace(value="completed"),
                    phases=[SimpleNamespace(phase=SimpleNamespace(value="discovery"))],
                )

        class FakeAIOrchestrator:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, enabled=True, dry_run=True):
                captured["ai_called"] = True
                return {"mode": "deterministic_fallback"}

        monkeypatch.setattr(audit_module, "WorkflowEngine", FakeWorkflowEngine)
        monkeypatch.setattr(audit_module, "AIReasoningOrchestrator", FakeAIOrchestrator)

        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run(
            target_path=str(target),
            profile="api",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=False,
            ai_reasoning=True,
        )

        assert result["status"] == "completed"
        assert captured["ai_called"] is True
        assert result["ai_reasoning"]["artifact"] == "ai_reasoning_summary.json"

    def test_audit_ai_first_runs_brain_orchestrator(self, tmp_dir, monkeypatch):
        target = tmp_dir / "sample_app"
        target.mkdir(parents=True)
        captured = {"ai_first_called": False}

        class FakeWorkflowEngine:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, app_path, app_name, platform, phases):
                return SimpleNamespace(
                    run_id="run_fake123",
                    status=SimpleNamespace(value="completed"),
                    phases=[SimpleNamespace(phase=SimpleNamespace(value="discovery"))],
                )

        class FakeAIAuditOrchestrator:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, app_path="", dry_run=True, enabled=True):
                captured["ai_first_called"] = True
                return {"mode": "deterministic_fallback", "overall_confidence": 0.71}

        monkeypatch.setattr(audit_module, "WorkflowEngine", FakeWorkflowEngine)
        monkeypatch.setattr(audit_module, "AIAuditOrchestrator", FakeAIAuditOrchestrator)

        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run(
            target_path=str(target),
            profile="api",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=False,
            ai_first=True,
        )
        assert result["status"] == "completed"
        assert captured["ai_first_called"] is True
        assert result["ai_first"]["artifact"] == "ai_audit_brain_summary.json"

    def test_run_ai_audit_wraps_ai_first(self, tmp_dir, monkeypatch):
        target = tmp_dir / "sample_app"
        target.mkdir(parents=True)
        captured = {}

        def fake_run(self, target_path, profile, output_dir="artifacts", dry_run=False, ai_reasoning=False, ci_mode=False, ai_first=False):
            captured["ai_first"] = ai_first
            return {"status": "ok"}

        monkeypatch.setattr(audit_module.AuditCommand, "run", fake_run)
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_ai_audit(target_path=str(target), profile="full_stack", output_dir=str(tmp_dir / "artifacts"), dry_run=True)
        assert result["status"] == "ok"
        assert captured["ai_first"] is True

    def test_doctor_generates_doctor_report_artifact(self, tmp_dir):
        cmd = AuditCommand(profile_manager=_manager())
        report = cmd.run_doctor(output_dir=str(tmp_dir / "artifacts"))

        assert "status" in report
        assert "checks" in report
        assert "python" in report["checks"]
        assert (tmp_dir / "artifacts" / "doctor_report.json").exists()

    def test_report_regeneration_outputs_expected_files(self, tmp_dir):
        artifacts = tmp_dir / "artifacts"
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_report(artifacts_dir=str(artifacts))

        assert result["status"] == "ok"
        assert (artifacts / "reports" / "audit_dashboard.html").exists()
        assert (artifacts / "reports" / "executive_report.html").exists()
        assert (artifacts / "reports" / "technical_report.html").exists()

    def test_benchmark_command_generates_outputs(self, tmp_dir, monkeypatch):
        class FakeBenchmarkRunner:
            def run(self, sample_root, output_dir="artifacts", execute=False):
                return {
                    "benchmark_root": sample_root,
                    "apps": [{"app_name": "demo", "findings": []}],
                    "totals": {"apps_total": 1, "findings_total": 0},
                }

        class FakeDetectionMetrics:
            def run(self, benchmark_summary):
                return {"metrics": {"issue_coverage": 0.0}, "per_app": []}

        class FakeToolComparison:
            def run(self, benchmark_summary=None, benchmark_metrics=None):
                return {"qa_ai": {"integrated_depth": "ok"}}

        class FakeBenchmarkReport:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, benchmark_summary=None, benchmark_metrics=None, comparison=None):
                self.store.save_artifact("benchmark_summary", benchmark_summary or {}, agent="test")
                self.store.save_artifact("benchmark_metrics", benchmark_metrics or {}, agent="test")
                self.store.save_report("benchmark_report.html", "<html></html>")
                return {
                    "benchmark_summary": "benchmark_summary.json",
                    "benchmark_metrics": "benchmark_metrics.json",
                    "benchmark_report": "benchmark_report.html",
                }

        monkeypatch.setattr(audit_module, "BenchmarkRunner", FakeBenchmarkRunner)
        monkeypatch.setattr(audit_module, "DetectionMetrics", FakeDetectionMetrics)
        monkeypatch.setattr(audit_module, "ToolComparison", FakeToolComparison)
        monkeypatch.setattr(audit_module, "BenchmarkReport", FakeBenchmarkReport)

        artifacts = tmp_dir / "artifacts"
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_benchmark(sample_root="sample_apps", output_dir=str(artifacts), execute=False)

        assert result["status"] == "ok"
        assert result["apps_benchmarked"] == 1
        assert (artifacts / "benchmark_summary.json").exists()
        assert (artifacts / "benchmark_metrics.json").exists()

    def test_live_benchmark_command_path(self, tmp_dir, monkeypatch):
        class FakeLiveBenchmarkRunner:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, sample_root, output_dir="artifacts", dry_run=True):
                self.store.save_artifact("live_benchmark_summary", {"apps": []}, agent="test")
                self.store.save_artifact("live_benchmark_metrics", {"metrics": {}}, agent="test")
                return {
                    "status": "ok",
                    "benchmark_root": sample_root,
                    "apps_benchmarked": 0,
                    "findings_total": 0,
                    "dry_run": dry_run,
                    "artifacts": {
                        "live_benchmark_summary": "live_benchmark_summary.json",
                        "live_benchmark_metrics": "live_benchmark_metrics.json",
                    },
                }

        monkeypatch.setattr(audit_module, "LiveBenchmarkRunner", FakeLiveBenchmarkRunner)
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_benchmark(
            sample_root="sample_apps",
            output_dir=str(tmp_dir / "artifacts"),
            live=True,
            dry_run=True,
        )
        assert result["status"] == "ok"
        assert result["dry_run"] is True

    def test_runtime_lab_doctor_generates_report_artifact(self, tmp_dir):
        cmd = AuditCommand(profile_manager=_manager())
        report = cmd.run_runtime_lab_doctor(output_dir=str(tmp_dir / "artifacts"))
        assert "status" in report
        assert "checks" in report
        assert (tmp_dir / "artifacts" / "runtime_lab_doctor_report.json").exists()

    def test_distributed_runtime_command_generates_artifacts(self, tmp_dir):
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_distributed_runtime(
            sample_path="sample_apps/sync_conflict_demo",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=True,
            actors=["cashier", "manager", "background_sync"],
        )

        assert result["status"] == "ok"
        assert result["dry_run"] is True
        assert result["artifacts"]["distributed_runtime_report"] == "distributed_runtime_report.json"
        assert (tmp_dir / "artifacts" / "distributed_runtime_report.json").exists()
        assert (tmp_dir / "artifacts" / "actor_registry.json").exists()
        assert (tmp_dir / "artifacts" / "concurrency_analysis.json").exists()

    def test_benchmark_distributed_path_uses_distributed_runtime(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_distributed_runtime(self, sample_path, output_dir="artifacts", dry_run=True, actors=None):
            captured["sample_path"] = sample_path
            captured["dry_run"] = dry_run
            return {
                "status": "ok",
                "app_path": sample_path,
                "summary": {"anomaly_count": 3},
                "artifacts": {"distributed_runtime_report": "distributed_runtime_report.json"},
            }

        monkeypatch.setattr(audit_module.AuditCommand, "run_distributed_runtime", fake_distributed_runtime)
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_benchmark(
            sample_root="sample_apps/sync_conflict_demo",
            output_dir=str(tmp_dir / "artifacts"),
            live=True,
            dry_run=False,
            distributed=True,
        )

        assert result["status"] == "ok"
        assert result["distributed"] is True
        assert result["findings_total"] == 3
        assert captured["sample_path"] == "sample_apps/sync_conflict_demo"
        assert captured["dry_run"] is True

    def test_mobile_runtime_command_generates_artifacts(self, tmp_dir):
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_mobile_runtime(
            sample_path="sample_apps/flutter_offline_app",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=True,
            distributed=True,
        )

        assert result["status"] == "ok"
        assert result["dry_run"] is True
        assert result["distributed"] is True
        assert (tmp_dir / "artifacts" / "mobile_runtime_report.json").exists()
        assert (tmp_dir / "artifacts" / "device_registry.json").exists()

    def test_benchmark_mobile_path_uses_mobile_runtime(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_mobile_runtime(self, sample_path, output_dir="artifacts", dry_run=True, distributed=False):
            captured["sample_path"] = sample_path
            captured["dry_run"] = dry_run
            captured["distributed"] = distributed
            return {
                "status": "ok",
                "app_path": sample_path,
                "summary": {"critical_mobile_signals": 2},
                "artifacts": {"mobile_runtime_report": "mobile_runtime_report.json"},
            }

        monkeypatch.setattr(audit_module.AuditCommand, "run_mobile_runtime", fake_mobile_runtime)
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_benchmark(
            sample_root="sample_apps/flutter_offline_app",
            output_dir=str(tmp_dir / "artifacts"),
            execute=False,
            live=True,
            distributed=True,
            mobile=True,
        )

        assert result["status"] == "ok"
        assert result["mobile"] is True
        assert result["distributed"] is True
        assert result["findings_total"] == 2
        assert captured["sample_path"] == "sample_apps/flutter_offline_app"
        assert captured["dry_run"] is True
        assert captured["distributed"] is True

    def test_benchmark_ai_reasoning_path(self, tmp_dir, monkeypatch):
        class FakeBenchmarkRunner:
            def run(self, sample_root, output_dir="artifacts", execute=False):
                return {
                    "benchmark_root": sample_root,
                    "apps": [],
                    "totals": {"apps_total": 0, "findings_total": 0},
                }

        class FakeDetectionMetrics:
            def run(self, benchmark_summary):
                return {"metrics": {}, "per_app": []}

        class FakeToolComparison:
            def run(self, benchmark_summary=None, benchmark_metrics=None):
                return {}

        class FakeBenchmarkReport:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, benchmark_summary=None, benchmark_metrics=None, comparison=None):
                return {}

        captured = {"ai_called": False}

        class FakeAIOrchestrator:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, enabled=True, dry_run=True):
                captured["ai_called"] = True
                return {"mode": "deterministic_fallback"}

        monkeypatch.setattr(audit_module, "BenchmarkRunner", FakeBenchmarkRunner)
        monkeypatch.setattr(audit_module, "DetectionMetrics", FakeDetectionMetrics)
        monkeypatch.setattr(audit_module, "ToolComparison", FakeToolComparison)
        monkeypatch.setattr(audit_module, "BenchmarkReport", FakeBenchmarkReport)
        monkeypatch.setattr(audit_module, "AIReasoningOrchestrator", FakeAIOrchestrator)

        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_benchmark(
            sample_root="sample_apps",
            output_dir=str(tmp_dir / "artifacts"),
            execute=False,
            ai_reasoning=True,
        )
        assert result["status"] == "ok"
        assert captured["ai_called"] is True
        assert result["ai_reasoning"]["artifact"] == "ai_reasoning_summary.json"

    def test_ai_reasoning_command_generates_summary(self, tmp_dir, monkeypatch):
        class FakeAIOrchestrator:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, enabled=True, dry_run=True):
                self.store.save_artifact("ai_reasoning_summary", {"mode": "deterministic_fallback"}, agent="test")
                return {"mode": "deterministic_fallback", "model_available": False, "artifacts": {}}

        monkeypatch.setattr(audit_module, "AIReasoningOrchestrator", FakeAIOrchestrator)
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_ai_reasoning(artifacts_dir=str(tmp_dir / "artifacts"), dry_run=True)
        assert result["status"] == "ok"
        assert result["artifact"] == "ai_reasoning_summary.json"
        assert (tmp_dir / "artifacts" / "ai_reasoning_summary.json").exists()

    def test_cicd_doctor_generates_provider_artifact(self, tmp_dir):
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_cicd_doctor(output_dir=str(tmp_dir / "artifacts"))
        assert result["status"] == "ok"
        assert (tmp_dir / "artifacts" / "cicd_provider_report.json").exists()

    def test_cicd_plan_generates_ci_workflow_plan(self, tmp_dir):
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_cicd_plan(
            provider="github",
            output_dir=str(tmp_dir / "artifacts"),
            dry_run=True,
            approve_overwrite=False,
        )
        assert result["status"] == "ok"
        assert result["artifact"] == "ci_workflow_plan.json"
        assert (tmp_dir / "artifacts" / "ci_workflow_plan.json").exists()

    def test_cicd_release_gate_generates_decision_artifact(self, tmp_dir):
        artifacts = tmp_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_cicd_release_gate(artifacts_dir=str(artifacts))
        assert result["status"] == "ok"
        assert (artifacts / "release_gate_decision.json").exists()

    def test_performance_doctor_generates_profile_artifact(self, tmp_dir):
        cmd = AuditCommand(profile_manager=_manager())
        result = cmd.run_performance_doctor(output_dir=str(tmp_dir / "artifacts"))
        assert result["status"] == "ok"
        assert (tmp_dir / "artifacts" / "performance_profile.json").exists()
        assert (tmp_dir / "artifacts" / "parallel_execution_plan.json").exists()
        assert (tmp_dir / "artifacts" / "incremental_graph_plan.json").exists()
        assert (tmp_dir / "artifacts" / "memory_usage_report.json").exists()

    def test_performance_profile_lifecycle_evidence_and_scalability(self, tmp_dir):
        artifacts = tmp_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        cmd = AuditCommand(profile_manager=_manager())

        profile = cmd.run_performance_profile(artifacts_dir=str(artifacts))
        lifecycle = cmd.run_performance_lifecycle_plan(artifacts_dir=str(artifacts))
        evidence = cmd.run_performance_evidence_storage(artifacts_dir=str(artifacts))
        scalability = cmd.run_scalability_report(output_dir=str(artifacts))

        assert profile["status"] == "ok"
        assert lifecycle["status"] == "ok"
        assert evidence["status"] == "ok"
        assert scalability["status"] == "ok"
        assert (artifacts / "performance_profile.json").exists()
        assert (artifacts / "artifact_lifecycle_plan.json").exists()
        assert (artifacts / "evidence_storage_report.json").exists()
        assert (artifacts / "scalability_report.json").exists()

    def test_enterprise_commands_generate_governance_artifacts(self, tmp_dir):
        artifacts = tmp_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        cmd = AuditCommand(profile_manager=_manager())

        doctor = cmd.run_enterprise_doctor(output_dir=str(artifacts))
        workspaces = cmd.run_enterprise_workspaces(output_dir=str(artifacts))
        governance = cmd.run_enterprise_governance_report(output_dir=str(artifacts))
        history = cmd.run_enterprise_audit_history(output_dir=str(artifacts))

        assert doctor["status"] == "ok"
        assert workspaces["status"] == "ok"
        assert governance["status"] == "ok"
        assert history["status"] == "ok"
        assert (artifacts / "enterprise_runtime_summary.json").exists()
        assert (artifacts / "workspace_registry.json").exists()
        assert (artifacts / "governance_summary.json").exists()
        assert (artifacts / "audit_history_index.json").exists()

    def test_benchmark_intelligence_commands_generate_artifacts(self, tmp_dir):
        artifacts = tmp_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        cmd = AuditCommand(profile_manager=_manager())

        datasets = cmd.run_benchmark_intelligence_datasets(output_dir=str(artifacts), sample_root=str(tmp_dir))
        scoring = cmd.run_benchmark_intelligence_scoring(output_dir=str(artifacts))
        maturity = cmd.run_benchmark_intelligence_maturity(output_dir=str(artifacts))
        trends = cmd.run_benchmark_intelligence_trends(output_dir=str(artifacts))

        assert datasets["status"] == "ok"
        assert scoring["status"] == "ok"
        assert maturity["status"] == "ok"
        assert trends["status"] == "ok"
        assert (artifacts / "benchmark_dataset_registry.json").exists()
        assert (artifacts / "benchmark_scoring_report.json").exists()
        assert (artifacts / "benchmark_maturity_score.json").exists()
        assert (artifacts / "benchmark_runtime_summary.json").exists()

    def test_self_optimize_command_generates_summary_artifact(self, tmp_dir):
        artifacts = tmp_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        cmd = AuditCommand(profile_manager=_manager())

        result = cmd.run_self_optimize(
            artifacts_dir=str(artifacts),
            workspace="default",
            cross_project=True,
        )

        assert result["status"] == "ok"
        assert result["workspace"] == "default"
        assert result["cross_project"] is True
        assert result["advisory_only"] is True
        assert result["artifact_backed_learning_only"] is True
        assert result["automatic_source_modification"] is False
        assert result["external_upload"] is False
        assert (artifacts / "self_optimization_summary.json").exists()
