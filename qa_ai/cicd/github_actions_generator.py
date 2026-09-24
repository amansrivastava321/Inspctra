"""
github_actions_generator.py - Build safe GitHub Actions workflow plans.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class GitHubActionsGenerator:
    """Plans GitHub Actions workflow generation with overwrite guards."""

    WORKFLOW_PATH = ".github/workflows/qa_ai_audit.yml"

    def plan(
        self,
        repo_path: str = ".",
        dry_run: bool = True,
        explicit_approval: bool = False,
    ) -> Dict[str, Any]:
        root = Path(repo_path).expanduser().resolve()
        target = root / self.WORKFLOW_PATH
        exists = target.exists()

        action = "plan_only"
        wrote_file = False
        if exists and not explicit_approval:
            action = "skip_existing_requires_approval"
        elif explicit_approval and not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self._template(), encoding="utf-8")
            action = "written"
            wrote_file = True

        return {
            "provider": "github",
            "dry_run": bool(dry_run),
            "explicit_approval": bool(explicit_approval),
            "approval_required_for_overwrite": True,
            "apply_by_default": False,
            "file_plan": {
                "path": self.WORKFLOW_PATH,
                "exists": exists,
                "action": action,
                "written": wrote_file,
                "content_preview": self._template(),
            },
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    def _template(self) -> str:
        return """name: qa-ai-audit
on:
  pull_request:
  push:
    branches: [main]
jobs:
  qa-ai:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python -m qa_ai.cli audit . --profile full_stack --ci-mode --dry-run
      - run: python -m qa_ai.cli cicd release-gate artifacts/
"""
