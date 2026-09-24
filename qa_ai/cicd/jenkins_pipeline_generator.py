"""
jenkins_pipeline_generator.py - Build safe Jenkins pipeline plans.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class JenkinsPipelineGenerator:
    """Plans Jenkinsfile generation with overwrite guards."""

    FILE_PATH = "Jenkinsfile"

    def plan(
        self,
        repo_path: str = ".",
        dry_run: bool = True,
        explicit_approval: bool = False,
    ) -> Dict[str, Any]:
        root = Path(repo_path).expanduser().resolve()
        target = root / self.FILE_PATH
        exists = target.exists()

        action = "plan_only"
        wrote_file = False
        if exists and not explicit_approval:
            action = "skip_existing_requires_approval"
        elif explicit_approval and not dry_run:
            target.write_text(self._template(), encoding="utf-8")
            action = "written"
            wrote_file = True

        return {
            "provider": "jenkins",
            "dry_run": bool(dry_run),
            "explicit_approval": bool(explicit_approval),
            "approval_required_for_overwrite": True,
            "apply_by_default": False,
            "file_plan": {
                "path": self.FILE_PATH,
                "exists": exists,
                "action": action,
                "written": wrote_file,
                "content_preview": self._template(),
            },
            "summary": {"generated_at": datetime.now(timezone.utc).isoformat()},
        }

    def _template(self) -> str:
        return """pipeline {
  agent any
  stages {
    stage('QA-AI Audit') {
      steps {
        sh 'pip install -r requirements.txt'
        sh 'python -m qa_ai.cli audit . --profile full_stack --ci-mode --dry-run'
        sh 'python -m qa_ai.cli cicd release-gate artifacts/'
      }
    }
  }
}
"""
