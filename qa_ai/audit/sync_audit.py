"""
sync_audit.py - Offline-first and sync architecture audit agent.
Detects sync architecture signals and generates checks for
duplicate push risk, missing guards, cursor risks, tombstone propagation,
and more.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import re
import time

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.schemas.audit_result_schema import (
    AuditResult,
    AuditCheck,
    AuditCheckStatus,
    AuditSeverity,
    AuditResultMetadata,
)

logger = logging.getLogger(__name__)


# Sync architecture signal patterns
SYNC_SIGNALS: Dict[str, List[str]] = {
    "sync_status": [
        r"syncStatus",
        r"sync_status",
        r"syncState",
        r"sync_state",
        r"isSyncing",
        r"is_syncing",
        r"pending_sync",
        r"needs_sync",
    ],
    "remote_id": [
        r"remoteId",
        r"remote_id",
        r"serverId",
        r"server_id",
        r"cloudId",
        r"cloud_id",
        r"external_id",
    ],
    "local_id": [
        r"localId",
        r"local_id",
        r"clientId",
        r"client_id",
        r"offline_id",
    ],
    "sync_states": [
        r"pending",
        r"synced",
        r"failed",
        r"conflict",
        r"in.?flight",
        r"inFlight",
    ],
    "tombstone": [
        r"deleted_at",
        r"deletedAt",
        r"is_deleted",
        r"isDeleted",
        r"tombstone",
        r"soft.?delete",
    ],
    "sync_functions": [
        r"pull\(",
        r"push\(",
        r"sync\(",
        r"fetch_remote",
        r"push_changes",
        r"pull_changes",
        r"replicate",
    ],
    "conflict_resolution": [
        r"conflict",
        r"merge",
        r"last.?write.?wins",
        r"first.?write.?wins",
        r"manual.?resolve",
        r"resolve_conflict",
    ],
    "local_db": [
        r"sqlite",
        r"sqflite",
        r"drift",
        r"isar",
        r"hive",
        r"shared_preferences",
        r"local.?storage",
        r"indexeddb",
        r"localforage",
    ],
    "remote_db": [
        r"supabase",
        r"firebase",
        r"firestore",
        r"rest.?api",
        r"graphql",
        r"websocket",
        r"realtime",
    ],
    "cursor_patterns": [
        r"cursor",
        r"offset",
        r"lastId",
        r"last_id",
        r"since_id",
        r"page_token",
    ],
}


class SyncAuditAgent:
    """
    Audits offline-first and sync architecture patterns.

    Detects:
    - syncStatus/remoteId/localId fields
    - pending/synced/failed states
    - deleted_at/tombstone fields
    - pull/push sync functions
    - conflict resolution logic

    Checks for:
    - Duplicate push risk
    - Missing in-flight guard
    - Child-only sync risk
    - Global cursor vs per-table cursor risk
    - Tombstone/delete propagation
    - Failed row retry
    - Missing remoteId repair
    - Auth/RLS session continuity
    - Offline recovery
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_map: Optional[Dict[str, Any]] = None,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> AuditResult:
        """
        Run the sync audit.

        Args:
            app_map: Application map from Discovery phase.
            file_contents: Dict of file_path -> content for analysis.

        Returns:
            AuditResult with all checks.
        """
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        # Detect sync signals
        detected_signals = self._detect_signals(app_map, file_contents)
        logger.info(f"Detected sync signals: {list(detected_signals.keys())}")

        is_sync_architecture = len(detected_signals) >= 2

        checks: List[AuditCheck] = []

        if not is_sync_architecture:
            checks.append(AuditCheck(
                check_id="SYNC-NONE",
                title="No sync architecture detected",
                description="The application does not appear to use an offline-first/sync architecture.",
                status=AuditCheckStatus.SKIPPED,
                severity=AuditSeverity.INFO,
                category="sync_detection",
                recommendation="If sync is planned, consider the patterns documented here.",
            ))
        else:
            # Generate checks based on detected signals
            checks.extend(self._check_duplicate_push(detected_signals, file_contents))
            checks.extend(self._check_inflight_guard(detected_signals, file_contents))
            checks.extend(self._check_child_only_sync(detected_signals, file_contents))
            checks.extend(self._check_cursor_risk(detected_signals, file_contents))
            checks.extend(self._check_tombstone_propagation(detected_signals, file_contents))
            checks.extend(self._check_failed_row_retry(detected_signals, file_contents))
            checks.extend(self._check_remote_id_repair(detected_signals, file_contents))
            checks.extend(self._check_auth_session_continuity(detected_signals, file_contents))
            checks.extend(self._check_offline_recovery(detected_signals, file_contents))
            checks.extend(self._check_conflict_resolution(detected_signals, file_contents))

        # Tally results
        passed = sum(1 for c in checks if c.status == AuditCheckStatus.PASSED)
        failed = sum(1 for c in checks if c.status == AuditCheckStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == AuditCheckStatus.WARNING)
        blocked = sum(1 for c in checks if c.status == AuditCheckStatus.BLOCKED)
        skipped = sum(1 for c in checks if c.status == AuditCheckStatus.SKIPPED)

        duration = time.time() - start_time

        result = AuditResult(
            metadata=AuditResultMetadata(
                audit_type="sync_audit",
                app_name=app_map.get("metadata", {}).get("app_name", ""),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration,
                generated_by="SyncAuditAgent",
            ),
            total_checks=len(checks),
            passed=passed,
            failed=failed,
            warnings=warnings,
            blocked=blocked,
            skipped=skipped,
            checks=checks,
            summary=self._build_summary(checks, detected_signals),
        )

        self.store.save_artifact("sync_audit_results", result.model_dump(), agent="SyncAuditAgent")

        logger.info(
            f"Sync audit complete: {passed} passed, {failed} failed, "
            f"{warnings} warnings out of {len(checks)} checks"
        )

        return result

    def _detect_signals(
        self,
        app_map: Dict[str, Any],
        file_contents: Optional[Dict[str, str]],
    ) -> Dict[str, List[str]]:
        """Detect sync architecture signals in codebase."""
        detected: Dict[str, List[str]] = {}

        # Build searchable text
        texts_to_search: List[str] = []

        # From app_map
        stack = app_map.get("stack", {})
        if stack.get("database"):
            texts_to_search.append(stack["database"])
        if stack.get("state_management"):
            texts_to_search.append(stack["state_management"])

        # From file contents
        if file_contents:
            for filepath, content in file_contents.items():
                texts_to_search.append(filepath)
                texts_to_search.append(content)

        all_text = "\n".join(texts_to_search)

        for signal_name, patterns in SYNC_SIGNALS.items():
            for pattern in patterns:
                if re.search(pattern, all_text, re.IGNORECASE):
                    if signal_name not in detected:
                        detected[signal_name] = []
                    detected[signal_name].append(pattern)
                    break

        return detected

    def _check_duplicate_push(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check if sync guards against duplicate pushes."""
        checks: List[AuditCheck] = []

        has_sync_states = "sync_states" in signals
        has_inflight = bool(re.search(
            r"in.?flight|inFlight|is_syncing|isSyncing",
            str(file_contents or ""),
            re.IGNORECASE,
        ))

        if has_sync_states and not has_inflight:
            checks.append(AuditCheck(
                check_id="SYNC-DUP-001",
                title="Missing in-flight guard for duplicate push prevention",
                description="Sync states detected but no in-flight tracking found. Duplicate pushes may occur on retry.",
                status=AuditCheckStatus.FAILED,
                severity=AuditSeverity.HIGH,
                category="sync_safety",
                recommendation="Add an in-flight flag to prevent duplicate network requests during sync.",
            ))
        elif has_sync_states and has_inflight:
            checks.append(AuditCheck(
                check_id="SYNC-DUP-001",
                title="In-flight guard present",
                description="Sync states and in-flight tracking detected.",
                status=AuditCheckStatus.PASSED,
                severity=AuditSeverity.LOW,
                category="sync_safety",
            ))

        return checks

    def _check_inflight_guard(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check for proper in-flight request tracking."""
        checks: List[AuditCheck] = []

        if "sync_status" not in signals:
            return checks

        all_text = str(file_contents or "")
        has_guard = bool(re.search(
            r"(inFlight|in_flight|is_syncing|isSyncing|LOCK|lock_guard|mutex)",
            all_text, re.IGNORECASE,
        ))

        if not has_guard:
            checks.append(AuditCheck(
                check_id="SYNC-FLIGHT-001",
                title="No in-flight request guard",
                description="Sync status fields found but no guard against concurrent sync operations.",
                status=AuditCheckStatus.FAILED,
                severity=AuditSeverity.HIGH,
                category="concurrency",
                recommendation="Add an in-flight flag or mutex to prevent concurrent sync operations.",
            ))

        return checks

    def _check_child_only_sync(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check for child-only sync without parent relationship."""
        checks: List[AuditCheck] = []

        if "remote_id" not in signals:
            return checks

        all_text = str(file_contents or "")

        # Check if there are foreign key references without parent sync
        has_fk = bool(re.search(
            r"(user_id|account_id|parent_id|owner_id)",
            all_text, re.IGNORECASE,
        ))
        has_parent_sync = bool(re.search(
            r"(parent.*sync|owner.*sync|account.*sync|user.*sync)",
            all_text, re.IGNORECASE,
        ))

        if has_fk and not has_parent_sync:
            checks.append(AuditCheck(
                check_id="SYNC-CHILD-001",
                title="Child-only sync risk",
                description="Child records reference parent entities but no parent sync logic detected.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="sync_ordering",
                recommendation="Ensure parent records are synced before children to avoid orphan references.",
            ))

        return checks

    def _check_cursor_risk(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check for global cursor vs per-table cursor risk."""
        checks: List[AuditCheck] = []

        if "cursor_patterns" not in signals:
            return checks

        all_text = str(file_contents or "")

        # Count distinct cursor variable declarations
        cursor_vars = re.findall(
            r"(?:let|const|var|final)\s+(\w*(?:cursor|offset|lastId|since)\w*)",
            all_text, re.IGNORECASE,
        )
        unique_cursors = set(v.lower() for v in cursor_vars)

        # Count distinct sync endpoints/targets that use cursor-like parameters
        cursor_endpoint_uses = re.findall(
            r"(?:fetch|request|get|pull|sync)\s*\([^)]*(?:cursor|offset|lastId|since|page_token)[^)]*\)",
            all_text, re.IGNORECASE,
        )

        # Global cursor risk: one cursor variable used across multiple endpoints
        if len(unique_cursors) == 1 and len(cursor_endpoint_uses) > 1:
            checks.append(AuditCheck(
                check_id="SYNC-CURSOR-001",
                title="Global cursor risk",
                description="Only one cursor variable found used across multiple sync endpoints. A global cursor may skip rows if tables have different update rates.",
                status=AuditCheckStatus.FAILED,
                severity=AuditSeverity.HIGH,
                category="sync_cursor",
                recommendation="Use per-table cursors to ensure no rows are skipped during incremental sync.",
            ))
        elif len(unique_cursors) > 1:
            checks.append(AuditCheck(
                check_id="SYNC-CURSOR-001",
                title="Per-table cursors detected",
                description="Multiple cursor variables found, suggesting per-table tracking.",
                status=AuditCheckStatus.PASSED,
                severity=AuditSeverity.LOW,
                category="sync_cursor",
            ))

        return checks

    def _check_tombstone_propagation(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check if tombstones/deletes propagate to the remote."""
        checks: List[AuditCheck] = []

        if "tombstone" not in signals:
            return checks

        all_text = str(file_contents or "")

        has_remote_delete = bool(re.search(
            r"(remote.*delete|server.*delete|push.*delete|sync.*delete|DELETE\s)",
            all_text, re.IGNORECASE,
        ))

        if not has_remote_delete:
            checks.append(AuditCheck(
                check_id="SYNC-TOMB-001",
                title="Tombstone not propagated to remote",
                description="Local tombstones (deleted_at) found but no logic to propagate deletions to remote server.",
                status=AuditCheckStatus.FAILED,
                severity=AuditSeverity.HIGH,
                category="data_consistency",
                recommendation="Add sync logic to push tombstones to the remote server.",
            ))

        return checks

    def _check_failed_row_retry(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check if failed sync rows have retry logic."""
        checks: List[AuditCheck] = []

        if "sync_states" not in signals:
            return checks

        all_text = str(file_contents or "")

        has_failed_state = bool(re.search(r"failed|error|retry", all_text, re.IGNORECASE))
        has_retry = bool(re.search(
            r"(retry|backoff|exponential|requeue|reattempt)",
            all_text, re.IGNORECASE,
        ))

        if has_failed_state and not has_retry:
            checks.append(AuditCheck(
                check_id="SYNC-RETRY-001",
                title="No retry logic for failed sync rows",
                description="Failed sync state detected but no retry mechanism found.",
                status=AuditCheckStatus.FAILED,
                severity=AuditSeverity.HIGH,
                category="sync_reliability",
                recommendation="Add exponential backoff retry logic for failed sync operations.",
            ))

        return checks

    def _check_remote_id_repair(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check if missing remoteId can be repaired."""
        checks: List[AuditCheck] = []

        if "remote_id" not in signals:
            return checks

        all_text = str(file_contents or "")

        has_repair = bool(re.search(
            r"(repair|reconcile|backfill|fetch.*missing|lookup.*remote)",
            all_text, re.IGNORECASE,
        ))

        if not has_repair:
            checks.append(AuditCheck(
                check_id="SYNC-REPAIR-001",
                title="No remoteId repair logic",
                description="remoteId fields found but no logic to repair missing remote IDs.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="data_integrity",
                recommendation="Add a reconciliation job to look up missing remoteIds by local unique fields.",
            ))

        return checks

    def _check_auth_session_continuity(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check if auth tokens are refreshed during long sync operations."""
        checks: List[AuditCheck] = []

        all_text = str(file_contents or "")

        has_auth = bool(re.search(
            r"(token|auth|session|jwt|bearer)",
            all_text, re.IGNORECASE,
        ))
        has_refresh = bool(re.search(
            r"(refresh.*token|token.*refresh|reauth|session.*extend)",
            all_text, re.IGNORECASE,
        ))

        if has_auth and not has_refresh:
            checks.append(AuditCheck(
                check_id="SYNC-AUTH-001",
                title="No token refresh during sync",
                description="Auth tokens used in sync but no refresh logic found. Long sync operations may fail on token expiry.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="auth_continuity",
                recommendation="Add token refresh logic to handle long-running sync operations.",
            ))

        return checks

    def _check_offline_recovery(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check for offline-to-online transition handling."""
        checks: List[AuditCheck] = []

        all_text = str(file_contents or "")

        has_offline = bool(re.search(
            r"(offline|disconnect|network.*change|connectivity)",
            all_text, re.IGNORECASE,
        ))
        has_recovery = bool(re.search(
            r"(reconnect|online.*handler|network.*restore|sync.*on.*connect)",
            all_text, re.IGNORECASE,
        ))

        if has_offline and not has_recovery:
            checks.append(AuditCheck(
                check_id="SYNC-RECOVERY-001",
                title="No offline recovery handler",
                description="Offline handling detected but no automatic recovery/sync on reconnect.",
                status=AuditCheckStatus.FAILED,
                severity=AuditSeverity.HIGH,
                category="offline_recovery",
                recommendation="Add a network change listener that triggers sync on reconnect.",
            ))

        return checks

    def _check_conflict_resolution(
        self,
        signals: Dict[str, List[str]],
        file_contents: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Check for conflict resolution strategy."""
        checks: List[AuditCheck] = []

        if "conflict_resolution" not in signals:
            if "sync_status" in signals:
                checks.append(AuditCheck(
                    check_id="SYNC-CONFLICT-001",
                    title="No conflict resolution strategy",
                    description="Sync architecture detected but no conflict resolution logic found.",
                    status=AuditCheckStatus.FAILED,
                    severity=AuditSeverity.HIGH,
                    category="conflict_resolution",
                    recommendation="Implement a conflict resolution strategy (last-write-wins, merge, or manual).",
                ))
            return checks

        all_text = str(file_contents or "")

        has_strategy = bool(re.search(
            r"(last.?write.?wins|first.?write.?wins|merge|manual.?resolve|client.?wins|server.?wins)",
            all_text, re.IGNORECASE,
        ))

        if has_strategy:
            checks.append(AuditCheck(
                check_id="SYNC-CONFLICT-001",
                title="Conflict resolution strategy found",
                description="A conflict resolution strategy is implemented.",
                status=AuditCheckStatus.PASSED,
                severity=AuditSeverity.LOW,
                category="conflict_resolution",
            ))

        return checks

    def _build_summary(
        self,
        checks: List[AuditCheck],
        signals: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Build a summary of sync audit results."""
        by_category: Dict[str, int] = {}
        for c in checks:
            by_category[c.category] = by_category.get(c.category, 0) + 1

        return {
            "is_sync_architecture": len(signals) >= 2,
            "detected_signals": list(signals.keys()),
            "total_checks": len(checks),
            "by_category": by_category,
            "has_critical_sync_risks": any(
                c.status == AuditCheckStatus.FAILED
                and c.severity == AuditSeverity.CRITICAL
                for c in checks
            ),
            "has_high_sync_risks": any(
                c.status == AuditCheckStatus.FAILED
                and c.severity == AuditSeverity.HIGH
                for c in checks
            ),
        }
