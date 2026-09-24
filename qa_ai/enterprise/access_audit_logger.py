"""
access_audit_logger.py - Immutable governance access/event logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class AccessAuditLogger:
    """Append-only hash-chained governance access log."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, events: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        existing = self._load("governance_access_log")
        entries = existing.get("entries", []) if isinstance(existing.get("entries"), list) else []
        chain = list(entries)

        runtime_events = events if isinstance(events, list) else self._default_events()
        for event in runtime_events:
            if not isinstance(event, dict):
                continue
            chain.append(self._entry(chain, event))

        report = {
            "entries": chain,
            "immutable": True,
            "hash_chain": True,
            "summary": {
                "entry_count": len(chain),
                "new_entries": len(runtime_events),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("governance_access_log", report, agent="Enterprise.AccessAuditLogger")
        return report

    def _default_events(self) -> List[Dict[str, Any]]:
        workspace = self._load("workspace_registry")
        roles = self._load("role_access_report")
        policy = self._load("governance_policy_report")
        approvals = self._load("remediation_approval_workflow")
        return [
            self._evt("workspace_access", {"workspace_count": len(workspace.get("workspaces", [])) if isinstance(workspace.get("workspaces"), list) else 0}),
            self._evt("role_decisions", {"decisions": int((roles.get("summary") or {}).get("decision_count", 0) or 0)}),
            self._evt("policy_evaluations", {"blocked_rules": len((policy.get("summary") or {}).get("blocked_rules", [])) if isinstance(policy.get("summary"), dict) else 0}),
            self._evt("remediation_approvals", self._approval_counts(approvals)),
        ]

    def _approval_counts(self, approval: Dict[str, Any]) -> Dict[str, Any]:
        entries = approval.get("entries", []) if isinstance(approval.get("entries"), list) else []
        approved = sum(1 for row in entries if isinstance(row, dict) and row.get("state") == "approved")
        pending = sum(1 for row in entries if isinstance(row, dict) and row.get("state") == "pending_approval")
        return {"approved": approved, "pending": pending}

    def _evt(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_type": event_type,
            "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }

    def _entry(self, chain: List[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
        previous_hash = str(chain[-1].get("entry_hash", "")) if chain else "GENESIS"
        body = {
            "event": event,
            "previous_hash": previous_hash,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical.encode("utf-8")).hexdigest()
        return {**body, "entry_hash": digest}

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
