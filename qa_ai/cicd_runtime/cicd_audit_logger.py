"""
cicd_audit_logger.py - Immutable CI/CD audit lifecycle logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class CICDAuditLogger:
    """Append-only hash-chained CI/CD audit log."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, events: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        existing = self._load("cicd_audit_log")
        entries = existing.get("entries", []) if isinstance(existing.get("entries"), list) else []
        chain = list(entries)

        runtime_events = events if isinstance(events, list) else self._default_events()
        for event in runtime_events:
            if not isinstance(event, dict):
                continue
            chain.append(self._entry(chain, event))

        result = {
            "entries": chain,
            "immutable": True,
            "hash_chain": True,
            "summary": {
                "entry_count": len(chain),
                "new_entries": len(runtime_events),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("cicd_audit_log", result, agent="CICDRuntime.CICDAuditLogger")
        return result

    def _default_events(self) -> List[Dict[str, Any]]:
        return [
            self._evt("provider_detection", self._count("cicd_provider_report", "evidence")),
            self._evt("workflow_plans", {
                "github_plan": self._exists("github_actions_plan"),
                "gitlab_plan": self._exists("gitlab_ci_plan"),
                "jenkins_plan": self._exists("jenkins_pipeline_plan"),
            }),
            self._evt("baseline_comparison", self._count("baseline_comparison_report", "regressions")),
            self._evt("release_gate_decisions", self._load("release_gate_decision")),
            self._evt("policy_violations", self._load("pipeline_policy_report")),
            self._evt("pr_audit_outcomes", self._count("pr_audit_report", "remediation_review_suggestions")),
        ]

    def _count(self, artifact_name: str, key: str) -> Dict[str, Any]:
        payload = self._load(artifact_name)
        value = payload.get(key)
        if isinstance(value, list):
            return {"count": len(value)}
        if isinstance(value, dict):
            return {"count": len(value.keys())}
        return {"count": 0}

    def _exists(self, artifact_name: str) -> bool:
        return self.store.artifact_exists(artifact_name)

    def _evt(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_type": event_type,
            "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }

    def _entry(self, chain: List[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
        prev = str(chain[-1].get("entry_hash", "")) if chain else "GENESIS"
        body = {
            "event": event,
            "previous_hash": prev,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical.encode("utf-8")).hexdigest()
        return {**body, "entry_hash": digest}

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
