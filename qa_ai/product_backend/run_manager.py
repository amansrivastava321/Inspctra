"""
run_manager.py - Background run lifecycle manager.

Runs execute in daemon threads (no real browser/app launch without permission).
Cancellation via threading.Event.
Results published to EventStream for SSE delivery.

Security:
- Never launches app processes without explicit user permission.
- No shell=True. No os.system. No eval.
- Cancellation is cooperative (thread checks cancel flag between steps).
- Errors are logged but not re-raised to the main thread.
"""
from __future__ import annotations

import logging
import threading
import time
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.product_backend.event_stream import EventStream
from qa_ai.product_backend.models import Provenance, SUPPORTED_API_ACTIONS, SUPPORTED_WEB_ACTIONS
from qa_ai.product_backend.run_event_recorder import RunEventRecorder

logger = logging.getLogger(__name__)

_GENERIC_DRY_RUN_ACTIONS = frozenset({"interact", "verify", "wait"})
_UNAVAILABLE_ACTION_MARKERS = (
    "mobile", "android", "ios", "desktop", "native", "distributed", "chaos",
    "ci_", "cicd", "pipeline", "enterprise", "governance",
)
_DUAL_ENGINE_ACTIONS = SUPPORTED_WEB_ACTIONS & SUPPORTED_API_ACTIONS


def classify_action_family(action_type: Any, app_type: Optional[str] = None) -> str:
    """Return the one execution family that owns an action."""
    action = str(action_type or "")
    if action in _DUAL_ENGINE_ACTIONS:
        return "api" if app_type == "api" else "browser"
    if action in SUPPORTED_API_ACTIONS:
        return "api"
    if action in SUPPORTED_WEB_ACTIONS:
        return "browser"
    if action in _GENERIC_DRY_RUN_ACTIONS:
        return "dry_run"
    if any(marker in action.lower() for marker in _UNAVAILABLE_ACTION_MARKERS):
        return "unavailable"
    return "unavailable"


def compute_run_provenance(values: List[Any]) -> Provenance:
    """Aggregate step provenance without hiding mixed execution sources."""
    normalized: List[Provenance] = []
    for value in values:
        try:
            normalized.append(Provenance(value))
        except (TypeError, ValueError):
            normalized.append(Provenance.UNAVAILABLE)
    if not normalized:
        return Provenance.UNAVAILABLE
    unique = set(normalized)
    if len(unique) == 1:
        return normalized[0]
    return Provenance.MIXED


class RunManager:
    """
    Manages background validation run execution.

    Each run executes in a daemon thread. Cancellation is cooperative:
    the thread checks `cancel_flag.is_set()` between steps.

    Executes supported HTTP and Playwright steps when their runtime is
    available, and structurally validates safe fallback steps otherwise.
    """

    def __init__(
        self,
        event_stream: EventStream,
        storage: Any,
        artifact_index: Optional[Any] = None,
        event_recorder: Optional[RunEventRecorder] = None,
    ) -> None:
        self._stream = event_stream
        self._storage = storage
        self._artifact_index = artifact_index
        self._event_recorder = event_recorder
        self._lock = threading.Lock()
        # run_id → thread
        self._threads: Dict[str, threading.Thread] = {}
        # run_id → cancel flag
        self._cancel_flags: Dict[str, threading.Event] = {}

    # ── public ────────────────────────────────────────────────────────────────

    def start_run(
        self,
        run_id: str,
        steps: List[Dict[str, Any]],
        app_target: Dict[str, Any],
    ) -> None:
        """
        Start a background run. Non-blocking.
        Raises ValueError if run_id is already running.
        """
        with self._lock:
            if run_id in self._threads and self._threads[run_id].is_alive():
                raise ValueError(f"Run {run_id!r} is already running.")
            cancel_flag = threading.Event()
            thread = threading.Thread(
                target=self._execute,
                args=(run_id, steps, app_target, cancel_flag),
                daemon=True,
                name=f"run-{run_id[:8]}",
            )
            self._threads[run_id] = thread
            self._cancel_flags[run_id] = cancel_flag
        thread.start()
        logger.info("RunManager: started run %s (%d steps)", run_id, len(steps))

    def cancel_run(self, run_id: str) -> bool:
        """
        Signal cancellation for a running run.
        Returns True if signal was sent, False if run not found.
        """
        with self._lock:
            flag = self._cancel_flags.get(run_id)
        if flag is None:
            return False
        flag.set()
        logger.info("RunManager: cancel signal sent for run %s", run_id)
        return True

    def is_running(self, run_id: str) -> bool:
        with self._lock:
            t = self._threads.get(run_id)
        return t is not None and t.is_alive()

    def schedule_run(self, pack_id: str) -> Optional[str]:
        """
        Create and start an automated scheduled run for pack_id.
        Returns run_id on success, None if pack/app cannot be resolved.
        """
        from qa_ai.product_backend.models import LiveRunRecord, Provenance  # local import avoids circular
        pack_row = self._storage.get_validation_pack(pack_id)
        if not pack_row:
            logger.warning("ScheduleRun: pack %s not found", pack_id)
            return None

        app_target_id = pack_row.get("app_id")
        if not app_target_id:
            apps = self._storage.list_app_targets(project_id=pack_row.get("project_id"))
            if not apps:
                logger.warning("ScheduleRun: no app targets in project for pack %s", pack_id)
                return None
            app_target_id = apps[0]["id"]

        target_row = self._storage.get_app_target(app_target_id)
        if not target_row:
            logger.warning("ScheduleRun: app target %s not found", app_target_id)
            return None

        run = LiveRunRecord(
            pack_id=pack_id,
            app_target_id=app_target_id,
            execution_mode="automated",
            status="pending",
            provenance=Provenance.REAL_EXECUTION,
        )
        self._storage.create_run(run.model_dump())

        cases = self._storage.list_test_cases(pack_id)
        enabled_cases = [c for c in cases if c.get("enabled")]
        if enabled_cases:
            steps: List[Dict[str, Any]] = []
            for case in enabled_cases:
                test_steps = sorted(case.get("test_steps") or [], key=lambda s: s.get("step_order", 0))
                for t_step in test_steps:
                    steps.append({
                        "step_id": t_step.get("step_id", ""),
                        "action_type": t_step.get("action_type"),
                        "target": t_step.get("target"),
                        "value": t_step.get("value"),
                        "expected": t_step.get("expected"),
                        "input_value": t_step.get("value") or t_step.get("expected") or "",
                        "timeout_seconds": (t_step.get("timeout_ms") or 30000) / 1000,
                        "optional": bool(t_step.get("optional")),
                        "method": t_step.get("method"),
                        "url": t_step.get("url"),
                        "headers": t_step.get("headers") or {},
                        "query_params": t_step.get("query_params") or {},
                        "body_json": t_step.get("body_json"),
                        "expected_status": t_step.get("expected_status"),
                        "description": f"[Scheduled] {t_step.get('action_type', '')} {t_step.get('target') or ''}".strip(),
                    })
        else:
            steps = list(pack_row.get("steps") or [])

        try:
            self.start_run(run.id, steps, target_row)
        except ValueError:
            logger.warning("ScheduleRun: run %s already tracked", run.id)

        logger.info("ScheduleRun: started run %s for pack %s (schedule=%s)",
                    run.id, pack_id, pack_row.get("schedule"))
        return run.id

    # ── background thread ─────────────────────────────────────────────────────

    def _execute(
        self,
        run_id: str,
        steps: List[Dict[str, Any]],
        app_target: Dict[str, Any],
        cancel: threading.Event,
    ) -> None:
        """Main body of the background run thread."""
        engine = None
        api_engine = None
        try:
            self._storage.update_run_status(
                run_id, "running",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            self._publish_event(run_id, "status", {"run_id": run_id, "status": "running", "total_steps": len(steps)}, "step_start")

            target_url = app_target.get("base_url") or app_target.get("source_url") or ""
            api_context: Dict[str, Any] = {}

            total = len(steps)
            passed = 0
            failed = 0
            step_provenances: List[Provenance] = []

            for idx, step in enumerate(steps):
                if cancel.is_set():
                    self._finalize_run(run_id, "cancelled", passed, failed, total)
                    return

                step_num = idx + 1
                description = step.get("description", f"Step {step_num}")
                step_id = step.get("step_id", "")
                step_started_at = datetime.now(timezone.utc)

                self._publish_event(
                    run_id, "step_started",
                    {
                        "run_id": run_id,
                        "step": step_num,
                        "total": total,
                        "step_name": description,
                        "step_id": step_id,
                    },
                    "step_start"
                )

                action_type = step.get("action_type")
                family = classify_action_family(action_type, app_target.get("app_type"))
                if family == "api":
                    if api_engine is None:
                        from qa_ai.live_execution.api_engine import ApiEngine

                        api_engine = ApiEngine()
                    result = self._run_api_step(step, api_engine, run_id, step_num, app_target, api_context)
                    api_context = result.pop("_api_context", api_context)
                elif family == "browser":
                    if engine is None:
                        self._publish_event(
                            run_id,
                            "browser_started",
                            {"run_id": run_id, "message": "Launching headless Chromium..."},
                            "log",
                        )
                        try:
                            from qa_ai.live_execution.playwright_engine import PlaywrightEngine

                            candidate = PlaywrightEngine(config={"headless": True})
                            engine = candidate if candidate.launch() else None
                        except Exception as exc:
                            logger.warning("RunManager: failed to launch PlaywrightEngine: %s", exc)
                            engine = None

                    if engine is None:
                        result = self._browser_runtime_unavailable(step)
                    elif not engine.reset_context(timeout_seconds=float(step.get("timeout_seconds", 30))):
                        result = self._browser_runtime_unavailable(step)
                    else:
                        if action_type != "navigate" and target_url and engine.page:
                            try:
                                engine.page.goto(
                                    target_url,
                                    wait_until="domcontentloaded",
                                    timeout=max(1, int(float(step.get("timeout_seconds", 30)) * 1000)),
                                )
                            except Exception as exc:
                                preload_evidence = self._capture_page_state_evidence(
                                    engine, run_id, step_num, step.get("step_id", ""), app_target
                                )
                                result = {
                                    "status": "error",
                                    "notes": f"Could not load the app target before {action_type}: {type(exc).__name__}.",
                                    "action_type": action_type,
                                    "step_id": step.get("step_id", ""),
                                    "evidence_ids": preload_evidence,
                                    "provenance": Provenance.REAL_EXECUTION,
                                }
                            else:
                                result = self._run_step_real(step, engine, run_id, step_num, total, cancel, app_target)
                                result.setdefault("provenance", Provenance.REAL_EXECUTION)
                        else:
                            result = self._run_step_real(step, engine, run_id, step_num, total, cancel, app_target)
                            result.setdefault("provenance", Provenance.REAL_EXECUTION)
                elif family == "dry_run":
                    result = self._run_step_safe(step, app_target, cancel)
                else:
                    result = {
                        "status": "capability_gap",
                        "notes": f"Action {action_type!r} is not implemented in Inspectra yet.",
                        "action_type": step.get("action_type", "interact"),
                        "step_id": step.get("step_id", ""),
                        "provenance": Provenance.UNAVAILABLE,
                    }

                try:
                    step_provenance = Provenance(result.get("provenance"))
                except (TypeError, ValueError):
                    step_provenance = Provenance.UNAVAILABLE
                result["provenance"] = step_provenance.value
                step_provenances.append(step_provenance)

                step_completed_at = datetime.now(timezone.utc)
                result.update({
                    "started_at": step_started_at.isoformat(),
                    "completed_at": step_completed_at.isoformat(),
                    "duration_ms": max(
                        0,
                        int((step_completed_at - step_started_at).total_seconds() * 1000),
                    ),
                })

                status = result.get("status", "inconclusive")
                if status == "passed":
                    passed += 1
                elif status in ("failed", "error", "capability_gap", "inconclusive"):
                    failed += 1

                self._publish_event(
                    run_id, "step_completed",
                    {
                        "run_id": run_id,
                        "step": step_num,
                        "total": total,
                        "status": status,
                        "step_name": description,
                        "step_id": step_id,
                        "notes": result.get("notes", ""),
                    },
                    "step_end"
                )

                try:
                    self._storage.append_run_step_result(run_id, step_num, result)
                    self._storage.update_run_provenance(
                        run_id, compute_run_provenance(step_provenances)
                    )
                except Exception as exc:
                    logger.warning("RunManager: failed to persist step %d result: %s", step_num, exc)

                is_optional = bool(step.get("optional") or step.get("is_optional"))
                if status in ("failed", "error") and not is_optional:
                    break

                if cancel.is_set():
                    break

            self._storage.update_run_provenance(
                run_id, compute_run_provenance(step_provenances)
            )
            final_status = "cancelled" if cancel.is_set() else ("failed" if failed > 0 else "completed")
            self._finalize_run(run_id, final_status, passed, failed, total)

        except Exception as exc:
            logger.error("RunManager: run %s raised unexpected error: %s", run_id, exc, exc_info=True)
            try:
                self._storage.update_run_status(
                    run_id, "failed",
                    error=str(exc),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception:
                pass
            self._publish_event(run_id, "run_failed", {"run_id": run_id, "error": str(exc)}, "error")
        finally:
            if engine:
                try:
                    engine.close()
                except Exception:
                    pass
            self._stream.close_run(run_id)
            with self._lock:
                self._threads.pop(run_id, None)
                self._cancel_flags.pop(run_id, None)

    def _finalize_run(
        self, run_id: str, status: str, passed: int, failed: int, total: int
    ) -> None:
        completed_at = datetime.now(timezone.utc).isoformat()
        try:
            self._storage.update_run_status(run_id, status, completed_at=completed_at)
        except Exception as exc:
            logger.warning("RunManager: failed to update final status: %s", exc)
        self._stream.publish_from_thread(
            run_id, "status",
            {
                "run_id": run_id,
                "status": status,
                "steps_passed": passed,
                "steps_failed": failed,
                "steps_total": total,
                "completed_at": completed_at,
            },
        )
        # Memory ingestion — non-fatal; errors must never fail the run
        self._ingest_memory(run_id, status, passed, failed, total)

    def _ingest_memory(
        self, run_id: str, verdict: str, passed: int, failed: int, total: int
    ) -> None:
        """
        Ingest completed run into memory kernel.
        Called from background thread — all errors are caught and logged.
        Memory errors must never propagate to the run outcome.
        """
        try:
            from qa_ai.memory_kernel.memory_api_service import MemoryAPIService  # lazy import
            svc = MemoryAPIService()
            failures: List[str] = []
            run_row = self._storage.get_run(run_id)
            if run_row:
                failures = [
                    sr.get("description") or f"step-{sr.get('step', '?')}"
                    for sr in (run_row.get("step_results") or [])
                    if sr.get("status") in ("failed", "error", "inconclusive")
                ]
            svc.ingest_run(
                scope_id="default",
                run_id=run_id,
                run_type="regression",
                current_run={
                    "run_id": run_id,
                    "verdict": verdict,
                    "step_count": total,
                    "timing_ms": 0.0,
                    "failures": failures,
                    "evidence_fingerprints": [],
                },
                auto_update_baseline=False,
                severity="medium",
            )
            logger.info("RunManager: memory ingested run %s", run_id)
        except Exception as exc:
            logger.debug("RunManager: memory ingestion skipped for run %s: %s", run_id, exc)

    @staticmethod
    def _browser_runtime_unavailable(step: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "error",
            "notes": (
                "Playwright Chromium is not available. Install it with "
                "`python -m playwright install chromium`."
            ),
            "error": "BrowserRuntimeUnavailable",
            "action_type": step.get("action_type", "interact"),
            "step_id": step.get("step_id", ""),
            "provenance": Provenance.UNAVAILABLE,
        }

    def _run_step_safe(
        self,
        step: Dict[str, Any],
        app_target: Dict[str, Any],
        cancel: threading.Event,
    ) -> Dict[str, Any]:
        """
        Execute one validation step in dry-run mode.

        Dry-run mode: validates the step structure and returns a
        'dry_run_only' status. No browser is launched, no network
        calls are made, no app is touched.

        Live execution is a future phase requiring InteractionExecutor
        wiring and explicit user permission.
        """
        step_id = step.get("step_id", "")
        action_type = step.get("action_type", "interact")
        description = step.get("description", "")
        target = step.get("target")
        expected = step.get("expected_result")
        timeout = step.get("timeout_seconds", 30)

        # Brief simulated delay to represent work (capped at 0.05s for speed)
        if not cancel.is_set():
            time.sleep(min(0.05, timeout * 0.001))

        if cancel.is_set():
            return {"status": "cancelled", "notes": "Step cancelled before execution."}

        # Structural validation only — no real execution
        issues = []
        if not description:
            issues.append("step has no description")
        allowed_actions = {"interact", "verify", "wait"} | SUPPORTED_WEB_ACTIONS | SUPPORTED_API_ACTIONS
        if action_type not in allowed_actions:
            issues.append(f"unknown action_type: {action_type!r}")
        if action_type in ("interact", "navigate") and not target:
            issues.append("action requires a target but none provided")

        if issues:
            return {
                "status": "inconclusive",
                "notes": f"Dry-run validation issues: {'; '.join(issues)}",
                "action_type": action_type,
                "step_id": step_id,
                "mode": "dry_run",
                "provenance": Provenance.DRY_RUN,
            }

        return {
            "status": "dry_run_only",
            "notes": (
                f"Step validated in dry-run mode. "
                f"Live execution requires InteractionExecutor and user permission."
            ),
            "action_type": action_type,
            "step_id": step_id,
            "target": target,
            "expected_result": expected,
            "mode": "dry_run",
            "provenance": Provenance.DRY_RUN,
        }

    def _publish_event(self, run_id: str, event_type: str, data: Dict[str, Any], standard_type: Optional[str] = None) -> None:
        data["ts"] = datetime.now(timezone.utc).isoformat()
        self._record_durable_event(run_id, event_type, data)
        self._stream.publish_from_thread(run_id, event_type, data)
        if standard_type and standard_type != event_type:
            fdata = dict(data)
            fdata["type"] = standard_type
            if "message" not in fdata and "step_name" in fdata:
                fdata["message"] = fdata["step_name"]
            self._stream.publish_from_thread(run_id, standard_type, fdata)

    def _record_durable_event(
        self,
        run_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        if self._event_recorder is None:
            return

        normalized_type: Optional[str] = None
        message = ""
        step_index = data.get("step")
        if event_type == "step_started":
            normalized_type = "step_started"
            message = f"Step {step_index} started: {data.get('step_name', 'Unnamed step')}"
        elif event_type == "step_completed":
            normalized_type = "step_completed"
            message = f"Step {step_index} completed: {data.get('status', 'unknown')}"
        elif event_type == "evidence_collected":
            normalized_type = "evidence_captured"
            message = f"Evidence captured: {data.get('type', 'artifact')}"
        elif event_type in {"step_failed", "run_failed"}:
            normalized_type = "error"
            message = str(
                data.get("error")
                or data.get("notes")
                or "Run execution error"
            )
        if normalized_type is None:
            return

        self._event_recorder.record({
            "run_id": run_id,
            "step_index": step_index,
            "step_id": data.get("step_id"),
            "event_type": normalized_type,
            "message": message,
            "payload": dict(data),
            "created_at": data["ts"],
        })

    def _write_json_evidence(
        self,
        run_id: str,
        step_num: int,
        step_id: str,
        evidence_type: str,
        payload: Any,
        provenance: Any = Provenance.REAL_EXECUTION,
        app_target: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self._artifact_index:
            return None
        raw = json.dumps(payload, indent=2, default=str).encode("utf-8")
        sha256 = hashlib.sha256(raw).hexdigest()
        rel_path = f"runs/{run_id}/step_{step_num}_{evidence_type}.json"
        self._artifact_index.write_file(rel_path, raw)
        evidence_id = str(uuid.uuid4())
        metadata = dict(payload) if isinstance(payload, dict) else {"entries": payload}
        metadata.update({
            "step_index": step_num,
            "app_id": (app_target or {}).get("id"),
            "project_id": (app_target or {}).get("project_id"),
        })
        self._storage.create_evidence({
            "id": evidence_id,
            "run_id": run_id,
            "step_id": step_id,
            "type": evidence_type,
            "name": f"{evidence_type.replace('_', ' ').title()} Step {step_num}",
            "relative_path": rel_path,
            "mime_type": "application/json",
            "size_bytes": len(raw),
            "sha256": sha256,
            "metadata_json": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provenance": provenance,
        })
        self._publish_event(
            run_id,
            "evidence_collected",
            {
                "run_id": run_id,
                "step": step_num,
                "type": evidence_type,
                "evidence_id": evidence_id,
                "path": rel_path,
            },
            "log",
        )
        return evidence_id

    def _write_blob_evidence(
        self,
        run_id: str,
        step_num: int,
        step_id: str,
        evidence_type: str,
        content: bytes,
        extension: str,
        mime_type: str,
        app_target: Dict[str, Any],
        provenance: Any = Provenance.REAL_EXECUTION,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self._artifact_index or not content:
            return None
        if evidence_type == "screenshot" and len(content) > 10 * 1024 * 1024:
            # TODO: introduce an evidence retention/compression policy.
            logger.warning("Screenshot evidence exceeds 10 MB for run %s step %s", run_id, step_num)
        rel_path = f"runs/{run_id}/step_{step_num}_{evidence_type}.{extension}"
        self._artifact_index.write_file(rel_path, content)
        evidence_id = str(uuid.uuid4())
        context_metadata = dict(metadata or {})
        context_metadata.update({
            "step_index": step_num,
            "app_id": app_target.get("id"),
            "project_id": app_target.get("project_id"),
        })
        self._storage.create_evidence({
            "id": evidence_id,
            "run_id": run_id,
            "step_id": step_id,
            "type": evidence_type,
            "name": f"{evidence_type.replace('_', ' ').title()} Step {step_num}",
            "relative_path": rel_path,
            "mime_type": mime_type,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "metadata_json": context_metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provenance": provenance,
        })
        self._publish_event(
            run_id,
            "evidence_collected",
            {
                "run_id": run_id,
                "step": step_num,
                "type": evidence_type,
                "evidence_id": evidence_id,
                "path": rel_path,
            },
            "screenshot" if evidence_type == "screenshot" else "log",
        )
        return evidence_id

    def _capture_page_state_evidence(
        self,
        engine: Any,
        run_id: str,
        step_num: int,
        step_id: str,
        app_target: Dict[str, Any],
    ) -> List[str]:
        """Best-effort screenshot and HTML capture for browser setup failures."""
        evidence_ids: List[str] = []
        try:
            screenshot = engine.screenshot_full_page()
            if screenshot:
                evidence_id = self._write_blob_evidence(
                    run_id, step_num, step_id, "screenshot", screenshot,
                    "png", "image/png", app_target,
                )
                if evidence_id:
                    evidence_ids.append(evidence_id)
        except Exception as exc:
            logger.warning("RunManager: preload screenshot capture failed: %s", exc)
        try:
            page_html = engine.page.content() if engine.page else None
            if page_html:
                evidence_id = self._write_blob_evidence(
                    run_id, step_num, step_id, "page_html", str(page_html).encode("utf-8"),
                    "html", "text/html", app_target,
                )
                if evidence_id:
                    evidence_ids.append(evidence_id)
        except Exception as exc:
            logger.warning("RunManager: preload HTML capture failed: %s", exc)
        return evidence_ids

    def _run_api_step(
        self,
        step: Dict[str, Any],
        api_engine: Any,
        run_id: str,
        step_num: int,
        app_target: Dict[str, Any],
        api_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        action_type = step.get("action_type", "api_request")
        step_id = step.get("step_id", "")
        
        is_perf_action = action_type in ("assert_response_time_under", "assert_api_response_time_under")
        if action_type == "api_request":
            self._publish_event(
                run_id,
                "api_request_started",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "method": step.get("method") or "GET",
                    "url": step.get("url") or step.get("target"),
                },
                "api_call",
            )
        elif is_perf_action:
            self._publish_event(
                run_id,
                "performance_started",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "action_type": action_type,
                    "metric_name": "response_time_ms",
                },
                "log",
            )

        result = api_engine.execute_step(step, app_target, api_context)
        next_context = result.get("context") or api_context
        evidence_ids: List[str] = []

        request_summary = result.get("request_summary")
        response_summary = result.get("response_summary")
        assertion_summary = result.get("assertion_summary")
        if action_type == "api_request":
            executed_for_real = bool(response_summary) or bool(result.get("bytes_exchanged"))
        else:
            executed_for_real = bool(next_context.get("last_response"))
        step_provenance = (
            Provenance.REAL_EXECUTION
            if executed_for_real
            else Provenance.UNAVAILABLE
        )

        if request_summary:
            evidence_id = self._write_json_evidence(
                run_id, step_num, step_id, "api_request", request_summary, step_provenance, app_target
            )
            if evidence_id:
                evidence_ids.append(evidence_id)

        if response_summary:
            evidence_id = self._write_json_evidence(
                run_id, step_num, step_id, "api_response", response_summary, step_provenance, app_target
            )
            if evidence_id:
                evidence_ids.append(evidence_id)
            self._publish_event(
                run_id,
                "api_response_received",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "status_code": response_summary.get("status_code"),
                    "response_time_ms": response_summary.get("response_time_ms"),
                    "url": response_summary.get("final_url"),
                },
                "api_call",
            )

        if assertion_summary:
            evidence_id = self._write_json_evidence(
                run_id, step_num, step_id, "api_assertion", assertion_summary, step_provenance, app_target
            )
            if evidence_id:
                evidence_ids.append(evidence_id)
            self._publish_event(
                run_id,
                "api_assertion_completed",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "assertion_type": assertion_summary.get("assertion_type"),
                    "passed": assertion_summary.get("passed"),
                },
                "api_call",
            )

        # Handle API performance specific events and evidence
        if is_perf_action:
            last_resp = next_context.get("last_response") or {}
            resp_time = float(last_resp.get("response_time_ms") or 0.0)
            self._publish_event(
                run_id,
                "performance_metric_captured",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "metric_name": "response_time_ms",
                    "value": resp_time,
                },
                "log",
            )
            
            budget = float(step.get("budget_ms") or step.get("expected_value") or 0.0)
            warning = result.get("warning", False)
            self._publish_event(
                run_id,
                "performance_budget_checked",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "metric_name": "response_time_ms",
                    "budget": budget,
                    "value": resp_time,
                    "passed": result.get("status") == "passed",
                    "warning": warning,
                },
                "log",
            )

            # Write api_timing evidence
            api_timing_payload = {
                "step_id": step_id,
                "action_type": action_type,
                "response_time_ms": resp_time,
                "status_code": last_resp.get("status_code"),
                "body_size_bytes": len(str(last_resp.get("body_preview") or "").encode("utf-8")),
                "header_size_estimate": len(str(last_resp.get("headers") or "")),
                "timeout_ms": step.get("timeout_ms") or 30000,
                "budget_ms": budget,
                "warn_ms": step.get("warn_ms"),
            }
            api_ev_id = self._write_json_evidence(
                run_id, step_num, step_id, "api_timing", api_timing_payload, step_provenance, app_target
            )
            if api_ev_id:
                evidence_ids.append(api_ev_id)

            # Write performance_summary evidence
            perf_summary_payload = {
                "step_id": step_id,
                "action_type": action_type,
                "verdict": "fail" if result.get("status") == "failed" else ("warn" if warning else "pass"),
                "metric_name": "response_time_ms",
                "measured_ms": resp_time,
                "budget_ms": budget,
                "warn_ms": step.get("warn_ms"),
                "notes": result.get("notes", ""),
            }
            perf_ev_id = self._write_json_evidence(
                run_id, step_num, step_id, "performance_summary", perf_summary_payload, step_provenance, app_target
            )
            if perf_ev_id:
                evidence_ids.append(perf_ev_id)

        final = {
            "status": result.get("status", "failed"),
            "notes": result.get("notes", ""),
            "action_type": action_type,
            "step_id": step_id,
            "method": request_summary.get("method") if request_summary else step.get("method"),
            "url": request_summary.get("url") if request_summary else step.get("url"),
            "status_code": response_summary.get("status_code") if response_summary else None,
            "response_time_ms": response_summary.get("response_time_ms") if response_summary else None,
            "assertion_result": assertion_summary.get("passed") if assertion_summary else None,
            "failure_reason": None if result.get("status") == "passed" else result.get("notes", ""),
            "evidence_ids": evidence_ids,
            "warning": result.get("warning", False),
            "provenance": step_provenance,
            "_api_context": next_context,
        }
        if result.get("status") in ("failed", "error"):
            self._publish_event(
                run_id,
                "step_failed",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "action_type": action_type,
                    "notes": final["failure_reason"],
                },
                "error",
            )
        return final

    def _run_step_real(
        self,
        step: Dict[str, Any],
        engine: Any,
        run_id: str,
        step_num: int,
        total: int,
        cancel: threading.Event,
        app_target: Dict[str, Any]
    ) -> Dict[str, Any]:
        if cancel.is_set():
            return {
                "status": "cancelled",
                "notes": "Step cancelled before execution.",
                "provenance": Provenance.UNAVAILABLE,
            }

        action_type = step.get("action_type", "interact")
        target = step.get("target", "")
        input_value = step.get("input_value") or step.get("expected_result") or ""
        timeout = step.get("timeout_seconds", 30)
        step_id = step.get("step_id", "")

        if action_type not in SUPPORTED_WEB_ACTIONS:
            return {
                "status": "capability_gap",
                "notes": f"Action {action_type!r} is not supported.",
                "action_type": action_type,
                "step_id": step_id,
                "provenance": Provenance.UNAVAILABLE,
            }

        if action_type in ("navigate", "passive_security_check", "assert_no_critical_security_findings", "assert_security_headers_present", "assert_cookie_flags_secure"):
            base_url = app_target.get("base_url") or app_target.get("source_url") or ""
            if target:
                if target.startswith("http://") or target.startswith("https://"):
                    url = target
                else:
                    url = base_url.rstrip("/") + "/" + target.lstrip("/")
                target = url

            if action_type == "navigate":
                self._publish_event(
                    run_id, "page_loaded",
                    {"run_id": run_id, "step": step_num, "status": "loading", "url": target},
                    "log"
                )

        self._publish_event(
            run_id, "action_started",
            {
                "run_id": run_id,
                "step": step_num,
                "action_type": action_type,
                "target": target,
            },
            "log"
        )

        # Emit performance started if applicable
        if action_type in ("measure_page_load", "assert_page_load_under"):
            self._publish_event(
                run_id, "performance_started",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "action_type": action_type,
                    "metric_name": step.get("metric_name") or "total_load_ms"
                },
                "log"
            )

        res = engine.execute_action(
            action_type=action_type,
            target=target,
            input_value=input_value,
            is_local_app=True,
            timeout_seconds=timeout,
            budget_ms=step.get("budget_ms"),
            warn_ms=step.get("warn_ms"),
            metric_name=step.get("metric_name")
        )

        if action_type in ("passive_security_check", "assert_no_critical_security_findings", "assert_security_headers_present", "assert_cookie_flags_secure"):
            from qa_ai.live_execution.security_engine import SecurityEngine

            page_url = ""
            raw_headers = {}
            if hasattr(engine, "page") and engine.page:
                try:
                    page_url = engine.page.url
                except Exception:
                    pass

            raw_response_headers = getattr(engine, "raw_response_headers", None)
            if raw_response_headers:
                raw_headers = raw_response_headers.get(page_url) or {}
                if not raw_headers and raw_response_headers:
                    try:
                        last_url = list(raw_response_headers.keys())[-1]
                        raw_headers = raw_response_headers[last_url]
                    except Exception:
                        pass

            cookie_headers = []
            set_cookie_header = raw_headers.get("set-cookie") or raw_headers.get("Set-Cookie") or ""
            for c in set_cookie_header.split("\n"):
                if c.strip():
                    cookie_headers.append(c.strip())

            if hasattr(engine, "context") and engine.context:
                try:
                    for c in engine.context.cookies(urls=[page_url] if page_url else None):
                        parts = [f"{c['name']}={c['value']}"]
                        if c.get("secure"):
                            parts.append("Secure")
                        if c.get("httpOnly"):
                            parts.append("HttpOnly")
                        if c.get("sameSite"):
                            parts.append(f"SameSite={c['sameSite']}")
                        cookie_headers.append("; ".join(parts))
                except Exception:
                    pass

            # De-duplicate cookie headers
            unique_cookies = {}
            for ch in cookie_headers:
                parts = ch.split(";")
                if parts:
                    name_val = parts[0].strip()
                    name = name_val.split("=")[0].strip() if "=" in name_val else name_val
                    unique_cookies[name] = ch
            cookie_headers = list(unique_cookies.values())

            network_summary = res.get("network_summary") or []
            original_url = target if (target and (target.startswith("http://") or target.startswith("https://"))) else None
            response_findings = SecurityEngine.analyze_response(raw_headers, page_url, original_url=original_url)
            cookie_findings = SecurityEngine.analyze_cookies(cookie_headers)
            network_findings = SecurityEngine.analyze_network(network_summary, page_url)

            all_findings = response_findings + cookie_findings + network_findings

            passed = True
            failure_reason = ""
            if action_type == "assert_no_critical_security_findings":
                critical_findings = [f for f in all_findings if f.get("severity") in ("critical", "high")]
                if critical_findings:
                    passed = False
                    failure_reason = f"Found {len(critical_findings)} critical/high security finding(s): " + ", ".join([f["title"] for f in critical_findings])
            elif action_type == "assert_security_headers_present":
                missing_headers = [f for f in all_findings if f.get("category") == "header"]
                if missing_headers:
                    passed = False
                    failure_reason = f"Missing required security headers: " + ", ".join([f["title"] for f in missing_headers])
            elif action_type == "assert_cookie_flags_secure":
                insecure_cookies = [f for f in all_findings if f.get("category") == "cookie"]
                if insecure_cookies:
                    passed = False
                    failure_reason = f"Insecure cookie flag configuration: " + ", ".join([f["title"] for f in insecure_cookies])

            if not passed:
                res["status"] = "failed"
                res["notes"] = failure_reason
                res["error"] = "SecurityAssertionFailed"
            else:
                res["status"] = "passed"
                res["notes"] = f"Security check passed with {len(all_findings)} finding(s)."

            res["security_findings"] = all_findings

        if action_type in ("assert_visual_match", "visual_capture", "visual_compare") and res.get("status") == "passed":
            baseline_name = step.get("value") or f"baseline_{step_id}"
            app_id = app_target.get("id") or ""
            current_screenshot = res.get("screenshot")

            if not current_screenshot:
                res["status"] = "failed"
                res["notes"] = f"Visual operation {action_type} failed: could not capture screenshot."
            else:
                if len(current_screenshot) > 5 * 1024 * 1024:
                    res["status"] = "failed"
                    res["notes"] = f"Screenshot size exceeds limit: {len(current_screenshot)} bytes"
                else:
                    try:
                        import io
                        from PIL import Image
                        img = Image.open(io.BytesIO(current_screenshot))
                        if img.width > 4000 or img.height > 4000:
                            raise ValueError(f"Dimensions exceed limit: {img.size}")
                        width, height = img.size
                        sha256 = hashlib.sha256(current_screenshot).hexdigest()

                        baseline = self._storage.get_visual_baseline_by_step(app_id, step_id)

                        if action_type == "visual_capture":
                            approve_baseline = step.get("approve_baseline")
                            is_approved = approve_baseline is True or str(approve_baseline).lower() == "true"
                            
                            if is_approved:
                                rel_path = f"baselines/{app_id}/{step_id}.png"
                                self._artifact_index.write_file(rel_path, current_screenshot)
                                if baseline:
                                    self._storage.delete_visual_baseline(baseline["id"])
                                baseline_id = str(uuid.uuid4())
                                run_rec = self._storage.get_run(run_id) or {}
                                self._storage.create_visual_baseline({
                                    "id": baseline_id,
                                    "app_id": app_id,
                                    "pack_id": run_rec.get("pack_id"),
                                    "test_case_id": step.get("case_id"),
                                    "step_id": step_id,
                                    "name": baseline_name,
                                    "relative_path": rel_path,
                                    "width": width,
                                    "height": height,
                                    "sha256": sha256,
                                })
                                res["notes"] = f"Visual capture: screenshot saved and approved as baseline '{baseline_name}'."
                            else:
                                rel_path = f"baselines/{app_id}/{step_id}_candidate.png"
                                self._artifact_index.write_file(rel_path, current_screenshot)
                                res["notes"] = f"Visual capture: screenshot saved as candidate baseline to '{rel_path}'."
                            res["status"] = "passed"

                        elif not baseline:
                            if action_type == "visual_compare":
                                res["status"] = "capability_gap"
                                res["notes"] = f"Baseline missing for visual compare step '{baseline_name}'."
                                res["error"] = "BaselineMissing"
                            else:
                                baseline_id = str(uuid.uuid4())
                                rel_path = f"baselines/{app_id}/{step_id}.png"
                                self._artifact_index.write_file(rel_path, current_screenshot)
                                run_rec = self._storage.get_run(run_id) or {}
                                self._storage.create_visual_baseline({
                                    "id": baseline_id,
                                    "app_id": app_id,
                                    "pack_id": run_rec.get("pack_id"),
                                    "test_case_id": step.get("case_id"),
                                    "step_id": step_id,
                                    "name": baseline_name,
                                    "relative_path": rel_path,
                                    "width": width,
                                    "height": height,
                                    "sha256": sha256,
                                })
                                res["status"] = "passed"
                                res["notes"] = f"No baseline found. Initialized current screenshot as baseline '{baseline_name}'."
                        else:
                            baseline_rel_path = baseline["relative_path"]
                            baseline_abs_path = self._artifact_index._resolve_safe(baseline_rel_path)
                            
                            current_rel_path = f"runs/{run_id}/step_{step_num}_current.png"
                            self._artifact_index.write_file(current_rel_path, current_screenshot)
                            current_abs_path = self._artifact_index._resolve_safe(current_rel_path)
                            
                            diff_rel_path = f"runs/{run_id}/step_{step_num}_diff.png"
                            diff_abs_path = self._artifact_index._resolve_safe(diff_rel_path)
                            
                            from qa_ai.live_execution.visual_engine import VisualEngine
                            
                            try:
                                threshold = float(step.get("expected") or "0.05")
                            except ValueError:
                                threshold = 0.05
                                
                            diff_ratio = VisualEngine.compare_images(
                                baseline_abs_path,
                                current_abs_path,
                                diff_abs_path
                            )
                            
                            passed = diff_ratio <= threshold
                            res["status"] = "passed" if passed else "failed"
                            res["notes"] = f"Visual match: diff ratio {diff_ratio:.2%} (threshold {threshold:.2%})."
                            if not passed:
                                res["error"] = "VisualMismatch"
                            
                            total_pixels = width * height
                            pixel_diff_count = int(round(diff_ratio * total_pixels))
                            
                            summary_rel_path = f"runs/{run_id}/step_{step_num}_visual_summary.json"
                            summary_data = {
                                "pixel_diff_count": pixel_diff_count,
                                "pixel_diff_percent": diff_ratio,
                                "threshold_percent": threshold,
                                "passed": passed
                            }
                            self._artifact_index.write_file(
                                summary_rel_path,
                                json.dumps(summary_data, indent=2).encode("utf-8")
                            )
                            
                            if self._artifact_index:
                                diff_bytes = diff_abs_path.read_bytes()
                                sha256_diff = hashlib.sha256(diff_bytes).hexdigest()
                                evidence_id = str(uuid.uuid4())
                                ev_record = {
                                    "id": evidence_id,
                                    "run_id": run_id,
                                    "step_id": step_id,
                                    "type": "visual_diff",
                                    "name": f"Visual Diff Step {step_num}",
                                    "relative_path": diff_rel_path,
                                    "mime_type": "image/png",
                                    "size_bytes": len(diff_bytes),
                                    "sha256": sha256_diff,
                                    "metadata_json": {
                                        "diff_ratio": diff_ratio,
                                        "threshold": threshold,
                                        "baseline_path": baseline_rel_path,
                                        "current_path": current_rel_path,
                                        "summary_path": summary_rel_path,
                                        "step_index": step_num,
                                        "app_id": app_target.get("id"),
                                        "project_id": app_target.get("project_id"),
                                    },
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                    "provenance": Provenance.REAL_EXECUTION,
                                }
                                self._storage.create_evidence(ev_record)
                                res["visual_diff_evidence_id"] = evidence_id
                                
                                self._publish_event(
                                    run_id, "evidence_collected",
                                    {
                                        "run_id": run_id,
                                        "step": step_num,
                                        "type": "visual_diff",
                                        "evidence_id": evidence_id,
                                        "path": diff_rel_path,
                                    },
                                    "screenshot"
                                )
                    except Exception as e:
                        res["status"] = "failed"
                        res["notes"] = f"Visual comparison failed: {e}"

        try:
            full_page = engine.screenshot_full_page()
            if full_page:
                res["full_page_screenshot"] = full_page
        except Exception as exc:
            logger.warning("RunManager: full-page capture failed for step %s: %s", step_num, exc)

        status = res.get("status", "failed")
        if status in ("failed", "error") and not res.get("page_html"):
            try:
                if engine.page:
                    res["page_html"] = engine.page.content()
            except Exception as exc:
                logger.warning("RunManager: failure HTML capture failed for step %s: %s", step_num, exc)
        notes = res.get("notes", "")
        error_msg = res.get("error")

        evidence_ids = []
        if res.get("visual_diff_evidence_id"):
            evidence_ids.append(res["visual_diff_evidence_id"])

        # Publish captured and budget checked events for performance step
        if action_type in ("measure_page_load", "assert_page_load_under"):
            metrics = res.get("metrics") or {}
            m_name = step.get("metric_name") or "total_load_ms"
            measured_ms = metrics.get(m_name, 0)
            self._publish_event(
                run_id, "performance_metric_captured",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "metric_name": m_name,
                    "value": measured_ms
                },
                "log"
            )
            budget = step.get("budget_ms") or 5000
            warning = res.get("warning", False)
            self._publish_event(
                run_id, "performance_budget_checked",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "metric_name": m_name,
                    "budget": budget,
                    "value": measured_ms,
                    "passed": status == "passed",
                    "warning": warning
                },
                "log"
            )

            # Write web_timing evidence
            web_timing_payload = {
                "step_id": step_id,
                "action_type": action_type,
                "metrics": metrics,
                "budget_ms": step.get("budget_ms"),
                "warn_ms": step.get("warn_ms"),
                "metric_name": step.get("metric_name")
            }
            web_ev_id = self._write_json_evidence(run_id, step_num, step_id, "web_timing", web_timing_payload, app_target=app_target)
            if web_ev_id:
                evidence_ids.append(web_ev_id)

            # Write performance_summary evidence
            perf_summary_payload = {
                "step_id": step_id,
                "action_type": action_type,
                "verdict": "fail" if status == "failed" else ("warn" if warning else "pass"),
                "metric_name": m_name,
                "measured_ms": measured_ms,
                "budget_ms": step.get("budget_ms"),
                "warn_ms": step.get("warn_ms"),
                "notes": notes
            }
            perf_ev_id = self._write_json_evidence(run_id, step_num, step_id, "performance_summary", perf_summary_payload, app_target=app_target)
            if perf_ev_id:
                evidence_ids.append(perf_ev_id)

        if action_type in ("check_accessibility", "assert_accessibility", "accessibility_scan", "assert_no_critical_a11y_violations", "assert_no_a11y_violations"):
            a11y_result = res.get("a11y_result") or {}
            total_violations = a11y_result.get("total_violations", 0)
            warning = res.get("warning", False)
            
            self._publish_event(
                run_id, "accessibility_checked",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "total_violations": total_violations,
                    "passed": status == "passed",
                    "warning": warning
                },
                "log"
            )

            a11y_violations_payload = {
                "step_id": step_id,
                "action_type": action_type,
                "a11y_result": a11y_result,
                "budget_violations": step.get("budget_ms"),
                "warn_violations": step.get("warn_ms")
            }
            a11y_ev_id = self._write_json_evidence(run_id, step_num, step_id, "accessibility_violations", a11y_violations_payload, app_target=app_target)
            if a11y_ev_id:
                evidence_ids.append(a11y_ev_id)

            a11y_summary_payload = {
                "step_id": step_id,
                "action_type": action_type,
                "verdict": "fail" if status == "failed" else ("warn" if warning else "pass"),
                "total_violations": total_violations,
                "budget_violations": step.get("budget_ms"),
                "warn_violations": step.get("warn_ms"),
                "notes": notes
            }
            a11y_sum_ev_id = self._write_json_evidence(run_id, step_num, step_id, "accessibility_summary", a11y_summary_payload, app_target=app_target)
            if a11y_sum_ev_id:
                evidence_ids.append(a11y_sum_ev_id)

        if action_type in ("passive_security_check", "assert_no_critical_security_findings", "assert_security_headers_present", "assert_cookie_flags_secure"):
            security_findings = res.get("security_findings") or []
            self._publish_event(
                run_id, "security_checked",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "total_findings": len(security_findings),
                    "passed": status == "passed",
                },
                "log"
            )

            security_payload = {
                "step_id": step_id,
                "action_type": action_type,
                "findings": security_findings,
            }
            sec_ev_id = self._write_json_evidence(run_id, step_num, step_id, "security_findings", security_payload, app_target=app_target)
            if sec_ev_id:
                evidence_ids.append(sec_ev_id)

        screenshot_bytes = res.get("full_page_screenshot") or res.get("screenshot")
        if screenshot_bytes:
            try:
                evidence_id = self._write_blob_evidence(
                    run_id, step_num, step_id, "screenshot", screenshot_bytes,
                    "png", "image/png", app_target,
                )
                if evidence_id:
                    evidence_ids.append(evidence_id)
            except Exception as exc:
                logger.error("Failed to write screenshot evidence: %s", exc)

        console_logs = [
            entry for entry in (res.get("console_logs") or [])
            if str(entry.get("type", "")).lower() in {"warning", "warn", "error"}
        ]
        if console_logs:
            try:
                console_id = self._write_json_evidence(
                    run_id, step_num, step_id, "console", console_logs,
                    app_target=app_target,
                )
                if console_id:
                    evidence_ids.append(console_id)
            except Exception as exc:
                logger.error("Failed to write console evidence: %s", exc)

        network_summary = res.get("network_summary") or []
        if network_summary:
            try:
                network_id = self._write_json_evidence(
                    run_id, step_num, step_id, "network", network_summary,
                    app_target=app_target,
                )
                if network_id:
                    evidence_ids.append(network_id)
            except Exception as exc:
                logger.error("Failed to write network evidence: %s", exc)

        page_html = res.get("page_html")
        if page_html:
            try:
                html_id = self._write_blob_evidence(
                    run_id, step_num, step_id, "page_html", str(page_html).encode("utf-8"),
                    "html", "text/html", app_target,
                )
                if html_id:
                    evidence_ids.append(html_id)
            except Exception as exc:
                logger.error("Failed to write page HTML evidence: %s", exc)

        if status in ("failed", "error"):
            self._publish_event(
                run_id, "step_failed",
                {
                    "run_id": run_id,
                    "step": step_num,
                    "action_type": action_type,
                    "notes": notes,
                    "error": error_msg or "Action failed"
                },
                "error"
            )

        self._publish_event(
            run_id, "action_completed",
            {
                "run_id": run_id,
                "step": step_num,
                "action_type": action_type,
                "status": status,
                "notes": notes
            },
            "log"
        )

        ret = {
            "status": status,
            "notes": notes,
            "action_type": action_type,
            "step_id": step_id,
            "evidence_ids": evidence_ids,
            "error": error_msg
        }
        if "expected" in res:
            ret["expected"] = res["expected"]
        if "actual" in res:
            ret["actual"] = res["actual"]
        if "a11y_result" in res:
            ret["a11y_result"] = res["a11y_result"]
        if "warning" in res:
            ret["warning"] = res["warning"]
        if "security_findings" in res:
            ret["security_findings"] = res["security_findings"]
        return ret
