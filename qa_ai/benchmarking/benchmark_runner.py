"""
benchmark_runner.py - Execute QA-AI benchmark runs for sample apps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json
import time
import uuid

from qa_ai.orchestration.workflow_engine import WorkflowEngine, WorkflowPhase
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime.execution_context import Platform


class BenchmarkRunner:
    """Runs safe audit benchmarks on sample applications."""

    SAFE_BENCHMARK_PHASES: List[WorkflowPhase] = [
        WorkflowPhase.DISCOVERY,
        WorkflowPhase.SECURITY_AUDIT,
        WorkflowPhase.API_AUDIT,
        WorkflowPhase.DATABASE_AUDIT,
        WorkflowPhase.SYNC_AUDIT,
        WorkflowPhase.CODE_QUALITY_AUDIT,
        WorkflowPhase.DEPENDENCY_AUDIT,
        WorkflowPhase.RELEASE_READINESS_AUDIT,
        WorkflowPhase.FINDING_CORRELATION,
        WorkflowPhase.ROOT_CAUSE_ANALYSIS,
        WorkflowPhase.RUNTIME_VALIDATION,
        WorkflowPhase.EXECUTION_REPLAY,
        WorkflowPhase.REPLAY_ANALYSIS,
        WorkflowPhase.SOFTWARE_HEALTH_ASSESSMENT,
        WorkflowPhase.IMPROVEMENT_PLANNING,
        WorkflowPhase.REMEDIATION_PLANNING,
        WorkflowPhase.RETEST_ORCHESTRATION,
        WorkflowPhase.REGRESSION_GUARD,
        WorkflowPhase.QUALITY_TRACKING,
        WorkflowPhase.LEARNING_UPDATE,
    ]

    PROFILE_MAP: Dict[str, str] = {
        "vulnerable_fastapi_app": "api",
        "react_dashboard_app": "web",
        "ecommerce_web_app": "full_stack",
        "sync_conflict_demo": "api",
        "flutter_offline_app": "flutter",
    }

    PLATFORM_MAP: Dict[str, Platform] = {
        "web": Platform.WEB,
        "api": Platform.BACKEND,
        "flutter": Platform.ANDROID,
        "full_stack": Platform.CROSS_PLATFORM,
    }

    def discover_sample_apps(self, sample_root: Path) -> List[Path]:
        if not sample_root.exists() or not sample_root.is_dir():
            return []
        if (sample_root / "expected_issues.json").exists():
            return [sample_root]
        return sorted([path for path in sample_root.iterdir() if path.is_dir()], key=lambda p: p.name)

    def run(
        self,
        sample_root: str,
        output_dir: str = "artifacts",
        execute: bool = False,
        app_urls: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        root = Path(sample_root).expanduser().resolve()
        output_root = Path(output_dir).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        benchmark_root = output_root / "benchmarks"
        benchmark_root.mkdir(parents=True, exist_ok=True)

        apps = self.discover_sample_apps(root)
        started_at = datetime.now(timezone.utc).isoformat()
        run_id = f"benchmark_{uuid.uuid4().hex[:10]}"
        results: List[Dict[str, Any]] = []

        for app_dir in apps:
            profile = self.PROFILE_MAP.get(app_dir.name, "web")
            platform = self.PLATFORM_MAP.get(profile, Platform.UNKNOWN)
            app_artifacts = benchmark_root / app_dir.name
            app_artifacts.mkdir(parents=True, exist_ok=True)
            store = ArtifactStore(base_dir=app_artifacts)
            result = self._run_single(
                app_dir=app_dir,
                profile=profile,
                platform=platform,
                store=store,
                execute=execute,
                app_url=(app_urls or {}).get(app_dir.name) if isinstance(app_urls, dict) else None,
            )
            store.save_artifact("benchmark_app_result", result, agent="BenchmarkRunner")
            results.append(result)

        totals = self._aggregate(results)
        return {
            "run_id": run_id,
            "benchmark_root": str(root),
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "apps": results,
            "totals": totals,
            "execute": execute,
        }

    def _run_single(
        self,
        app_dir: Path,
        profile: str,
        platform: Platform,
        store: ArtifactStore,
        execute: bool,
        app_url: str | None = None,
    ) -> Dict[str, Any]:
        start = time.time()
        workflow_error = ""
        status = "completed"
        try:
            phases = self.SAFE_BENCHMARK_PHASES
            engine = WorkflowEngine(artifact_store=store)
            run_kwargs = {
                "app_path": str(app_dir),
                "app_name": app_dir.name,
                "platform": platform,
                "phases": phases,
            }
            if app_url:
                run_kwargs["app_url"] = app_url
            workflow = engine.run(**run_kwargs)
            workflow_status = workflow.status.value
        except Exception as exc:  # pragma: no cover - defensive safety path
            workflow_status = "failed"
            status = "failed"
            workflow_error = str(exc)

        findings = self._collect_findings(store)
        severity = self._severity_distribution(findings)
        runtime_validation = self._load_dict(store, "verified_findings")
        runtime_summary = runtime_validation.get("summary", {}) if isinstance(runtime_validation.get("summary"), dict) else {}
        evidence_graph = self._load_dict(store, "evidence_graph")
        replay = self._load_dict(store, "replay_analysis")
        execution = self._load_dict(store, "execution_results")
        regression = self._load_dict(store, "regression_guard_report")
        expected_issues = self._load_expected_issues(app_dir)

        duration = time.time() - start
        workflow_result = self._load_dict(store, "workflow_result")
        workflow_duration = workflow_result.get("duration_seconds")
        if isinstance(workflow_duration, (int, float)):
            duration = float(workflow_duration)

        return {
            "app_name": app_dir.name,
            "app_path": str(app_dir),
            "artifact_dir": str(store.base_dir),
            "profile": profile,
            "execute": execute,
            "status": status,
            "workflow_status": workflow_status,
            "workflow_error": workflow_error,
            "audit_duration_seconds": round(duration, 3),
            "findings_count": len(findings),
            "severity_distribution": severity,
            "runtime_failures": self._safe_int(execution.get("failed")),
            "replay_regressions": self._safe_int(
                (replay.get("comparison") or {}).get("total_regressions")
                if isinstance(replay.get("comparison"), dict)
                else 0
            ),
            "regression_detected": bool(regression.get("regression_detected", False)),
            "runtime_validation_summary": runtime_summary,
            "evidence_summary": evidence_graph.get("summary", {}) if isinstance(evidence_graph.get("summary"), dict) else {},
            "findings": findings,
            "expected_issues": expected_issues,
        }

    def _load_expected_issues(self, app_dir: Path) -> List[Dict[str, Any]]:
        manifest = app_dir / "expected_issues.json"
        if not manifest.exists():
            return []
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        issues = payload.get("issues", [])
        if not isinstance(issues, list):
            return []
        return [item for item in issues if isinstance(item, dict)]

    def _load_dict(self, store: ArtifactStore, artifact_name: str) -> Dict[str, Any]:
        payload = store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _collect_findings(self, store: ArtifactStore) -> List[Dict[str, Any]]:
        correlated = self._load_dict(store, "correlated_findings")
        correlated_findings = correlated.get("findings", [])
        if isinstance(correlated_findings, list) and correlated_findings:
            return [item for item in correlated_findings if isinstance(item, dict)]

        findings: List[Dict[str, Any]] = []
        for artifact_name in [
            "api_audit_results",
            "database_audit_results",
            "sync_audit_results",
            "security_audit_results",
            "code_quality_results",
            "dependency_audit_results",
            "release_readiness_results",
        ]:
            artifact = self._load_dict(store, artifact_name)
            checks = artifact.get("checks", [])
            if not isinstance(checks, list):
                continue
            for check in checks:
                if not isinstance(check, dict):
                    continue
                findings.append(
                    {
                        "id": check.get("check_id", ""),
                        "title": check.get("title", ""),
                        "description": check.get("description", ""),
                        "severity": str(check.get("severity", "medium")).lower(),
                        "category": check.get("category", ""),
                        "target": check.get("target", ""),
                    }
                )
        return findings

    def _severity_distribution(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in findings:
            severity = str(finding.get("severity", "medium")).lower()
            if severity not in distribution:
                severity = "medium"
            distribution[severity] += 1
        return distribution

    def _aggregate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        apps_total = len(results)
        findings_total = sum(self._safe_int(item.get("findings_count")) for item in results)
        regressions = sum(1 for item in results if bool(item.get("regression_detected")))
        replay_regressions = sum(self._safe_int(item.get("replay_regressions")) for item in results)
        failed = sum(1 for item in results if item.get("status") != "completed")
        duration = round(sum(float(item.get("audit_duration_seconds", 0.0) or 0.0) for item in results), 3)
        return {
            "apps_total": apps_total,
            "apps_failed": failed,
            "findings_total": findings_total,
            "apps_with_regressions": regressions,
            "replay_regressions_total": replay_regressions,
            "total_duration_seconds": duration,
        }

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
