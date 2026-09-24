"""
repeatability_runner.py - Run a target N times and compute a repeatability score.

repeatability_score = stable_successful_runs / total_runs

"stable" = all non-error runs produce the same live_verdict.
"""
from __future__ import annotations

import logging
import statistics
from typing import List, Optional

from qa_ai.interactive_runtime.validation.validation_target import ValidationTarget
from qa_ai.interactive_runtime.validation.validation_result import (
    RepeatabilityResult,
    RunMetrics,
    TargetValidationStatus,
    ValidationResult,
)
from qa_ai.interactive_runtime.validation.validation_runner import ValidationRunner

logger = logging.getLogger(__name__)


class RepeatabilityRunner:
    """
    Run a ValidationTarget multiple times and produce RepeatabilityResult.

    repeat_count: how many times to run
    stop_on_first_crash: abort remaining runs if one errors
    """

    def __init__(
        self,
        output_dir: str = "artifacts",
        repeat_count: int = 3,
        stop_on_first_crash: bool = False,
        interactive: bool = False,
    ):
        self._runner = ValidationRunner(output_dir=output_dir, interactive=interactive)
        self._repeat_count = max(1, repeat_count)
        self._stop_on_first_crash = stop_on_first_crash

    def run(
        self,
        target: ValidationTarget,
        live_guided: bool = False,
        ai_guided: bool = False,
        max_actions: Optional[int] = None,
    ) -> RepeatabilityResult:
        runs: List[ValidationResult] = []

        for i in range(self._repeat_count):
            logger.info(
                "RepeatabilityRunner: run %d/%d for '%s'",
                i + 1, self._repeat_count, target.target_id,
            )
            result = self._runner.run_live(
                target,
                live_guided=live_guided,
                ai_guided=ai_guided,
                max_actions=max_actions,
            )
            runs.append(result)

            if self._stop_on_first_crash and result.status == TargetValidationStatus.ERROR:
                logger.warning("Crash detected on run %d — stopping.", i + 1)
                break

        return self._aggregate(target, runs)

    def run_dry_only(self, target: ValidationTarget) -> RepeatabilityResult:
        """Dry-run only repeatability (for testing infrastructure without real launches)."""
        runs: List[ValidationResult] = []
        for i in range(self._repeat_count):
            result = self._runner.run_dry(target)
            runs.append(result)
        return self._aggregate(target, runs)

    # ── internals ─────────────────────────────────────────────────────────────

    def _aggregate(
        self, target: ValidationTarget, runs: List[ValidationResult]
    ) -> RepeatabilityResult:
        total = len(runs)
        if total == 0:
            return RepeatabilityResult(
                target_id=target.target_id,
                app_name=target.app_name,
                total_runs=0,
                successful_runs=0,
                stable_runs=0,
                repeatability_score=0.0,
            )

        successful = [
            r for r in runs
            if r.status not in (
                TargetValidationStatus.ERROR,
                TargetValidationStatus.BLOCKED_PLATFORM,
                TargetValidationStatus.BLOCKED_PERMISSION,
            )
        ]

        # verdict distribution
        verdict_dist: dict = {}
        for r in runs:
            v = r.live_verdict or r.status.value
            verdict_dist[v] = verdict_dist.get(v, 0) + 1

        # stability: all successful runs share same verdict
        live_verdicts = [r.live_verdict for r in successful if r.live_verdict is not None]
        stable_count = 0
        if live_verdicts:
            dominant = max(set(live_verdicts), key=live_verdicts.count)
            stable_count = sum(1 for v in live_verdicts if v == dominant)
        elif successful:
            # no live runs but dry-run stable
            statuses = [r.status.value for r in successful]
            dominant_s = max(set(statuses), key=statuses.count)
            stable_count = sum(1 for s in statuses if s == dominant_s)

        repeatability_score = stable_count / total if total > 0 else 0.0

        coverages = [r.coverage_pct for r in runs if r.coverage_pct > 0]
        avg_cov = statistics.mean(coverages) if coverages else 0.0

        durations = [r.duration_seconds for r in runs]
        avg_dur = statistics.mean(durations) if durations else 0.0
        dur_var = statistics.variance(durations) if len(durations) > 1 else 0.0

        run_metrics = [
            RunMetrics(
                run_index=i,
                status=r.status,
                live_verdict=r.live_verdict,
                coverage_pct=r.coverage_pct,
                duration_seconds=r.duration_seconds,
                capability_gaps=r.capability_gaps,
                error=r.error,
            )
            for i, r in enumerate(runs)
        ]

        return RepeatabilityResult(
            target_id=target.target_id,
            app_name=target.app_name,
            total_runs=total,
            successful_runs=len(successful),
            stable_runs=stable_count,
            repeatability_score=round(repeatability_score, 3),
            verdict_distribution=verdict_dist,
            avg_coverage_pct=round(avg_cov, 2),
            avg_duration_seconds=round(avg_dur, 3),
            duration_variance=round(dur_var, 3),
            runs=run_metrics,
        )
