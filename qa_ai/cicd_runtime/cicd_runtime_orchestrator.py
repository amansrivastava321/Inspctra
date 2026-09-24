"""
cicd_runtime_orchestrator.py - End-to-end CI/CD continuous audit runtime orchestration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.cicd_runtime.ci_provider_detector import CIProviderDetector
from qa_ai.cicd_runtime.github_actions_planner import GitHubActionsPlanner
from qa_ai.cicd_runtime.gitlab_ci_planner import GitLabCIPlanner
from qa_ai.cicd_runtime.jenkins_pipeline_planner import JenkinsPipelinePlanner
from qa_ai.cicd_runtime.incremental_audit_engine import IncrementalAuditEngine
from qa_ai.cicd_runtime.baseline_comparison_engine import BaselineComparisonEngine
from qa_ai.cicd_runtime.release_gate_engine import ReleaseGateEngine
from qa_ai.cicd_runtime.pipeline_policy_engine import PipelinePolicyEngine
from qa_ai.cicd_runtime.pr_audit_orchestrator import PRAuditOrchestrator
from qa_ai.cicd_runtime.cicd_audit_logger import CICDAuditLogger


class CICDRuntimeOrchestrator:
    """Run CI/CD runtime: detect -> plan -> incremental -> baseline -> gate -> policy -> PR -> log."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        repo_path: str = ".",
        provider: str = "auto",
        changed_files: Optional[List[str]] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        provider_report = CIProviderDetector(self.store).run(repo_path=repo_path)
        selected = provider if provider != "auto" else str(provider_report.get("provider", "unknown_manual"))

        github_plan: Dict[str, Any] = {}
        gitlab_plan: Dict[str, Any] = {}
        jenkins_plan: Dict[str, Any] = {}
        if selected == "github":
            github_plan = GitHubActionsPlanner(self.store).run(repo_path=repo_path, dry_run=dry_run)
        elif selected == "gitlab":
            gitlab_plan = GitLabCIPlanner(self.store).run(repo_path=repo_path, dry_run=dry_run)
        elif selected == "jenkins":
            jenkins_plan = JenkinsPipelinePlanner(self.store).run(repo_path=repo_path, dry_run=dry_run)
        elif selected == "azure":
            # Azure support is provider detection + advisory note; no file-write planner.
            gitlab_plan = {
                "provider": "azure",
                "dry_run": bool(dry_run),
                "advisory_only": True,
                "summary": {"note": "Use manual Azure pipeline template integration."},
            }

        incremental = IncrementalAuditEngine(self.store).run(changed_files=changed_files or [])
        baseline = BaselineComparisonEngine(self.store).run()
        release_gate = ReleaseGateEngine(self.store).run(baseline_report=baseline)
        policy = PipelinePolicyEngine(self.store).run(
            release_gate_decision=release_gate,
            baseline_report=baseline,
        )
        pr_audit = PRAuditOrchestrator(self.store).run(changed_files=changed_files or [])
        audit_log = CICDAuditLogger(self.store).run()

        summary = {
            "provider": selected,
            "dry_run": bool(dry_run),
            "advisory_only": True,
            "permission_aware": True,
            "rollback_aware": True,
            "deterministic_evidence_source_of_truth": True,
            "artifacts": {
                "cicd_provider_report": "cicd_provider_report.json",
                "github_actions_plan": "github_actions_plan.json" if github_plan else None,
                "gitlab_ci_plan": "gitlab_ci_plan.json" if gitlab_plan else None,
                "jenkins_pipeline_plan": "jenkins_pipeline_plan.json" if jenkins_plan else None,
                "incremental_audit_plan": "incremental_audit_plan.json",
                "baseline_comparison_report": "baseline_comparison_report.json",
                "release_gate_decision": "release_gate_decision.json",
                "pipeline_policy_report": "pipeline_policy_report.json",
                "pr_audit_report": "pr_audit_report.json",
                "cicd_audit_log": "cicd_audit_log.json",
                "cicd_runtime_summary": "cicd_runtime_summary.json",
            },
            "counts": {
                "changed_files": len(incremental.get("changed_files", [])) if isinstance(incremental.get("changed_files"), list) else 0,
                "recommended_phases": len(incremental.get("recommended_phases", [])) if isinstance(incremental.get("recommended_phases"), list) else 0,
                "blocked_rules": len(policy.get("summary", {}).get("blocked_rules", [])) if isinstance(policy.get("summary"), dict) else 0,
                "warning_rules": len(policy.get("summary", {}).get("warning_rules", [])) if isinstance(policy.get("summary"), dict) else 0,
            },
            "release_decision": release_gate.get("decision", "warning"),
            "integrations": {
                "ai_orchestration": self._exists("ai_decision_log") or self._exists("ai_reasoning_summary"),
                "remediation_runtime": self._exists("remediation_runtime_summary"),
                "runtime_intelligence": self._exists("replay_analysis") or self._exists("runtime_monitor_report"),
                "distributed_runtime": self._exists("distributed_runtime_report"),
                "mobile_runtime": self._exists("mobile_runtime_report"),
                "replay_engine": self._exists("replay_analysis"),
                "reporting": self._exists("audit_summary"),
                "artifact_store": True,
                "artifact_validator": True,
            },
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("cicd_runtime_summary", summary, agent="CICDRuntime.CICDRuntimeOrchestrator")
        return summary

    def _exists(self, artifact_name: str) -> bool:
        return self.store.artifact_exists(artifact_name)
