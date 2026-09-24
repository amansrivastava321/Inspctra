"""
ai_oracle.py - LLM reasoning to judge whether an action likely succeeded.

CRITICAL: AIOracle returns suggestions only. It cannot finalize verdicts.
Final verdict must go through EvidenceGrounder.

If no model is configured → returns UNCLEAR suggestion with capability gap noted.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.schemas import (
    AIGuidanceConfig,
    AIVerdict,
    CapabilityGap,
    CapabilityStatus,
    OracleSuggestion,
    VerificationResult,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class AIOracle:
    """
    Use LLM reasoning to suggest whether an action succeeded.

    Inputs summary + deterministic verification → suggested verdict.
    Never produces final PASS. Always is_suggestion_only=True.
    """

    def __init__(self, config: Optional[AIGuidanceConfig] = None):
        self._config = config or AIGuidanceConfig()
        self._available: Optional[bool] = None

    def suggest(
        self,
        step_id: str,
        action_description: str,
        expected_outcome: str,
        screen_before_summary: str,
        screen_after_summary: str,
        log_snippets: Optional[List[str]] = None,
        db_check_summary: Optional[str] = None,
        backend_check_summary: Optional[str] = None,
        file_check_summary: Optional[str] = None,
        deterministic_result: Optional[VerificationResult] = None,
    ) -> OracleSuggestion:
        """
        Build a suggested verdict.

        Returns OracleSuggestion with is_suggestion_only=True always.
        Deterministic failures short-circuit to FAIL suggestion immediately.
        """
        # Deterministic failure overrides oracle — no need to call LLM
        if deterministic_result and deterministic_result.overall_status == VerificationStatus.FAILED:
            return OracleSuggestion(
                step_id=step_id,
                suggested_verdict=AIVerdict.FAIL,
                reasoning="Deterministic verification failed — oracle defers to evidence.",
                confidence=0.90,
                evidence_gaps=[],
                recommended_next_check="Review failing deterministic checks above.",
                is_suggestion_only=True,
            )

        # Build evidence context
        evidence_context = self._build_evidence_context(
            action_description, expected_outcome,
            screen_before_summary, screen_after_summary,
            log_snippets, db_check_summary, backend_check_summary, file_check_summary,
            deterministic_result,
        )

        # Try LLM if enabled and available
        if self._config.enabled and not self._config.allow_cloud and self._is_local_available():
            try:
                return self._suggest_via_llm(step_id, evidence_context)
            except Exception as exc:
                logger.warning("Oracle LLM call failed, falling back to heuristic: %s", exc)

        # Heuristic fallback
        return self._heuristic_suggest(step_id, evidence_context, deterministic_result)

    def _heuristic_suggest(
        self,
        step_id: str,
        ctx: Dict[str, Any],
        deterministic_result: Optional[VerificationResult],
    ) -> OracleSuggestion:
        """Rule-based suggestion when no LLM is available."""
        logs = ctx.get("log_snippets") or []
        screen_changed = ctx.get("screen_changed", False)
        det_passed = deterministic_result and deterministic_result.overall_status == VerificationStatus.PASSED

        gaps = []
        if not logs:
            gaps.append("No logs available — cannot verify backend behavior.")
        if not ctx.get("db_check_summary"):
            gaps.append("No DB check performed.")
        if not ctx.get("backend_check_summary"):
            gaps.append("No backend API check performed.")

        if det_passed and screen_changed:
            verdict = AIVerdict.PASS
            conf = 0.65
            reasoning = "Deterministic checks passed and screen state changed as expected."
        elif det_passed:
            verdict = AIVerdict.UNCLEAR
            conf = 0.45
            reasoning = "Deterministic checks passed but no screen change detected."
        elif screen_changed:
            verdict = AIVerdict.UNCLEAR
            conf = 0.40
            reasoning = "Screen changed but no deterministic confirmation available."
        else:
            verdict = AIVerdict.UNCLEAR
            conf = 0.25
            reasoning = "Insufficient evidence to determine outcome."

        next_check = "Add log tags or DB verification to confirm outcome." if gaps else ""

        return OracleSuggestion(
            step_id=step_id,
            suggested_verdict=verdict,
            reasoning=reasoning,
            confidence=conf,
            evidence_gaps=gaps,
            recommended_next_check=next_check,
            is_suggestion_only=True,
        )

    def _suggest_via_llm(
        self, step_id: str, ctx: Dict[str, Any]
    ) -> OracleSuggestion:
        """Call local model via TaskRouter for reasoning."""
        try:
            from qa_ai.ai.task_router import ModelTask, get_task_router
            router = get_task_router()
            prompt = self._build_prompt(ctx)
            result = router.call(ModelTask.AI_ORACLE, prompt)
            if result.ok:
                return self._parse_llm_response(step_id, result.output_text, ctx)
            # TaskRouter returned capability_gap
            logger.debug("Oracle TaskRouter gap: %s", result.capability_gap)
        except Exception as exc:
            logger.debug("Oracle TaskRouter unavailable, using legacy path: %s", exc)
            # Legacy direct Ollama path as final fallback
            self._suggest_via_llm_legacy(step_id, ctx)
        return self._heuristic_suggest(step_id, ctx, None)

    def _suggest_via_llm_legacy(
        self, step_id: str, ctx: Dict[str, Any]
    ) -> Optional[OracleSuggestion]:
        """Legacy direct Ollama call — only used if TaskRouter unavailable."""
        try:
            import json
            import urllib.request
            prompt = self._build_prompt(ctx)
            payload = json.dumps({
                "model": self._config.model,
                "prompt": prompt,
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                raw = data.get("response", "")
            return self._parse_llm_response(step_id, raw, ctx)
        except Exception:
            return None

    def _parse_llm_response(
        self, step_id: str, raw: str, ctx: Dict[str, Any]
    ) -> OracleSuggestion:
        raw_lower = raw.lower()
        if "fail" in raw_lower or "error" in raw_lower or "not found" in raw_lower:
            verdict = AIVerdict.FAIL
            conf = 0.55
        elif "success" in raw_lower or "pass" in raw_lower or "confirmed" in raw_lower:
            verdict = AIVerdict.UNCLEAR  # Still unclear until EvidenceGrounder confirms
            conf = 0.50
        else:
            verdict = AIVerdict.UNCLEAR
            conf = 0.35

        return OracleSuggestion(
            step_id=step_id,
            suggested_verdict=verdict,
            reasoning=raw[:300],
            confidence=conf,
            evidence_gaps=["LLM response — verify with deterministic evidence."],
            recommended_next_check="Run deterministic verification before finalizing verdict.",
            is_suggestion_only=True,
        )

    def _build_prompt(self, ctx: Dict[str, Any]) -> str:
        return (
            f"Action: {ctx.get('action_description', '')}\n"
            f"Expected: {ctx.get('expected_outcome', '')}\n"
            f"Screen before: {ctx.get('screen_before_summary', '')}\n"
            f"Screen after: {ctx.get('screen_after_summary', '')}\n"
            f"Logs: {'; '.join((ctx.get('log_snippets') or [])[:5])}\n"
            f"DB: {ctx.get('db_check_summary', 'none')}\n"
            f"Backend: {ctx.get('backend_check_summary', 'none')}\n\n"
            "Based on the evidence above, did this action likely succeed? "
            "Answer in 2-3 sentences. Mention 'success' or 'fail' clearly."
        )

    def _build_evidence_context(
        self,
        action_description: str,
        expected_outcome: str,
        screen_before_summary: str,
        screen_after_summary: str,
        log_snippets: Optional[List[str]],
        db_check_summary: Optional[str],
        backend_check_summary: Optional[str],
        file_check_summary: Optional[str],
        deterministic_result: Optional[VerificationResult],
    ) -> Dict[str, Any]:
        screen_changed = screen_before_summary != screen_after_summary
        return {
            "action_description": action_description,
            "expected_outcome": expected_outcome,
            "screen_before_summary": screen_before_summary,
            "screen_after_summary": screen_after_summary,
            "screen_changed": screen_changed,
            "log_snippets": log_snippets or [],
            "db_check_summary": db_check_summary,
            "backend_check_summary": backend_check_summary,
            "file_check_summary": file_check_summary,
            "deterministic_passed": (
                deterministic_result.overall_status == VerificationStatus.PASSED
                if deterministic_result else None
            ),
        }

    def _is_local_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
            self._available = True
        except Exception:
            self._available = False
        return self._available
