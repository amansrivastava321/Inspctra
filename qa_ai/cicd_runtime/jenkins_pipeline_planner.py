"""
jenkins_pipeline_planner.py - Advisory Jenkins pipeline planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class JenkinsPipelinePlanner:
    """Generate advisory-only Jenkins pipeline plans."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, repo_path: str = ".", dry_run: bool = True) -> Dict[str, Any]:
        root = Path(repo_path).expanduser().resolve()
        target = root / "Jenkinsfile"
        exists = target.exists()

        stages: List[Dict[str, Any]] = [
            {
                "name": "Audit Orchestration",
                "commands": [
                    "python -m qa_ai.cli audit . --profile full_stack --ci-mode --dry-run",
                ],
            },
            {
                "name": "Release Gate",
                "commands": [
                    "python -m qa_ai.cli cicd-runtime release-gate artifacts/",
                ],
            },
            {
                "name": "Remediation Review",
                "commands": [
                    "python -m qa_ai.cli remediation-runtime artifacts/ --dry-run",
                ],
            },
        ]

        result = {
            "provider": "jenkins",
            "dry_run": bool(dry_run),
            "advisory_only": True,
            "apply_by_default": False,
            "permission_required_for_write": True,
            "target_file": "Jenkinsfile",
            "target_exists": exists,
            "overwrite_allowed_automatically": False,
            "stages": stages,
            "summary": {
                "stage_count": len(stages),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("jenkins_pipeline_plan", result, agent="CICDRuntime.JenkinsPipelinePlanner")
        return result
