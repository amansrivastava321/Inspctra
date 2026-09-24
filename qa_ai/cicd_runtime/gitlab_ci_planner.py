"""
gitlab_ci_planner.py - Advisory GitLab CI planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class GitLabCIPlanner:
    """Generate advisory-only GitLab CI stage plans."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, repo_path: str = ".", dry_run: bool = True) -> Dict[str, Any]:
        root = Path(repo_path).expanduser().resolve()
        target = root / ".gitlab-ci.yml"
        exists = target.exists()

        stages = [
            {
                "stage": "audit",
                "commands": ["python -m qa_ai.cli audit . --profile full_stack --ci-mode --dry-run"],
            },
            {
                "stage": "runtime",
                "commands": [
                    "python -m qa_ai.cli remediation-runtime artifacts/ --dry-run",
                    "python -m qa_ai.cli runtime-lab doctor",
                ],
            },
            {
                "stage": "regression",
                "commands": [
                    "python -m qa_ai.cli cicd-runtime release-gate artifacts/",
                ],
            },
        ]

        result = {
            "provider": "gitlab",
            "dry_run": bool(dry_run),
            "advisory_only": True,
            "apply_by_default": False,
            "permission_required_for_write": True,
            "target_file": ".gitlab-ci.yml",
            "target_exists": exists,
            "overwrite_allowed_automatically": False,
            "stages": stages,
            "summary": {
                "stage_count": len(stages),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("gitlab_ci_plan", result, agent="CICDRuntime.GitLabCIPlanner")
        return result
