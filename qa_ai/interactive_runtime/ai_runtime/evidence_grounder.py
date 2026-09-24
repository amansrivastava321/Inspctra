"""
evidence_grounder.py - Turn AI judgment + deterministic evidence into final verdict.

RULES (non-negotiable):
  PASS requires at least one strong evidence source (UI/log/DB/backend/file/screenshot).
  FAIL if explicit error, crash, expected result missing, or backend/API/DB failed.
  UNCLEAR if action executed but evidence is weak or unavailable.
  Deterministic failure ALWAYS overrides AI oracle suggestion of PASS.
  AI-only → max confidence 0.50, status UNCLEAR.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from qa_ai.interactive_runtime.schemas import (
    AIVerdict,
    EvidenceGroundingConfig,
    EvidenceSource,
    GroundedVerdict,
    OracleSuggestion,
    ScreenState,
    VerificationResult,
    VerificationStatus,
)
from qa_ai.interactive_runtime.ai_runtime.confidence_calibrator import ConfidenceCalibrator

logger = logging.getLogger(__name__)


class EvidenceGrounder:
    """
    Finalize verdict by grounding AI oracle suggestion in deterministic evidence.

    This is the authoritative verdict producer. EvidenceGrounder cannot be overridden
    by AI oracle. Deterministic failures always produce FAIL or UNCLEAR, never PASS.
    """

    def __init__(self, config: Optional[EvidenceGroundingConfig] = None):
        self._config = config or EvidenceGroundingConfig()
        self._calibrator = ConfidenceCalibrator()

    def ground(
        self,
        step_id: str,
        oracle_suggestion: Optional[OracleSuggestion] = None,
        deterministic_result: Optional[VerificationResult] = None,
        screen_after: Optional[ScreenState] = None,
        log_matches: Optional[List[str]] = None,
        db_check_result: Optional[str] = None,
        backend_check_result: Optional[str] = None,
        screenshot_after: Optional[str] = None,
        used_coordinate_click: bool = False,
    ) -> GroundedVerdict:
        """
        Produce the final GroundedVerdict.

        Steps:
          1. Collect evidence sources.
          2. Check for deterministic failure (hard FAIL).
          3. Check for minimum evidence threshold.
          4. Apply AI oracle as advisory input.
          5. Calibrate confidence.
          6. Return final verdict.
        """
        sources, missing = self._collect_evidence(
            deterministic_result, screen_after, log_matches,
            db_check_result, backend_check_result, screenshot_after,
        )

        det_failed = self._is_deterministic_failure(deterministic_result)
        det_passed = self._is_deterministic_pass(deterministic_result)
        has_strong = any(s.strength == "strong" for s in sources)
        ai_only = not sources

        # --- Hard FAIL path ---
        if det_failed:
            conf = self._calibrator.calibrate(
                sources, used_coordinate_click, deterministic_failure=True
            )
            return GroundedVerdict(
                step_id=step_id,
                final_status=AIVerdict.FAIL,
                confidence=conf,
                evidence_sources_used=sources,
                evidence_sources_missing=missing,
                reasoning="Deterministic verification failed — overrides any AI suggestion.",
                next_best_check="Investigate failing checks in deterministic verification.",
                oracle_suggestion=oracle_suggestion,
                deterministic_override=True,
            )

        # --- No evidence path ---
        if ai_only or not sources:
            return GroundedVerdict(
                step_id=step_id,
                final_status=AIVerdict.UNCLEAR,
                confidence=self._config.ai_only_max_confidence,
                evidence_sources_used=[],
                evidence_sources_missing=missing or ["all_evidence_types"],
                reasoning="No deterministic evidence available. AI oracle alone is insufficient for PASS.",
                next_best_check="Add log tags, DB verification, or UI text checks.",
                oracle_suggestion=oracle_suggestion,
                deterministic_override=False,
            )

        # --- Strong evidence path ---
        conf = self._calibrator.calibrate(
            sources,
            used_coordinate_click=used_coordinate_click,
            ai_judgment_only=ai_only,
        )

        # Oracle suggestion adjusts confidence slightly but cannot flip PASS to FAIL alone
        oracle_verdict = oracle_suggestion.suggested_verdict if oracle_suggestion else None

        if has_strong and det_passed:
            final = AIVerdict.PASS
            reasoning = self._pass_reasoning(sources, oracle_verdict)
        elif has_strong and not det_passed:
            # Strong evidence but deterministic inconclusive — borderline
            if conf >= 0.70:
                final = AIVerdict.PASS
                reasoning = f"Strong evidence sources confirm outcome (confidence {conf:.0%})."
            else:
                final = AIVerdict.UNCLEAR
                reasoning = "Evidence present but deterministic checks inconclusive."
        else:
            # Weak/moderate evidence only
            final = AIVerdict.UNCLEAR
            reasoning = "Evidence sources too weak for confident PASS. Needs stronger verification."
            conf = min(conf, 0.60)

        # Require screenshot for UI actions if configured
        if (
            self._config.require_screenshot_for_ui_actions
            and not screenshot_after
            and not any(s.source_type == "screenshot" for s in sources)
        ):
            missing.append("screenshot_after")
            if final == AIVerdict.PASS:
                final = AIVerdict.UNCLEAR
                reasoning += " No screenshot evidence available."
                conf = min(conf, 0.65)

        return GroundedVerdict(
            step_id=step_id,
            final_status=final,
            confidence=conf,
            evidence_sources_used=sources,
            evidence_sources_missing=missing,
            reasoning=reasoning,
            next_best_check=self._next_check(missing, final),
            oracle_suggestion=oracle_suggestion,
            deterministic_override=False,
        )

    def _collect_evidence(
        self,
        deterministic_result: Optional[VerificationResult],
        screen_after: Optional[ScreenState],
        log_matches: Optional[List[str]],
        db_check_result: Optional[str],
        backend_check_result: Optional[str],
        screenshot_after: Optional[str],
    ) -> tuple:
        sources: List[EvidenceSource] = []
        missing: List[str] = []

        # Deterministic checks
        if deterministic_result:
            passed = deterministic_result.passed_count
            failed = deterministic_result.failed_count
            total = len(deterministic_result.checks)
            if passed > 0 and failed == 0:
                sources.append(EvidenceSource(
                    source_type="ui_state",
                    description=f"Deterministic: {passed}/{total} checks passed",
                    strength="strong",
                    detail=f"passed={passed} failed={failed}",
                ))
            elif passed > 0:
                sources.append(EvidenceSource(
                    source_type="ui_state",
                    description=f"Deterministic: {passed}/{total} passed, {failed} failed",
                    strength="moderate",
                ))
        else:
            missing.append("deterministic_verification")

        # UI state
        if screen_after:
            if screen_after.visible_text or screen_after.elements:
                sources.append(EvidenceSource(
                    source_type="ui_state",
                    description=f"Screen '{screen_after.title}' captured",
                    strength="moderate",
                    detail=f"elements={len(screen_after.elements)} text_lines={len(screen_after.visible_text)}",
                ))
        else:
            missing.append("screen_state_after")

        # Log matches
        if log_matches:
            sources.append(EvidenceSource(
                source_type="log",
                description=f"{len(log_matches)} log tag(s) matched",
                strength="strong",
                detail="; ".join(log_matches[:3]),
            ))
        else:
            missing.append("log_evidence")

        # DB check
        if db_check_result:
            strength = "strong" if "pass" in db_check_result.lower() else "moderate"
            sources.append(EvidenceSource(
                source_type="db",
                description="Database check result",
                strength=strength,
                detail=db_check_result[:100],
            ))
        else:
            missing.append("db_check")

        # Backend check
        if backend_check_result:
            strength = "strong" if "200" in backend_check_result or "pass" in backend_check_result.lower() else "moderate"
            sources.append(EvidenceSource(
                source_type="backend",
                description="Backend API check result",
                strength=strength,
                detail=backend_check_result[:100],
            ))
        else:
            missing.append("backend_check")

        # Screenshot
        if screenshot_after:
            sources.append(EvidenceSource(
                source_type="screenshot",
                description="Screenshot captured after action",
                strength="moderate",
                detail=screenshot_after,
            ))

        return sources, missing

    @staticmethod
    def _is_deterministic_failure(result: Optional[VerificationResult]) -> bool:
        return (
            result is not None
            and result.overall_status == VerificationStatus.FAILED
        )

    @staticmethod
    def _is_deterministic_pass(result: Optional[VerificationResult]) -> bool:
        return (
            result is not None
            and result.overall_status == VerificationStatus.PASSED
        )

    @staticmethod
    def _pass_reasoning(sources: List[EvidenceSource], oracle_verdict: Optional[AIVerdict]) -> str:
        source_types = [s.source_type for s in sources if s.strength == "strong"]
        parts = " + ".join(source_types) if source_types else "evidence"
        oracle_note = (
            f" Oracle also suggested {oracle_verdict.value}." if oracle_verdict else ""
        )
        return f"Strong evidence confirms pass: {parts}.{oracle_note}"

    @staticmethod
    def _next_check(missing: List[str], verdict: AIVerdict) -> str:
        if verdict == AIVerdict.PASS:
            return ""
        if "log_evidence" in missing:
            return "Add expected_tags to config to match log output."
        if "db_check" in missing:
            return "Enable database_verification in config."
        if "backend_check" in missing:
            return "Enable backend_verification or add backend_base_url."
        if "screenshot_after" in missing:
            return "Enable screenshot_enabled in config."
        return "Review capability_gaps.json for missing verification capabilities."
