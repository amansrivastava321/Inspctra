"""
ci_provider_detector.py - Safe CI provider detection for continuous audit runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
import os

from qa_ai.runtime.artifact_store import ArtifactStore


class CIProviderDetector:
    """Detect supported CI providers via read-only environment/file markers."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, repo_path: str = ".") -> Dict[str, Any]:
        root = Path(repo_path).expanduser().resolve()
        provider, evidence = self._detect(root)
        result = {
            "provider": provider,
            "repo_path": str(root),
            "known_provider": provider in {"github", "gitlab", "jenkins", "azure"},
            "supported_providers": ["github", "gitlab", "jenkins", "azure", "unknown_manual"],
            "evidence": evidence,
            "advisory_only": True,
            "summary": {
                "provider": provider,
                "evidence_count": len(evidence),
                "safe_read_only_detection": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("cicd_provider_report", result, agent="CICDRuntime.CIProviderDetector")
        return result

    def _detect(self, root: Path) -> Tuple[str, List[Dict[str, str]]]:
        evidence: List[Dict[str, str]] = []

        env_markers = [
            ("GITHUB_ACTIONS", "github"),
            ("GITLAB_CI", "gitlab"),
            ("JENKINS_URL", "jenkins"),
            ("TF_BUILD", "azure"),
            ("AZURE_HTTP_USER_AGENT", "azure"),
            ("SYSTEM_COLLECTIONURI", "azure"),
        ]
        for key, provider in env_markers:
            if os.environ.get(key):
                evidence.append({"type": "environment", "key": key, "value": "set"})
                return provider, evidence

        file_markers = [
            (root / ".github" / "workflows", "github", ".github/workflows"),
            (root / ".gitlab-ci.yml", "gitlab", ".gitlab-ci.yml"),
            (root / "Jenkinsfile", "jenkins", "Jenkinsfile"),
            (root / "azure-pipelines.yml", "azure", "azure-pipelines.yml"),
            (root / "azure-pipelines.yaml", "azure", "azure-pipelines.yaml"),
        ]
        for path, provider, rel in file_markers:
            if path.exists():
                evidence.append({"type": "file", "path": rel})
                return provider, evidence

        if os.environ.get("CI"):
            evidence.append({"type": "environment", "key": "CI", "value": "true"})
            return "unknown_manual", evidence

        evidence.append({"type": "fallback", "reason": "no_known_ci_markers_detected"})
        return "unknown_manual", evidence
