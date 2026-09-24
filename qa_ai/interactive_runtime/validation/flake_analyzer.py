"""
flake_analyzer.py - Detect unstable/flaky behavior across multiple validation runs.

Inputs: List[ValidationResult] for the same or multiple targets.
Output: FlakeReport with ranked FlakeFinding entries.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Dict, List

from qa_ai.interactive_runtime.validation.validation_result import (
    FlakeFinding,
    FlakeReport,
    FlakeSeverity,
    RepeatabilityResult,
    TargetValidationStatus,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class FlakeAnalyzer:
    """
    Detects flaky behavior from:
    - Multiple ValidationResult for same target (verdict inconsistency)
    - RepeatabilityResult (stability score, variance)
    """

    def analyze_results(self, results: List[ValidationResult]) -> FlakeReport:
        """Analyze results grouped by target_id."""
        by_target: Dict[str, List[ValidationResult]] = {}
        for r in results:
            by_target.setdefault(r.target_id, []).append(r)

        findings: List[FlakeFinding] = []
        for tid, runs in by_target.items():
            findings.extend(self._analyze_target_runs(tid, runs))

        return self._build_report(list(by_target.keys()), findings)

    def analyze_repeatability(self, rep: RepeatabilityResult) -> FlakeReport:
        """Derive flake findings from a RepeatabilityResult."""
        findings: List[FlakeFinding] = []

        score = rep.repeatability_score
        if score < 0.5:
            findings.append(FlakeFinding(
                target_id=rep.target_id,
                signal=f"Low repeatability score: {score:.2f} ({rep.stable_runs}/{rep.total_runs} stable)",
                severity=FlakeSeverity.BLOCKER,
                evidence=[f"run {m.run_index}: {m.live_verdict or m.status.value}" for m in rep.runs],
                recommendation="Investigate launch stability and timing-dependent failures.",
            ))
        elif score < 0.75:
            findings.append(FlakeFinding(
                target_id=rep.target_id,
                signal=f"Moderate repeatability score: {score:.2f}",
                severity=FlakeSeverity.HIGH,
                evidence=[f"run {m.run_index}: {m.live_verdict or m.status.value}" for m in rep.runs],
                recommendation="Add wait/retry logic or increase readiness_timeout_seconds.",
            ))

        # verdict inconsistency
        live_verdicts = [m.live_verdict for m in rep.runs if m.live_verdict]
        if live_verdicts:
            dist = Counter(live_verdicts)
            if len(dist) > 1:
                evidence = [f"run {m.run_index}: {m.live_verdict}" for m in rep.runs if m.live_verdict]
                findings.append(FlakeFinding(
                    target_id=rep.target_id,
                    signal=f"Mixed live verdicts across {len(live_verdicts)} runs: {dict(dist)}",
                    severity=FlakeSeverity.HIGH,
                    evidence=evidence,
                    recommendation="Check for timing-dependent UI conditions or app startup flakiness.",
                ))

        # duration variance
        if rep.duration_variance > 30.0:
            findings.append(FlakeFinding(
                target_id=rep.target_id,
                signal=f"High duration variance: {rep.duration_variance:.1f}s²",
                severity=FlakeSeverity.MEDIUM,
                evidence=[f"avg={rep.avg_duration_seconds:.1f}s, var={rep.duration_variance:.1f}s²"],
                recommendation="Identify slow-loading UI elements or network-dependent steps.",
            ))

        # errors
        error_runs = [m for m in rep.runs if m.status == TargetValidationStatus.ERROR]
        if error_runs:
            findings.append(FlakeFinding(
                target_id=rep.target_id,
                signal=f"{len(error_runs)}/{rep.total_runs} runs ended in ERROR",
                severity=FlakeSeverity.BLOCKER if len(error_runs) == rep.total_runs else FlakeSeverity.HIGH,
                evidence=[f"run {m.run_index}: {m.error}" for m in error_runs],
                recommendation="Fix root cause errors before measuring repeatability.",
            ))

        # capability gaps inconsistency
        gap_sets = [frozenset(m.capability_gaps) for m in rep.runs]
        if len(set(gap_sets)) > 1:
            findings.append(FlakeFinding(
                target_id=rep.target_id,
                signal="Capability gaps differ across runs",
                severity=FlakeSeverity.MEDIUM,
                evidence=[f"run {m.run_index}: {m.capability_gaps}" for m in rep.runs],
                recommendation="Driver capabilities should be deterministic. Check OS permission state.",
            ))

        return self._build_report([rep.target_id], findings)

    # ── internals ─────────────────────────────────────────────────────────────

    def _analyze_target_runs(
        self, target_id: str, runs: List[ValidationResult]
    ) -> List[FlakeFinding]:
        findings: List[FlakeFinding] = []

        # mixed verdicts
        live_verdicts = [r.live_verdict for r in runs if r.live_verdict]
        if live_verdicts:
            dist = Counter(live_verdicts)
            if len(dist) > 1:
                findings.append(FlakeFinding(
                    target_id=target_id,
                    signal=f"Inconsistent live verdicts: {dict(dist)}",
                    severity=FlakeSeverity.HIGH,
                    evidence=[f"run {i}: {r.live_verdict}" for i, r in enumerate(runs)],
                    recommendation="Stabilize before trusting PASS/FAIL signals.",
                ))

        # any errors
        errors = [r for r in runs if r.status == TargetValidationStatus.ERROR]
        if errors:
            findings.append(FlakeFinding(
                target_id=target_id,
                signal=f"{len(errors)}/{len(runs)} runs errored",
                severity=FlakeSeverity.HIGH if len(errors) < len(runs) else FlakeSeverity.BLOCKER,
                evidence=[f"run {i}: {r.error}" for i, r in enumerate(runs) if r.error],
                recommendation="Fix errors before reliability assessment.",
            ))

        # UNCLEAR dominance
        unclear = [r for r in runs if r.live_verdict == "unclear"]
        if len(unclear) > len(runs) * 0.5:
            findings.append(FlakeFinding(
                target_id=target_id,
                signal=f"Majority of runs returned UNCLEAR ({len(unclear)}/{len(runs)})",
                severity=FlakeSeverity.MEDIUM,
                evidence=[f"run {i}: unclear" for i, r in enumerate(runs) if r.live_verdict == "unclear"],
                recommendation="Strengthen verification evidence or add observable assertions.",
            ))

        # blocked platform
        blocked = [r for r in runs if r.status == TargetValidationStatus.BLOCKED_PLATFORM]
        if blocked:
            findings.append(FlakeFinding(
                target_id=target_id,
                signal=f"Target blocked by platform mismatch on {len(blocked)}/{len(runs)} runs",
                severity=FlakeSeverity.LOW,
                evidence=[r.notes for r in blocked if r.notes],
                recommendation="Set expected_platform in validation pack or run on correct OS.",
            ))

        return findings

    def _build_report(
        self, target_ids: List[str], findings: List[FlakeFinding]
    ) -> FlakeReport:
        return FlakeReport(
            analyzed_targets=target_ids,
            total_findings=len(findings),
            blocker_count=sum(1 for f in findings if f.severity == FlakeSeverity.BLOCKER),
            high_count=sum(1 for f in findings if f.severity == FlakeSeverity.HIGH),
            medium_count=sum(1 for f in findings if f.severity == FlakeSeverity.MEDIUM),
            low_count=sum(1 for f in findings if f.severity == FlakeSeverity.LOW),
            findings=findings,
        )
