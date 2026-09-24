"""
memory_api_service.py - Orchestrate all memory kernel components.

Single entry point for: ingest run, recall, patterns, baseline, retention.
No hardcoded app logic. Reusable across Inspectra, Anvil, FlowBook, etc.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryAPIService:
    """
    High-level orchestrator for memory kernel operations.

    All methods: no raw prompts, no raw secrets, no SQL injection.
    dry_run defaults to True for all destructive operations.
    """

    def __init__(self, store=None, artifact_root: Optional[Path] = None):
        if store is None:
            from qa_ai.memory_kernel.memory_store import get_default_store
            store = get_default_store()
        self.store = store
        self.artifact_root = artifact_root or Path("artifacts")

    # ── Scope management ────────────────────────────────────────────────────────

    def get_or_create_scope(
        self,
        scope_id: str,
        project_id: str,
        app_id: str = "",
        product_area: str = "",
        environment: str = "default",
    ) -> Dict[str, Any]:
        """Get existing scope or create new one."""
        existing = self.store.get_scope(scope_id=scope_id)
        if existing:
            return {"status": "existing", "scope": existing}
        self.store.upsert_scope(
            scope_id=scope_id,
            project_id=project_id,
            app_id=app_id,
            product_area=product_area,
            environment=environment,
        )
        scope = self.store.get_scope(scope_id=scope_id)
        return {"status": "created", "scope": scope}

    def get_scope(self, scope_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get_scope(scope_id=scope_id)

    # ── Run ingestion ────────────────────────────────────────────────────────────

    def ingest_run(
        self,
        scope_id: str,
        run_id: str,
        run_type: str,
        current_run: Dict[str, Any],
        auto_update_baseline: bool = False,
        severity: str = "medium",
    ) -> Dict[str, Any]:
        """
        Full ingestion pipeline:
        1. Compute delta vs active baseline
        2. Store delta
        3. Extract patterns
        4. Optionally update baseline if stable
        """
        from qa_ai.memory_kernel.delta_engine import ingest_run as _ingest_run
        from qa_ai.memory_kernel.pattern_engine import ingest_delta_patterns
        from qa_ai.memory_kernel.baseline_manager import update_baseline_if_stable

        delta_id, delta = _ingest_run(
            store=self.store,
            scope_id=scope_id,
            run_id=run_id,
            run_type=run_type,
            current_run=current_run,
        )

        pattern_ids = ingest_delta_patterns(
            store=self.store,
            scope_id=scope_id,
            run_id=run_id,
            delta=delta,
            severity=severity,
        )

        baseline_updated = False
        if auto_update_baseline:
            promoted, _ = update_baseline_if_stable(
                store=self.store,
                scope_id=scope_id,
                run_id=run_id,
                run_type=run_type,
                run_artifacts=current_run,
            )
            baseline_updated = promoted

        return {
            "status": "ok",
            "delta_id": delta_id,
            "pattern_ids": pattern_ids,
            "baseline_updated": baseline_updated,
            "verdict": delta.get("verdict_change", ""),
            "new_failures": len(delta.get("new_failures", [])),
            "resolved_failures": len(delta.get("resolved_failures", [])),
        }

    # ── Evidence fingerprinting ──────────────────────────────────────────────────

    def store_evidence(
        self,
        scope_id: str,
        run_id: str,
        evidence_type: str,
        content_hash: str,
        verdict: str = "unknown",
        severity: str = "medium",
        step_id: str = "",
        index_for_recall: bool = False,
        text_for_recall: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fingerprint and store evidence. Deduplicate by content_hash.
        Optionally index for semantic recall.
        """
        from qa_ai.memory_kernel.semantic_recall import index_memory

        # Check duplicate
        existing_id = self.store.find_duplicate_fingerprint(
            content_hash=content_hash, scope_id=scope_id
        )
        if existing_id:
            return {"status": "duplicate", "fingerprint_id": existing_id}

        fp_id = str(uuid.uuid4())
        self.store.store_evidence_fingerprint({
            "fingerprint_id": fp_id,
            "scope_id": scope_id,
            "run_id": run_id,
            "step_id": step_id,
            "evidence_type": evidence_type,
            "content_hash": content_hash,
            "perceptual_hash": "",
            "semantic_hash": "",
            "schema_hash": "",
            "state_hash": "",
            "workflow_hash": "",
            "size_bytes": 0,
            "compact_size_bytes": 0,
            "duplicate_of": None,
            "value_score": 0.5,
            "retention_class": "warm",
            "artifact_ref": "",
            "created_at": _now_iso(),
        })

        index_result = {}
        if index_for_recall and text_for_recall:
            index_result = index_memory(
                store=self.store,
                source_type="fingerprint",
                source_id=fp_id,
                text=text_for_recall,
                scope_id=scope_id,
            )

        return {"status": "ok", "fingerprint_id": fp_id, "index_result": index_result}

    # ── Summaries ───────────────────────────────────────────────────────────────

    def store_summary(
        self,
        scope_id: str,
        source_id: str,
        source_type: str,
        summary_text: str,
        severity: str = "medium",
        utility_score: Optional[float] = None,
        index_for_recall: bool = True,
    ) -> Dict[str, Any]:
        """Store compact summary. Computes utility score if not provided."""
        from qa_ai.memory_kernel.utility_scorer import score_summary
        from qa_ai.memory_kernel.memory_privacy import redact_text
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_text
        from qa_ai.memory_kernel.semantic_recall import index_memory

        safe_text = redact_text(summary_text[:500])

        if utility_score is None:
            scored = score_summary(source_type=source_type, severity=severity)
            utility_score = round(scored.utility_score / 100.0, 4)

        summary_id = str(uuid.uuid4())
        self.store.store_compact_summary({
            "summary_id": summary_id,
            "scope_id": scope_id,
            "source_type": source_type,
            "source_id": source_id,
            "summary_text": safe_text,
            "summary_hash": fingerprint_text(safe_text)[:32],
            "entities": [],
            "tags": [],
            "severity": severity,
            "confidence": 0.8,
            "utility_score": utility_score,
            "created_at": _now_iso(),
        })

        index_result = {}
        if index_for_recall:
            index_result = index_memory(
                store=self.store,
                source_type="summary",
                source_id=summary_id,
                text=safe_text,
                scope_id=scope_id,
            )

        return {
            "status": "ok",
            "summary_id": summary_id,
            "utility_score": utility_score,
            "index_result": index_result,
        }

    # ── Recall ──────────────────────────────────────────────────────────────────

    def recall(
        self,
        scope_id: str,
        query: str,
        source_types: Optional[List[str]] = None,
        top_k: int = 10,
        min_score: float = 0.5,
    ) -> Dict[str, Any]:
        """Semantic recall across memory for scope."""
        from qa_ai.memory_kernel.semantic_recall import recall_similar

        results = recall_similar(
            store=self.store,
            query=query,
            scope_id=scope_id,
            source_types=source_types,
            top_k=top_k,
            min_score=min_score,
        )
        return {
            "status": "ok",
            "query_length": len(query),
            "results": results,
            "count": len(results),
        }

    # ── Patterns ────────────────────────────────────────────────────────────────

    def get_patterns(
        self,
        scope_id: str,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        from qa_ai.memory_kernel.pattern_engine import query_patterns
        patterns = query_patterns(
            store=self.store,
            scope_id=scope_id,
            pattern_type=pattern_type,
            min_confidence=min_confidence,
            limit=limit,
        )
        return {"status": "ok", "patterns": patterns, "count": len(patterns)}

    # ── Baselines ───────────────────────────────────────────────────────────────

    def get_active_baseline(self, scope_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get_active_baseline(scope_id=scope_id)

    def promote_baseline(self, baseline_id: str, scope_id: str) -> Dict[str, Any]:
        try:
            self.store.set_active_baseline(baseline_id=baseline_id, scope_id=scope_id)
            return {"status": "ok", "baseline_id": baseline_id}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def create_baseline(
        self,
        scope_id: str,
        run_id: str,
        run_type: str = "regression",
        artifacts: Optional[Dict[str, Any]] = None,
        notes: str = "",
    ) -> Dict[str, Any]:
        from qa_ai.memory_kernel.baseline_manager import create_baseline_from_run
        baseline_id = create_baseline_from_run(
            store=self.store,
            scope_id=scope_id,
            run_id=run_id,
            run_type=run_type,
            artifacts=artifacts,
            notes=notes,
        )
        return {"status": "ok" if baseline_id else "error", "baseline_id": baseline_id}

    # ── Retention ───────────────────────────────────────────────────────────────

    def retention_preview(self, scope_id: str) -> Dict[str, Any]:
        """Plan retention — no deletions."""
        from qa_ai.memory_kernel.retention_engine import plan_retention
        from qa_ai.memory_kernel.memory_reporter import generate_retention_report
        plan = plan_retention(store=self.store, scope_id=scope_id)
        report = generate_retention_report(plan, format="markdown")
        return {
            "status": "ok",
            "plan": {
                "keep": len(plan.keep),
                "compress": len(plan.compress),
                "delete": len(plan.delete),
                "total": plan.total_records,
            },
            "report": report,
        }

    def run_retention(
        self,
        scope_id: str,
        dry_run: bool = True,
        max_delete_per_run: int = 500,
    ) -> Dict[str, Any]:
        """Execute retention cycle. dry_run=True by default."""
        from qa_ai.memory_kernel.retention_engine import run_retention_cycle
        return run_retention_cycle(
            store=self.store,
            scope_id=scope_id,
            dry_run=dry_run,
            max_delete_per_run=max_delete_per_run,
        )

    # ── Trajectories ────────────────────────────────────────────────────────────

    def store_trajectory(
        self,
        scope_id: str,
        run_id: str,
        problem_signature: str,
        action_taken: str,
        outcome: str,
        reasoning_steps: Optional[List[str]] = None,
        utility_score: float = 0.5,
    ) -> Dict[str, Any]:
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory
        tid = create_trajectory(
            store=self.store,
            scope_id=scope_id,
            run_id=run_id,
            problem_signature=problem_signature,
            action_taken=action_taken,
            outcome=outcome,
            reasoning_steps=reasoning_steps,
            utility_score=utility_score,
        )
        return {"status": "ok" if tid else "error", "trajectory_id": tid}

    # ── Reports ─────────────────────────────────────────────────────────────────

    def scope_report(self, scope_id: str, format: str = "markdown") -> str:
        from qa_ai.memory_kernel.memory_reporter import generate_scope_report
        return generate_scope_report(store=self.store, scope_id=scope_id, format=format)

    def stats(self, scope_id: str) -> Dict[str, Any]:
        return self.store.get_memory_stats(scope_id=scope_id)
