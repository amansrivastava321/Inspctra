"""Advisory root-cause suggestions for persisted product-backend live runs.

This module is deliberately separate from the static-audit RCA engines. It reads
ProductStorage and ArtifactIndex only, treats model output as untrusted, and never
changes run results, verdicts, selectors, or test definitions.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from qa_ai.ai.llm_router import ModelCapability, get_router
from qa_ai.ai.model_health import check_ollama_health, probe_ollama_chat_ready
from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.prompt_safety import make_safe
from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.dashboard_summary import normalize_failure
from qa_ai.product_backend.models import (
    AIRootCauseSuggestion,
    AIRootCauseSuggestionBatch,
    Provenance,
)
from qa_ai.product_backend.storage import ProductStorage

logger = logging.getLogger(__name__)

MAX_EVIDENCE_RECORDS = 20
MAX_ARTIFACT_BYTES = 16 * 1024
MAX_TOTAL_EVIDENCE_BYTES = 64 * 1024
MAX_EVENTS = 50

_TEXT_EVIDENCE_TYPES = frozenset(
    {
        "console",
        "console_log",
        "failure_html",
        "page_html",
        "network",
        "network_summary",
        "api_request",
        "api_response",
        "api_assertion",
        "accessibility",
        "accessibility_summary",
        "accessibility_violations",
        "visual_diff",
        "visual_summary",
        "security",
        "security_findings",
        "performance",
        "performance_summary",
        "api_timing",
        "web_timing",
        "manual_confirmation",
        "log",
    }
)
_TEXT_EXTENSIONS = frozenset({".json", ".html", ".txt", ".log"})
_SOURCE_EXTENSIONS = frozenset(
    {
        ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".go",
        ".rs", ".rb", ".php", ".swift", ".kt", ".dart", ".c", ".cc",
        ".cpp", ".h", ".hpp", ".env", ".pem", ".key",
    }
)
_FAILURE_STATUSES = frozenset(
    {"failed", "failure", "error", "blocked", "inconclusive", "capability_gap"}
)
_RELEVANT_EVENT_TYPES = frozenset(
    {
        "error", "run_failed", "step_failed", "step_completed", "step_end",
        "evidence_captured", "warning",
    }
)
_SENSITIVE_KEYS = frozenset(
    {
        "authorization", "cookie", "setcookie", "xapikey", "apikey", "token",
        "accesstoken", "refreshtoken", "secret", "password", "passwd",
        "clientsecret", "privatekey",
    }
)
_ABSOLUTE_PHRASES = (
    "definitely caused by",
    "root cause is",
    "certainly caused",
    "guaranteed cause",
)
_STRING_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[^\s,;]+"),
    re.compile(
        r"(?i)\b(authorization|cookie|set-cookie|x-api-key|api-key|api_key|"
        r"access_token|refresh_token|client_secret|private_key|token|secret|"
        r"password|passwd)\s*[:=]\s*([^\s,;&]+|\"[^\"]*\"|'[^']*')"
    ),
    re.compile(
        r"-----BEGIN\s+[A-Z ]*PRIVATE KEY-----.*?-----END\s+[A-Z ]*PRIVATE KEY-----",
        re.IGNORECASE | re.DOTALL,
    ),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _redact_string(value: str) -> str:
    redacted = value
    for pattern in _STRING_SECRET_PATTERNS:
        if "BEGIN" in pattern.pattern:
            redacted = pattern.sub("[REDACTED]", redacted)
        elif pattern.groups:
            redacted = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
        else:
            redacted = pattern.sub("Bearer [REDACTED]", redacted)
    return redacted


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, child in value.items():
            safe_key = str(key)[:160]
            if _clean_key(safe_key) in _SENSITIVE_KEYS:
                sanitized[safe_key] = "[REDACTED]"
            else:
                sanitized[safe_key] = _sanitize(child, depth=depth + 1)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, depth=depth + 1) for item in value[:200]]
    if isinstance(value, str):
        return _redact_string(value[:32_768])
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_string(str(value)[:2_000])


def _provenance(value: Any) -> str:
    try:
        return Provenance(value or Provenance.UNAVAILABLE).value
    except ValueError:
        return Provenance.UNAVAILABLE.value


def _aggregate_provenance(values: Iterable[Any]) -> str:
    normalized = {_provenance(value) for value in values if value is not None}
    if not normalized:
        return Provenance.UNAVAILABLE.value
    if len(normalized) == 1:
        return next(iter(normalized))
    return Provenance.MIXED.value


class AIRootCauseSuggester:
    """Build grounded, draft-only root-cause hypotheses for one live run."""

    def __init__(
        self,
        storage: ProductStorage,
        artifact_index: ArtifactIndex,
        router: Any = None,
    ) -> None:
        self.storage = storage
        self.artifact_index = artifact_index
        self.router = router or get_router()
        self._last_model_metadata: Dict[str, Any] = {}

    def build_context(
        self, run_id: str, step_id: Optional[str] = None
    ) -> Dict[str, Any]:
        run = self.storage.get_run(run_id)
        if run is None:
            raise ValueError("Run not found")

        all_steps = run.get("step_results") or []
        if step_id is not None:
            steps = [step for step in all_steps if step.get("step_id") == step_id]
        else:
            steps = [
                step
                for step in all_steps
                if str(step.get("status") or "").casefold() in _FAILURE_STATUSES
            ]
        selected_step_ids = {
            str(step.get("step_id")) for step in steps if step.get("step_id")
        }

        safe_steps = [self._step_context(step) for step in steps]
        events = self._event_context(run_id, selected_step_ids, step_id)
        evidence = self._evidence_context(run_id, selected_step_ids, step_id)
        signals = self._deterministic_signals(safe_steps, events, evidence)

        return _sanitize(
            {
                "run": {
                    "id": run.get("id"),
                    "status": run.get("status"),
                    "error": run.get("error"),
                    "execution_mode": run.get("execution_mode"),
                    "provenance": _provenance(run.get("provenance")),
                    "started_at": run.get("started_at"),
                    "completed_at": run.get("completed_at"),
                    "created_at": run.get("created_at"),
                    "pack_id": run.get("pack_id"),
                    "target_id": run.get("app_target_id"),
                },
                "steps": safe_steps,
                "events": events,
                "evidence": evidence,
                "deterministic_signals": signals,
            }
        )

    def suggest(
        self, run_id: str, step_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self.build_context(run_id, step_id)
        analysis_id = str(uuid.uuid4())
        created_at = _now_iso()
        model_output = self._try_model(context)
        suggestions = self._validate_model_suggestions(
            model_output, context, analysis_id, run_id, created_at
        )
        generation_source = (
            str(self._last_model_metadata.get("provider") or "ollama")
            if suggestions
            else "local_fallback"
        )
        generation_metadata = (
            _sanitize(self._last_model_metadata) if suggestions else {"mode": "deterministic"}
        )
        if not suggestions:
            suggestions = self._fallback_suggestions(
                context, analysis_id, run_id, created_at
            )

        if not suggestions:
            batch = AIRootCauseSuggestionBatch(
                analysis_id=analysis_id,
                run_id=run_id,
                status="inconclusive",
                authoritative=False,
                source_provenance=Provenance.UNAVAILABLE,
                generation_source="local_fallback",
                generation_metadata={"mode": "deterministic"},
                missing_evidence=[
                    "No failed step details or admissible execution evidence were available."
                ],
                suggestions=[],
                created_at=created_at,
            )
            return batch.model_dump(mode="json")

        batch = AIRootCauseSuggestionBatch(
            analysis_id=analysis_id,
            run_id=run_id,
            status="suggested",
            authoritative=False,
            source_provenance=_aggregate_provenance(
                item["source_provenance"] for item in suggestions
            ),
            generation_source=generation_source,
            generation_metadata=generation_metadata,
            missing_evidence=list(
                dict.fromkeys(
                    missing
                    for suggestion in suggestions
                    for missing in suggestion.get("missing_evidence", [])
                )
            ),
            suggestions=suggestions,
            created_at=created_at,
        )
        return batch.model_dump(mode="json")

    @staticmethod
    def _step_context(step: Dict[str, Any]) -> Dict[str, Any]:
        fields = (
            "step_id", "step", "action_type", "status", "failure_reason", "error",
            "notes", "expected", "actual", "actual_result", "status_code",
            "http_status", "duration_ms", "elapsed_ms", "provenance", "evidence_ids",
            "diff_ratio", "security_findings", "a11y_result",
        )
        result = {field: step.get(field) for field in fields if field in step}
        result["provenance"] = _provenance(step.get("provenance"))
        return _sanitize(result)

    def _event_context(
        self,
        run_id: str,
        selected_step_ids: set[str],
        requested_step_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        relevant: List[Dict[str, Any]] = []
        for event in self.storage.list_run_events(run_id):
            event_type = str(event.get("event_type") or "").casefold()
            message = str(event.get("message") or "")
            is_failure = event_type in _RELEVANT_EVENT_TYPES or any(
                word in message.casefold()
                for word in ("fail", "error", "timeout", "blocked", "mismatch")
            )
            if not is_failure:
                continue
            if requested_step_id and event.get("step_id") != requested_step_id:
                continue
            if selected_step_ids and event.get("step_id") not in selected_step_ids | {None}:
                continue
            relevant.append(
                _sanitize(
                    {
                        "id": event.get("id"),
                        "step_index": event.get("step_index"),
                        "step_id": event.get("step_id"),
                        "event_type": event.get("event_type"),
                        "message": event.get("message"),
                        "payload": event.get("payload") or {},
                        "created_at": event.get("created_at"),
                    }
                )
            )
            if len(relevant) >= MAX_EVENTS:
                break
        return relevant

    def _evidence_context(
        self,
        run_id: str,
        selected_step_ids: set[str],
        requested_step_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        records = self.storage.list_evidence(run_id)
        selected: List[Dict[str, Any]] = []
        total_bytes = 0
        for record in records:
            record_step_id = record.get("step_id")
            if requested_step_id and record_step_id != requested_step_id:
                continue
            if selected_step_ids and record_step_id not in selected_step_ids | {None}:
                continue
            content: Optional[str] = None
            evidence_type = str(record.get("type") or record.get("evidence_type") or "")
            extension = Path(str(record.get("relative_path") or "")).suffix.casefold()
            can_read = (
                evidence_type.casefold() in _TEXT_EVIDENCE_TYPES
                and extension in _TEXT_EXTENSIONS
                and extension not in _SOURCE_EXTENSIONS
                and total_bytes < MAX_TOTAL_EVIDENCE_BYTES
            )
            if can_read:
                remaining = min(
                    MAX_ARTIFACT_BYTES,
                    MAX_TOTAL_EVIDENCE_BYTES - total_bytes,
                )
                raw = self._read_bounded(record.get("relative_path"), remaining)
                content = self._truncate_utf8(
                    self._sanitize_artifact_text(raw), remaining
                )
                total_bytes += len(content.encode("utf-8"))
            selected.append(
                _sanitize(
                    {
                        "id": record.get("id"),
                        "step_id": record_step_id,
                        "type": evidence_type,
                        "name": record.get("name"),
                        "mime_type": record.get("mime_type"),
                        "size_bytes": record.get("size_bytes"),
                        "sha256": record.get("sha256"),
                        "metadata": record.get("metadata_json") or {},
                        "provenance": _provenance(record.get("provenance")),
                        "content": content,
                    }
                )
            )
            if len(selected) >= MAX_EVIDENCE_RECORDS:
                break
        return selected

    def _read_bounded(self, relative_path: Any, limit: int) -> bytes:
        if not isinstance(relative_path, str) or limit <= 0:
            return b""
        try:
            chunks: List[bytes] = []
            consumed = 0
            for chunk in self.artifact_index.stream_file(relative_path):
                take = min(len(chunk), limit - consumed)
                chunks.append(chunk[:take])
                consumed += take
                if consumed >= limit:
                    break
            return b"".join(chunks)
        except (FileNotFoundError, OSError, ValueError):
            return b""

    @staticmethod
    def _sanitize_artifact_text(raw: bytes) -> str:
        text = raw.decode("utf-8", errors="replace")
        try:
            return json.dumps(_sanitize(json.loads(text)), ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            return _redact_string(text)

    @staticmethod
    def _truncate_utf8(value: str, limit: int) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) <= limit:
            return value
        return encoded[:limit].decode("utf-8", errors="ignore")

    @staticmethod
    def _deterministic_signals(
        steps: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        for step in steps:
            raw = next(
                (
                    str(step.get(field))
                    for field in ("failure_reason", "error", "notes")
                    if step.get(field)
                ),
                "",
            )
            status_code = step.get("status_code") or step.get("http_status")
            try:
                status_code = int(status_code) if status_code is not None else None
            except (TypeError, ValueError):
                status_code = None
            category = normalize_failure(raw, status_code)
            action = str(step.get("action_type") or "").casefold()
            if "visual" in action:
                category = "Visual mismatch"
            elif "accessib" in action:
                category = "Accessibility violation"
            elif "security" in action:
                category = "Security finding"
            elif "performance" in action or "response_time" in action or "page_load" in action:
                category = "Performance budget"
            signals.append(
                {
                    "step_id": step.get("step_id"),
                    "category": category,
                    "signal": raw or f"Step status: {step.get('status')}",
                    "provenance": _provenance(step.get("provenance")),
                }
            )
        if not signals and events:
            event = events[-1]
            signals.append(
                {
                    "step_id": event.get("step_id"),
                    "category": normalize_failure(event.get("message")),
                    "signal": event.get("message") or event.get("event_type"),
                    "provenance": Provenance.UNAVAILABLE.value,
                }
            )
        for item in evidence:
            evidence_type = str(item.get("type") or "").casefold()
            searchable = json.dumps(
                {"metadata": item.get("metadata"), "content": item.get("content")},
                ensure_ascii=False,
                default=str,
            )
            category: Optional[str] = None
            if "visual" in evidence_type:
                category = "Visual mismatch"
            elif "accessib" in evidence_type:
                category = "Accessibility violation"
            elif "security" in evidence_type:
                category = "Security finding"
            elif "performance" in evidence_type or "timing" in evidence_type:
                category = "Performance budget"
            elif "console" in evidence_type and "error" in searchable.casefold():
                category = normalize_failure(searchable)
            elif "network" in evidence_type or "api_" in evidence_type:
                status_code = (item.get("metadata") or {}).get("status_code")
                try:
                    status_code = int(status_code) if status_code is not None else None
                except (TypeError, ValueError):
                    status_code = None
                normalized = normalize_failure(searchable, status_code)
                if normalized != "Unknown":
                    category = normalized
            if category:
                signals.append(
                    {
                        "step_id": item.get("step_id"),
                        "category": category,
                        "signal": f"{item.get('type')} evidence {item.get('id')}",
                        "provenance": _provenance(item.get("provenance")),
                    }
                )
        return signals[:20]

    def _try_model(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        prompt = self._build_prompt(context)
        safe = make_safe(prompt, private_mode=True, cloud_target=False)
        try:
            base_url = getattr(self.router.client, "base_url", "http://127.0.0.1:11434")
            reachable, _, reason = check_ollama_health(base_url=base_url, timeout=1.0)
            if reachable:
                model = self.router.model_registry[ModelCapability.QA_REASONING][0].name
                reachable, reason = probe_ollama_chat_ready(
                    model=model, base_url=base_url, timeout=2.0
                )
            if not reachable:
                logger.info("Local RCA model unavailable; deterministic fallback selected")
                return None
            result = self.router.specialist_router.route(
                component=RoutingComponent.STRUCTURED_REASONING,
                prompt=safe.safe_prompt,
                context={"contains_source_code": False},
                require_json=True,
                deterministic_fallback=None,
            )
            if not result.success:
                return None
            self._last_model_metadata = {
                "model": str(result.model)[:120],
                "provider": str(result.provider)[:40],
            }
            parsed = self.router._extract_json(result.content)
            if isinstance(parsed, dict):
                return parsed
            loaded = json.loads(result.content)
            return loaded if isinstance(loaded, dict) else None
        except Exception:
            # Never put exception text in logs: provider errors can contain secrets.
            logger.info("Local RCA model call failed; deterministic fallback selected")
            return None

    @staticmethod
    def _build_prompt(context: Dict[str, Any]) -> str:
        return (
            "You are a cautious QA analyst. Produce draft possible causes only. "
            "Every hypothesis must cite evidence_refs from the supplied step/evidence IDs. "
            "Never claim certainty, invent evidence, generate code patches, modify verdicts, "
            "or propose selector auto-healing. List contradicting and missing evidence. "
            "Return strict JSON: {\"suggestions\": [{\"step_id\": string|null, "
            "\"title\": string, \"possible_cause\": advisory string, \"category\": string, "
            "\"confidence\": number, \"evidence_refs\": [{\"type\": \"evidence|step_field\", "
            "\"id\": string, \"field\": string}], \"supporting_signals\": [string], "
            "\"contradicting_signals\": [string], \"missing_evidence\": [string], "
            "\"recommended_verification\": [string], \"suggested_owner_area\": string, "
            "\"authoritative\": false}]}.\nGROUNDING CONTEXT:\n"
            + json.dumps(context, ensure_ascii=False, default=str)
        )

    def _validate_model_suggestions(
        self,
        output: Any,
        context: Dict[str, Any],
        analysis_id: str,
        run_id: str,
        created_at: str,
    ) -> List[Dict[str, Any]]:
        if not isinstance(output, dict) or not isinstance(output.get("suggestions"), list):
            return []
        evidence_by_id = {item["id"]: item for item in context["evidence"] if item.get("id")}
        step_by_id = {item["step_id"]: item for item in context["steps"] if item.get("step_id")}
        validated: List[Dict[str, Any]] = []
        for raw in output["suggestions"][:5]:
            if not isinstance(raw, dict) or raw.get("authoritative") is True:
                continue
            raw_refs = raw.get("evidence_refs")
            if not isinstance(raw_refs, list) or not raw_refs:
                continue
            step_id = raw.get("step_id")
            if step_id is not None and step_id not in step_by_id:
                continue
            refs = self._validate_refs(raw_refs, evidence_by_id, step_by_id)
            if not refs or len(refs) != len(raw_refs):
                continue
            possible_cause = self._make_advisory(str(raw.get("possible_cause") or ""))
            confidence = self._confidence(raw.get("confidence"), refs, model_backed=True)
            candidate = {
                "suggestion_id": str(uuid.uuid4()),
                "analysis_id": analysis_id,
                "run_id": run_id,
                "step_id": step_id,
                "rank": len(validated) + 1,
                "title": str(raw.get("title") or "Possible execution cause")[:240],
                "possible_cause": possible_cause,
                "category": str(raw.get("category") or "Unknown")[:120],
                "confidence": confidence,
                "evidence_refs": refs,
                "supporting_signals": self._string_list(raw.get("supporting_signals")),
                "contradicting_signals": self._string_list(raw.get("contradicting_signals")),
                "missing_evidence": self._string_list(raw.get("missing_evidence")),
                "recommended_verification": self._string_list(raw.get("recommended_verification")),
                "suggested_owner_area": str(raw.get("suggested_owner_area") or "unknown")[:120],
                "source_provenance": _aggregate_provenance(ref["provenance"] for ref in refs),
                "generation_source": str(
                    self._last_model_metadata.get("provider") or "ollama"
                ),
                "generation_metadata": _sanitize(self._last_model_metadata),
                "authoritative": False,
                "created_at": created_at,
            }
            try:
                validated.append(AIRootCauseSuggestion(**candidate).model_dump(mode="json"))
            except ValueError:
                continue
        return validated

    @staticmethod
    def _validate_refs(
        raw_refs: List[Any],
        evidence_by_id: Dict[str, Dict[str, Any]],
        step_by_id: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        refs: List[Dict[str, Any]] = []
        for raw_ref in raw_refs:
            if not isinstance(raw_ref, dict):
                return []
            ref_type = str(raw_ref.get("type") or "")
            ref_id = str(raw_ref.get("id") or "")
            field = str(raw_ref.get("field") or "")
            if ref_type == "evidence" and ref_id in evidence_by_id:
                provenance = evidence_by_id[ref_id].get("provenance")
            elif ref_type == "step_field" and ref_id in step_by_id and field in step_by_id[ref_id]:
                provenance = step_by_id[ref_id].get("provenance")
            else:
                return []
            refs.append(
                {
                    "type": ref_type,
                    "id": ref_id,
                    "field": field[:120],
                    "provenance": _provenance(provenance),
                }
            )
        return refs

    def _fallback_suggestions(
        self,
        context: Dict[str, Any],
        analysis_id: str,
        run_id: str,
        created_at: str,
    ) -> List[Dict[str, Any]]:
        signals = context.get("deterministic_signals") or []
        if not signals:
            return []
        signal = signals[0]
        step_id = signal.get("step_id")
        step = next(
            (item for item in context["steps"] if item.get("step_id") == step_id),
            None,
        )
        evidence = next(
            (
                item
                for item in context["evidence"]
                if item.get("step_id") in {None, step_id}
            ),
            None,
        )
        if evidence is not None:
            refs = [
                {
                    "type": "evidence",
                    "id": evidence["id"],
                    "field": "content" if evidence.get("content") else "metadata",
                    "provenance": _provenance(evidence.get("provenance")),
                }
            ]
        elif step is not None:
            field = next(
                (name for name in ("failure_reason", "error", "notes", "status") if step.get(name)),
                None,
            )
            if field is None:
                return []
            refs = [
                {
                    "type": "step_field",
                    "id": step["step_id"],
                    "field": field,
                    "provenance": _provenance(step.get("provenance")),
                }
            ]
        else:
            return []
        category = str(signal.get("category") or "Unknown")
        wording = self._fallback_wording(category)
        candidate = {
            "suggestion_id": str(uuid.uuid4()),
            "analysis_id": analysis_id,
            "run_id": run_id,
            "step_id": step_id,
            "rank": 1,
            "title": f"Possible {category.casefold()} cause",
            "possible_cause": wording,
            "category": category,
            "confidence": self._confidence(0.35, refs, model_backed=False),
            "evidence_refs": refs,
            "supporting_signals": [str(signal.get("signal") or category)[:500]],
            "contradicting_signals": [],
            "missing_evidence": [
                "Additional independent execution evidence is needed to confirm this hypothesis."
            ],
            "recommended_verification": [
                "Review the cited execution evidence and reproduce the failed step under the same conditions."
            ],
            "suggested_owner_area": self._owner_area(category),
            "source_provenance": _aggregate_provenance(ref["provenance"] for ref in refs),
            "generation_source": "local_fallback",
            "generation_metadata": {"mode": "deterministic"},
            "authoritative": False,
            "created_at": created_at,
        }
        return [AIRootCauseSuggestion(**candidate).model_dump(mode="json")]

    @staticmethod
    def _fallback_wording(category: str) -> str:
        mapping = {
            "Timeout": "Possible cause: the target may not have reached the expected state before the timeout.",
            "Element not found": "Possible cause: the page state or selector may not match the captured execution state.",
            "Assertion failed": "Possible cause: the observed value may differ from the validation expectation.",
            "HTTP 4xx": "Possible cause: the request may be invalid or unauthorized for the target endpoint.",
            "HTTP 5xx": "Possible cause: the target service may have returned an upstream or server failure.",
            "Network error": "Possible cause: the target may have been unreachable during execution.",
            "Browser crash": "Possible cause: the browser runtime may have failed during the step.",
            "Visual mismatch": "Possible cause: the rendered UI may differ from the approved baseline.",
            "Accessibility violation": "Possible cause: the rendered page may violate an evaluated accessibility rule.",
            "Security finding": "Possible cause: the response may be missing an expected security control.",
            "Performance budget": "Possible cause: the measured operation may have exceeded its configured performance budget.",
        }
        return mapping.get(
            category,
            "Possible cause: the recorded execution signal may indicate a mismatch requiring verification.",
        )

    @staticmethod
    def _owner_area(category: str) -> str:
        if category in {"HTTP 4xx", "HTTP 5xx", "Network error"}:
            return "service_or_api"
        if category == "Performance budget":
            return "performance"
        if category == "Security finding":
            return "security"
        if category == "Accessibility violation":
            return "accessibility"
        return "test_automation"

    @staticmethod
    def _make_advisory(value: str) -> str:
        text = value.strip()
        for phrase in _ABSOLUTE_PHRASES:
            text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE).strip(" :-")
        if not text:
            text = "the recorded signals may indicate an execution mismatch"
        if text.casefold().startswith("possible cause:"):
            return text[:2_000]
        return f"Possible cause: {text[:1_980]}"

    @staticmethod
    def _confidence(value: Any, refs: List[Dict[str, Any]], *, model_backed: bool) -> float:
        try:
            confidence = max(0.0, float(value))
        except (TypeError, ValueError):
            confidence = 0.0
        independent = len({(ref["type"], ref["id"]) for ref in refs})
        if independent <= 1:
            cap = 0.35
        elif independent == 2:
            cap = 0.55
        else:
            cap = 0.80 if model_backed else 0.65
        return min(confidence, cap, 0.80)

    @staticmethod
    def _string_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [_redact_string(str(item))[:500] for item in value[:20]]
