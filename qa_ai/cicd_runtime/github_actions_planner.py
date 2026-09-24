"""
github_actions_planner.py - Advisory GitHub Actions workflow planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class GitHubActionsPlanner:
    """Generate advisory-only GitHub Actions plans without file modification."""

    WORKFLOWS = [
        {
            "name": "audit_workflow",
            "path": ".github/workflows/qa_ai_audit.yml",
            "trigger": ["pull_request", "push"],
            "steps": [
                "python -m qa_ai.cli audit . --profile full_stack --ci-mode --dry-run",
            ],
        },
        {
            "name": "runtime_audit_workflow",
            "path": ".github/workflows/qa_ai_runtime_audit.yml",
            "trigger": ["pull_request"],
            "steps": [
                "python -m qa_ai.cli runtime-lab doctor",
                "python -m qa_ai.cli audit . --profile full_stack --ci-mode",
            ],
        },
        {
            "name": "regression_workflow",
            "path": ".github/workflows/qa_ai_regression.yml",
            "trigger": ["pull_request"],
            "steps": [
                "python -m qa_ai.cli remediation-runtime artifacts/ --dry-run",
                "python -m qa_ai.cli cicd-runtime release-gate artifacts/",
            ],
        },
        {
            "name": "release_gate_workflow",
            "path": ".github/workflows/qa_ai_release_gate.yml",
            "trigger": ["push"],
            "steps": [
                "python -m qa_ai.cli cicd-runtime detect",
                "python -m qa_ai.cli cicd-runtime release-gate artifacts/",
            ],
        },
    ]

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, repo_path: str = ".", dry_run: bool = True) -> Dict[str, Any]:
        root = Path(repo_path).expanduser().resolve()
        existing = self._existing_workflows(root)

        workflow_plans: List[Dict[str, Any]] = []
        for workflow in self.WORKFLOWS:
            exists = workflow["path"] in existing
            workflow_plans.append(
                {
                    "workflow_name": workflow["name"],
                    "workflow_path": workflow["path"],
                    "exists": exists,
                    "action": "advisory_review_required" if exists else "advisory_create_new_file",
                    "trigger": workflow["trigger"],
                    "steps": workflow["steps"],
                    "overwrite_allowed_automatically": False,
                }
            )

        result = {
            "provider": "github",
            "dry_run": bool(dry_run),
            "advisory_only": True,
            "apply_by_default": False,
            "permission_required_for_write": True,
            "existing_workflows": existing,
            "workflow_plans": workflow_plans,
            "summary": {
                "workflow_count": len(workflow_plans),
                "existing_count": sum(1 for row in workflow_plans if row.get("exists")),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("github_actions_plan", result, agent="CICDRuntime.GitHubActionsPlanner")
        return result

    def _existing_workflows(self, root: Path) -> List[str]:
        workflows_dir = root / ".github" / "workflows"
        if not workflows_dir.exists():
            return []
        out: List[str] = []
        for path in sorted(workflows_dir.glob("*.y*ml")):
            rel = path.relative_to(root)
            out.append(str(rel))
        return out
