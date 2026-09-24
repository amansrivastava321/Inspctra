"""
remediation_audit_logger.py - Immutable audit trail for controlled remediation runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class RemediationAuditLogger:
    """Maintain an append-only, hash-chained remediation audit log."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, events: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        existing = self._load("remediation_audit_log")
        entries = existing.get("entries", []) if isinstance(existing.get("entries"), list) else []
        immutable_prefix = list(entries)

        runtime_events = events if isinstance(events, list) else self._default_events()
        for event in runtime_events:
            if not isinstance(event, dict):
                continue
            immutable_prefix.append(self._new_entry(immutable_prefix, event))

        result = {
            "entries": immutable_prefix,
            "immutable": True,
            "hash_chain": True,
            "summary": {
                "entry_count": len(immutable_prefix),
                "new_entries": len(runtime_events),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_audit_log", result, agent="RemediationAuditLogger")
        return result

    def _default_events(self) -> List[Dict[str, Any]]:
        return [
            self._event("proposal_generation", self._counts("patch_proposals", "proposals")),
            self._event("change_simulation", self._counts("remediation_change_simulation", "impacts")),
            self._event("rollback_planning", self._counts("remediation_rollback_plan", "plans")),
            self._event("validation", self._validation_counts()),
            self._event("retest_scope", self._counts("remediation_retest_scope", "tests")),
            self._event("approval_workflow", self._counts("remediation_approval_workflow", "entries")),
            self._event("sandbox", self._counts("remediation_sandbox_report", "operations")),
        ]

    def _event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_type": event_type,
            "event_payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }

    def _validation_counts(self) -> Dict[str, Any]:
        payload = self._load("remediation_validation_report")
        valid = payload.get("valid_proposals", []) if isinstance(payload.get("valid_proposals"), list) else []
        rejected = payload.get("rejected_proposals", []) if isinstance(payload.get("rejected_proposals"), list) else []
        return {
            "validated": len(valid),
            "rejected": len(rejected),
        }

    def _counts(self, artifact_name: str, key: str) -> Dict[str, Any]:
        payload = self._load(artifact_name)
        rows = payload.get(key, []) if isinstance(payload.get(key), list) else []
        return {"count": len(rows)}

    def _new_entry(self, entries: List[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
        previous_hash = str(entries[-1].get("entry_hash", "")) if entries else "GENESIS"
        base = {
            "event": event,
            "previous_hash": previous_hash,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        canonical = json.dumps(base, sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical.encode("utf-8")).hexdigest()
        return {
            **base,
            "entry_hash": digest,
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
