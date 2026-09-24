"""
test_cli_main.py - Tests for top-level QA-AI CLI command parsing and routing.
"""

import qa_ai.cli.main as cli_main
from qa_ai.cli.main import main


class TestCliMain:
    def test_profiles_command_lists_profiles(self, capsys):
        rc = main(["profiles"])
        out = capsys.readouterr().out

        assert rc == 0
        assert "web" in out
        assert "api" in out

    def test_audit_command_dry_run(self, tmp_dir):
        target = tmp_dir / "sample_app"
        target.mkdir(parents=True)
        artifacts = tmp_dir / "artifacts"

        rc = main(
            [
                "audit",
                str(target),
                "--profile",
                "web",
                "--dry-run",
                "--output-dir",
                str(artifacts),
            ]
        )

        assert rc == 0
        assert (artifacts / "run_summary.json").exists()

    def test_audit_ai_reasoning_flag_is_parsed(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_run(self, target_path, profile, output_dir="artifacts", dry_run=False, ai_reasoning=False, ci_mode=False, ai_first=False):
            captured["ai_reasoning"] = ai_reasoning
            captured["ci_mode"] = ci_mode
            captured["ai_first"] = ai_first
            return {"status": "dry_run"}

        monkeypatch.setattr(cli_main.AuditCommand, "run", fake_run)
        rc = main(
            [
                "audit",
                str(tmp_dir),
                "--profile",
                "web",
                "--ai-reasoning",
                "--dry-run",
            ]
        )
        assert rc == 0
        assert captured["ai_reasoning"] is True
        assert captured["ci_mode"] is False
        assert captured["ai_first"] is False

    def test_audit_ci_mode_flag_is_parsed(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_run(self, target_path, profile, output_dir="artifacts", dry_run=False, ai_reasoning=False, ci_mode=False, ai_first=False):
            captured["ci_mode"] = ci_mode
            captured["ai_first"] = ai_first
            return {"status": "dry_run"}

        monkeypatch.setattr(cli_main.AuditCommand, "run", fake_run)
        rc = main(
            [
                "audit",
                str(tmp_dir),
                "--profile",
                "full_stack",
                "--ci-mode",
                "--dry-run",
            ]
        )
        assert rc == 0
        assert captured["ci_mode"] is True
        assert captured["ai_first"] is False

    def test_audit_ai_first_flag_is_parsed(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_run(self, target_path, profile, output_dir="artifacts", dry_run=False, ai_reasoning=False, ci_mode=False, ai_first=False):
            captured["ai_first"] = ai_first
            return {"status": "dry_run"}

        monkeypatch.setattr(cli_main.AuditCommand, "run", fake_run)
        rc = main(
            [
                "audit",
                str(tmp_dir),
                "--profile",
                "full_stack",
                "--ai-first",
                "--dry-run",
            ]
        )
        assert rc == 0
        assert captured["ai_first"] is True

    def test_ai_audit_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_run_ai_audit(self, target_path, profile="full_stack", output_dir="artifacts", dry_run=False):
            captured["target_path"] = target_path
            captured["profile"] = profile
            captured["output_dir"] = output_dir
            captured["dry_run"] = dry_run
            return {"status": "ok"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_ai_audit", fake_run_ai_audit)
        rc = main(["ai-audit", str(tmp_dir), "--profile", "full_stack", "--dry-run"])
        assert rc == 0
        assert captured["profile"] == "full_stack"
        assert captured["dry_run"] is True

    def test_report_command_regenerates_dashboard(self, tmp_dir):
        artifacts = tmp_dir / "artifacts"
        rc = main(["report", str(artifacts)])

        assert rc == 0
        assert (artifacts / "reports" / "audit_dashboard.html").exists()
        assert (artifacts / "reports" / "technical_report.html").exists()

    def test_doctor_command_generates_report(self, tmp_dir):
        artifacts = tmp_dir / "artifacts"
        rc = main(["doctor", "--output-dir", str(artifacts)])

        assert rc in (0, 1)
        assert (artifacts / "doctor_report.json").exists()

    def test_benchmark_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_run_benchmark(
            self,
            sample_root,
            output_dir="artifacts",
            execute=False,
            live=False,
            dry_run=False,
            distributed=False,
            mobile=False,
            ai_reasoning=False,
            ai_first=False,
        ):
            captured["live"] = live
            captured["dry_run"] = dry_run
            captured["distributed"] = distributed
            captured["mobile"] = mobile
            captured["ai_reasoning"] = ai_reasoning
            captured["ai_first"] = ai_first
            return {
                "status": "ok",
                "benchmark_root": sample_root,
                "apps_benchmarked": 5,
                "findings_total": 12,
                "artifacts": {
                    "benchmark_summary": "benchmark_summary.json",
                    "benchmark_metrics": "benchmark_metrics.json",
                    "benchmark_report": "benchmark_report.html",
                },
            }

        monkeypatch.setattr(cli_main.AuditCommand, "run_benchmark", fake_run_benchmark)

        rc = main(["benchmark", "sample_apps", "--output-dir", str(tmp_dir / "artifacts"), "--live", "--dry-run"])
        assert rc == 0
        assert captured["live"] is True
        assert captured["dry_run"] is True
        assert captured["distributed"] is False
        assert captured["mobile"] is False
        assert captured["ai_reasoning"] is False
        assert captured["ai_first"] is False

    def test_benchmark_distributed_flag_is_parsed(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_run_benchmark(
            self,
            sample_root,
            output_dir="artifacts",
            execute=False,
            live=False,
            dry_run=False,
            distributed=False,
            mobile=False,
            ai_reasoning=False,
            ai_first=False,
        ):
            captured["sample_root"] = sample_root
            captured["distributed"] = distributed
            captured["dry_run"] = dry_run
            captured["mobile"] = mobile
            captured["ai_reasoning"] = ai_reasoning
            captured["ai_first"] = ai_first
            return {"status": "ok", "artifacts": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_benchmark", fake_run_benchmark)
        rc = main(
            [
                "benchmark",
                "sample_apps/sync_conflict_demo",
                "--distributed",
                "--dry-run",
                "--output-dir",
                str(tmp_dir / "artifacts"),
            ]
        )

        assert rc == 0
        assert captured["sample_root"].endswith("sample_apps/sync_conflict_demo")
        assert captured["distributed"] is True
        assert captured["dry_run"] is True
        assert captured["mobile"] is False
        assert captured["ai_reasoning"] is False
        assert captured["ai_first"] is False

    def test_benchmark_mobile_flag_is_parsed(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_run_benchmark(
            self,
            sample_root,
            output_dir="artifacts",
            execute=False,
            live=False,
            dry_run=False,
            distributed=False,
            mobile=False,
            ai_reasoning=False,
            ai_first=False,
        ):
            captured["sample_root"] = sample_root
            captured["distributed"] = distributed
            captured["mobile"] = mobile
            captured["ai_reasoning"] = ai_reasoning
            captured["ai_first"] = ai_first
            return {"status": "ok", "artifacts": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_benchmark", fake_run_benchmark)
        rc = main(
            [
                "benchmark",
                "sample_apps/flutter_offline_app",
                "--live",
                "--distributed",
                "--mobile",
                "--ai-reasoning",
                "--ai-first",
                "--output-dir",
                str(tmp_dir / "artifacts"),
            ]
        )
        assert rc == 0
        assert captured["sample_root"].endswith("sample_apps/flutter_offline_app")
        assert captured["distributed"] is True
        assert captured["mobile"] is True
        assert captured["ai_reasoning"] is True
        assert captured["ai_first"] is True

    def test_runtime_lab_doctor_command_executes(self, tmp_dir, monkeypatch):
        def fake_runtime_lab_doctor(self, output_dir="artifacts"):
            return {"status": "ok", "checks": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_runtime_lab_doctor", fake_runtime_lab_doctor)
        rc = main(["runtime-lab", "doctor", "--output-dir", str(tmp_dir / "artifacts")])
        assert rc == 0

    def test_distributed_runtime_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_distributed_runtime(self, sample_path, output_dir="artifacts", dry_run=True, actors=None):
            captured["sample_path"] = sample_path
            captured["dry_run"] = dry_run
            captured["actors"] = actors
            return {"status": "ok", "summary": {}, "artifacts": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_distributed_runtime", fake_distributed_runtime)
        rc = main(
            [
                "distributed-runtime",
                "sample_apps/sync_conflict_demo",
                "--dry-run",
                "--actors",
                "cashier,manager,background_sync",
                "--output-dir",
                str(tmp_dir / "artifacts"),
            ]
        )
        assert rc == 0
        assert captured["sample_path"].endswith("sample_apps/sync_conflict_demo")
        assert captured["dry_run"] is True
        assert captured["actors"] == ["cashier", "manager", "background_sync"]

    def test_mobile_runtime_doctor_executes(self, tmp_dir, monkeypatch):
        def fake_mobile_runtime_doctor(self, output_dir="artifacts"):
            return {"status": "ok", "checks": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_mobile_runtime_doctor", fake_mobile_runtime_doctor)
        rc = main(["mobile-runtime", "doctor", "--output-dir", str(tmp_dir / "artifacts")])
        assert rc == 0

    def test_mobile_runtime_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_mobile_runtime(self, sample_path, output_dir="artifacts", dry_run=True, distributed=False):
            captured["sample_path"] = sample_path
            captured["dry_run"] = dry_run
            captured["distributed"] = distributed
            return {"status": "ok", "summary": {}, "artifacts": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_mobile_runtime", fake_mobile_runtime)
        rc = main(
            [
                "mobile-runtime",
                "sample_apps/flutter_offline_app",
                "--dry-run",
                "--distributed",
                "--output-dir",
                str(tmp_dir / "artifacts"),
            ]
        )
        assert rc == 0
        assert captured["sample_path"].endswith("sample_apps/flutter_offline_app")
        assert captured["dry_run"] is True
        assert captured["distributed"] is True

    def test_cicd_doctor_command_executes(self, tmp_dir, monkeypatch):
        def fake_cicd_doctor(self, output_dir="artifacts"):
            return {"status": "ok", "provider": "unknown_manual"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_cicd_doctor", fake_cicd_doctor)
        rc = main(["cicd", "doctor", "--output-dir", str(tmp_dir / "artifacts")])
        assert rc == 0

    def test_cicd_plan_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_cicd_plan(self, provider="auto", output_dir="artifacts", dry_run=True, approve_overwrite=False):
            captured["provider"] = provider
            captured["dry_run"] = dry_run
            captured["approve_overwrite"] = approve_overwrite
            return {"status": "ok", "file_plan": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_cicd_plan", fake_cicd_plan)
        rc = main(
            [
                "cicd",
                "plan",
                "--provider",
                "github",
                "--dry-run",
                "--output-dir",
                str(tmp_dir / "artifacts"),
            ]
        )
        assert rc == 0
        assert captured["provider"] == "github"
        assert captured["dry_run"] is True
        assert captured["approve_overwrite"] is False

    def test_cicd_release_gate_command_executes(self, tmp_dir, monkeypatch):
        def fake_release_gate(self, artifacts_dir="artifacts"):
            return {"status": "ok", "decision": "warning"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_cicd_release_gate", fake_release_gate)
        rc = main(["cicd", "release-gate", str(tmp_dir / "artifacts")])
        assert rc == 0

    def test_cicd_runtime_commands_execute(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_doctor(self, output_dir="artifacts"):
            captured["doctor"] = output_dir
            return {"status": "ok"}

        def fake_detect(self, output_dir="artifacts"):
            captured["detect"] = output_dir
            return {"status": "ok"}

        def fake_plan(self, provider="auto", output_dir="artifacts", dry_run=True):
            captured["plan"] = {"provider": provider, "output_dir": output_dir, "dry_run": dry_run}
            return {"status": "ok"}

        def fake_gate(self, artifacts_dir="artifacts"):
            captured["gate"] = artifacts_dir
            return {"status": "ok"}

        def fake_pr(self, target_path, output_dir="artifacts"):
            captured["pr"] = {"target_path": target_path, "output_dir": output_dir}
            return {"status": "ok"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_cicd_runtime_doctor", fake_doctor)
        monkeypatch.setattr(cli_main.AuditCommand, "run_cicd_runtime_detect", fake_detect)
        monkeypatch.setattr(cli_main.AuditCommand, "run_cicd_runtime_plan", fake_plan)
        monkeypatch.setattr(cli_main.AuditCommand, "run_cicd_runtime_release_gate", fake_gate)
        monkeypatch.setattr(cli_main.AuditCommand, "run_cicd_runtime_pr_audit", fake_pr)

        rc1 = main(["cicd-runtime", "doctor", "--output-dir", str(tmp_dir / "artifacts")])
        rc2 = main(["cicd-runtime", "detect", "--output-dir", str(tmp_dir / "artifacts")])
        rc3 = main(["cicd-runtime", "plan", "--provider", "github", "--dry-run", "--output-dir", str(tmp_dir / "artifacts")])
        rc4 = main(["cicd-runtime", "release-gate", str(tmp_dir / "artifacts")])
        rc5 = main(["cicd-runtime", "pr-audit", str(tmp_dir), "--output-dir", str(tmp_dir / "artifacts")])

        assert rc1 == rc2 == rc3 == rc4 == rc5 == 0
        assert captured["plan"]["provider"] == "github"
        assert captured["plan"]["dry_run"] is True

    def test_ai_reasoning_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_run_ai_reasoning(self, artifacts_dir="artifacts", dry_run=True):
            captured["artifacts_dir"] = artifacts_dir
            captured["dry_run"] = dry_run
            return {"status": "ok", "mode": "deterministic_fallback", "artifact": "ai_reasoning_summary.json", "artifacts": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_ai_reasoning", fake_run_ai_reasoning)
        rc = main(["ai-reasoning", str(tmp_dir / "artifacts"), "--dry-run"])
        assert rc == 0
        assert captured["artifacts_dir"].endswith("artifacts")
        assert captured["dry_run"] is True

    def test_remediation_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_remediation(
            self,
            artifacts_dir="artifacts",
            dry_run=True,
            proposal_only=False,
            approve_fix_ids=None,
            sandbox=False,
        ):
            captured["artifacts_dir"] = artifacts_dir
            captured["dry_run"] = dry_run
            captured["proposal_only"] = proposal_only
            captured["approve_fix_ids"] = approve_fix_ids or []
            captured["sandbox"] = sandbox
            return {"status": "ok", "artifact": "remediation_summary.json", "artifacts": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_remediation", fake_remediation)
        rc = main(
            [
                "remediation",
                str(tmp_dir / "artifacts"),
                "--dry-run",
                "--proposal-only",
                "--approve",
                "FIX-001",
                "--sandbox",
            ]
        )
        assert rc == 0
        assert captured["artifacts_dir"].endswith("artifacts")
        assert captured["dry_run"] is True
        assert captured["proposal_only"] is True
        assert captured["approve_fix_ids"] == ["FIX-001"]
        assert captured["sandbox"] is True

    def test_remediation_runtime_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_runtime(
            self,
            artifacts_dir="artifacts",
            dry_run=True,
            proposal_only=False,
            simulate=False,
            sandbox=False,
            approve_fix_ids=None,
        ):
            captured["artifacts_dir"] = artifacts_dir
            captured["dry_run"] = dry_run
            captured["proposal_only"] = proposal_only
            captured["simulate"] = simulate
            captured["sandbox"] = sandbox
            captured["approve_fix_ids"] = approve_fix_ids or []
            return {"status": "ok", "artifact": "remediation_runtime_summary.json", "artifacts": {}}

        monkeypatch.setattr(cli_main.AuditCommand, "run_remediation_runtime", fake_runtime)
        rc = main(
            [
                "remediation-runtime",
                str(tmp_dir / "artifacts"),
                "--dry-run",
                "--proposal-only",
                "--simulate",
                "--sandbox",
                "--approve",
                "FIX-001",
            ]
        )
        assert rc == 0
        assert captured["artifacts_dir"].endswith("artifacts")
        assert captured["dry_run"] is True
        assert captured["proposal_only"] is True
        assert captured["simulate"] is True
        assert captured["sandbox"] is True
        assert captured["approve_fix_ids"] == ["FIX-001"]

    def test_performance_doctor_command_executes(self, tmp_dir, monkeypatch):
        def fake_performance_doctor(self, output_dir="artifacts"):
            return {"status": "ok", "artifact": "performance_profile.json"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_performance_doctor", fake_performance_doctor)
        rc = main(["performance", "doctor", "--output-dir", str(tmp_dir / "artifacts")])
        assert rc == 0

    def test_performance_profile_command_executes(self, tmp_dir, monkeypatch):
        def fake_performance_profile(self, artifacts_dir="artifacts"):
            return {"status": "ok", "artifact": "performance_profile.json"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_performance_profile", fake_performance_profile)
        rc = main(["performance", "profile", str(tmp_dir / "artifacts")])
        assert rc == 0

    def test_performance_lifecycle_evidence_and_scalability_commands_execute(self, tmp_dir, monkeypatch):
        def fake_lifecycle(self, artifacts_dir="artifacts"):
            return {"status": "ok", "artifact": "artifact_lifecycle_plan.json"}

        def fake_evidence(self, artifacts_dir="artifacts"):
            return {"status": "ok", "artifact": "evidence_storage_report.json"}

        def fake_scalability(self, output_dir="artifacts"):
            return {"status": "ok", "artifact": "scalability_report.json"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_performance_lifecycle_plan", fake_lifecycle)
        monkeypatch.setattr(cli_main.AuditCommand, "run_performance_evidence_storage", fake_evidence)
        monkeypatch.setattr(cli_main.AuditCommand, "run_scalability_report", fake_scalability)
        rc1 = main(["performance", "lifecycle-plan", str(tmp_dir / "artifacts")])
        rc2 = main(["performance", "evidence-storage", str(tmp_dir / "artifacts")])
        rc3 = main(["performance", "scalability-report", "--output-dir", str(tmp_dir / "artifacts")])
        assert rc1 == 0
        assert rc2 == 0
        assert rc3 == 0

    def test_enterprise_commands_execute(self, tmp_dir, monkeypatch):
        monkeypatch.setattr(
            cli_main.AuditCommand,
            "run_enterprise_doctor",
            lambda self, output_dir="artifacts": {"status": "ok", "artifact": "enterprise_runtime_summary.json"},
        )
        monkeypatch.setattr(
            cli_main.AuditCommand,
            "run_enterprise_workspaces",
            lambda self: {"status": "ok", "artifacts": {}},
        )
        monkeypatch.setattr(
            cli_main.AuditCommand,
            "run_enterprise_governance_report",
            lambda self: {"status": "ok", "artifact": "governance_summary.json"},
        )
        monkeypatch.setattr(
            cli_main.AuditCommand,
            "run_enterprise_audit_history",
            lambda self: {"status": "ok", "artifact": "audit_history_index.json"},
        )

        assert main(["enterprise", "doctor", "--output-dir", str(tmp_dir / "artifacts")]) == 0
        assert main(["enterprise", "workspaces"]) == 0
        assert main(["enterprise", "governance-report"]) == 0
        assert main(["enterprise", "audit-history"]) == 0

    def test_benchmark_intelligence_commands_execute(self, monkeypatch):
        monkeypatch.setattr(
            cli_main.AuditCommand,
            "run_benchmark_intelligence_datasets",
            lambda self: {"status": "ok", "artifact": "benchmark_dataset_registry.json"},
        )
        monkeypatch.setattr(
            cli_main.AuditCommand,
            "run_benchmark_intelligence_scoring",
            lambda self: {"status": "ok", "artifact": "benchmark_scoring_report.json"},
        )
        monkeypatch.setattr(
            cli_main.AuditCommand,
            "run_benchmark_intelligence_maturity",
            lambda self: {"status": "ok", "artifact": "benchmark_maturity_score.json"},
        )
        monkeypatch.setattr(
            cli_main.AuditCommand,
            "run_benchmark_intelligence_trends",
            lambda self: {"status": "ok", "artifact": "benchmark_runtime_summary.json"},
        )

        assert main(["benchmark-intelligence", "datasets"]) == 0
        assert main(["benchmark-intelligence", "scoring"]) == 0
        assert main(["benchmark-intelligence", "maturity"]) == 0
        assert main(["benchmark-intelligence", "trends"]) == 0

    def test_self_optimize_command_executes(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_self_optimize(self, artifacts_dir="artifacts", workspace="default", cross_project=False):
            captured["artifacts_dir"] = artifacts_dir
            captured["workspace"] = workspace
            captured["cross_project"] = cross_project
            return {"status": "ok", "artifact": "self_optimization_summary.json"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_self_optimize", fake_self_optimize)
        rc = main(
            [
                "self-optimize",
                str(tmp_dir / "artifacts"),
                "--workspace",
                "default",
                "--cross-project",
            ]
        )
        assert rc == 0
        assert captured["workspace"] == "default"
        assert captured["cross_project"] is True

    def test_audit_self_optimize_flag_triggers_self_optimization(self, tmp_dir, monkeypatch):
        captured = {"self_optimize_called": False}

        def fake_run(self, target_path, profile, output_dir="artifacts", dry_run=False, ai_reasoning=False, ci_mode=False, ai_first=False):
            return {"status": "dry_run"}

        def fake_self_optimize(self, artifacts_dir="artifacts", workspace="default", cross_project=False):
            captured["self_optimize_called"] = True
            captured["artifacts_dir"] = artifacts_dir
            captured["workspace"] = workspace
            captured["cross_project"] = cross_project
            return {"status": "ok", "artifact": "self_optimization_summary.json"}

        monkeypatch.setattr(cli_main.AuditCommand, "run", fake_run)
        monkeypatch.setattr(cli_main.AuditCommand, "run_self_optimize", fake_self_optimize)
        rc = main(
            [
                "audit",
                str(tmp_dir),
                "--profile",
                "web",
                "--dry-run",
                "--self-optimize",
                "--output-dir",
                str(tmp_dir / "artifacts"),
            ]
        )
        assert rc == 0
        assert captured["self_optimize_called"] is True
        assert captured["workspace"] == "default"
        assert captured["cross_project"] is False

    def test_benchmark_self_optimize_flag_triggers_self_optimization(self, tmp_dir, monkeypatch):
        captured = {"self_optimize_called": False}

        def fake_benchmark(
            self,
            sample_root,
            output_dir="artifacts",
            execute=False,
            live=False,
            dry_run=False,
            distributed=False,
            mobile=False,
            ai_reasoning=False,
            ai_first=False,
        ):
            return {"status": "ok", "artifacts": {}}

        def fake_self_optimize(self, artifacts_dir="artifacts", workspace="default", cross_project=False):
            captured["self_optimize_called"] = True
            captured["artifacts_dir"] = artifacts_dir
            return {"status": "ok", "artifact": "self_optimization_summary.json"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_benchmark", fake_benchmark)
        monkeypatch.setattr(cli_main.AuditCommand, "run_self_optimize", fake_self_optimize)
        rc = main(
            [
                "benchmark",
                "sample_apps",
                "--self-optimize",
                "--output-dir",
                str(tmp_dir / "artifacts"),
            ]
        )
        assert rc == 0
        assert captured["self_optimize_called"] is True
