"""
ci_provider_detector.py - Detect CI provider from environment and repository files.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import os

from qa_ai.runtime.artifact_store import ArtifactStore


class CIProviderDetector:
    """Detects CI provider with deterministic evidence from env and file layout."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, repo_path: str = ".") -> Dict[str, Any]:
        root = Path(repo_path).expanduser().resolve()
        provider, evidence = self._detect(root)
        result = {
            "provider": provider,
            "repo_path": str(root),
            "known_provider": provider in {"github", "gitlab", "jenkins"},
            "evidence": evidence,
            "summary": {
                "provider": provider,
                "evidence_count": len(evidence),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("cicd_provider_report", result, agent="CIProviderDetector")
        return result

    def _detect(self, root: Path) -> tuple[str, List[Dict[str, str]]]:
        evidence: List[Dict[str, str]] = []

        if os.environ.get("GITHUB_ACTIONS"):
            evidence.append({"type": "environment", "key": "GITHUB_ACTIONS", "value": "true"})
            return "github", evidence
        if os.environ.get("GITLAB_CI"):
            evidence.append({"type": "environment", "key": "GITLAB_CI", "value": "true"})
            return "gitlab", evidence
        if os.environ.get("JENKINS_URL"):
            evidence.append({"type": "environment", "key": "JENKINS_URL", "value": "set"})
            return "jenkins", evidence

        if (root / ".github" / "workflows").exists():
            evidence.append({"type": "file", "path": ".github/workflows"})
            return "github", evidence
        if (root / ".gitlab-ci.yml").exists():
            evidence.append({"type": "file", "path": ".gitlab-ci.yml"})
            return "gitlab", evidence
        if (root / "Jenkinsfile").exists():
            evidence.append({"type": "file", "path": "Jenkinsfile"})
            return "jenkins", evidence

        if os.environ.get("CI"):
            evidence.append({"type": "environment", "key": "CI", "value": "true"})
            return "unknown_manual", evidence

        evidence.append({"type": "fallback", "reason": "no_known_ci_markers_detected"})
        return "unknown_manual", evidence
