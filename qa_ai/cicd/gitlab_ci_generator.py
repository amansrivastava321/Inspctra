"""
gitlab_ci_generator.py - Build safe GitLab CI pipeline plans.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class GitLabCIGenerator:
    """Plans GitLab CI config generation with overwrite guards."""

    FILE_PATH = ".gitlab-ci.yml"

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
            "provider": "gitlab",
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
        return """stages:
  - audit

qa_ai_audit:
  stage: audit
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - python -m qa_ai.cli audit . --profile full_stack --ci-mode --dry-run
    - python -m qa_ai.cli cicd release-gate artifacts/
"""
