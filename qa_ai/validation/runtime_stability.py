"""
runtime_stability.py - Measures runtime stability across validation runs.

Stability metrics:
- verification_rate    : phases_completed / phases_attempted (per run)
- error_rate           : runs with errors / total runs
- mean_duration        : average execution time across runs
- phase_success_rates  : per-phase completion rate across all runs
- crash_free_rate      : runs that completed without "error" status / total
- artifact_yield       : artifacts_produced / phases_attempted (density measure)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List

from qa_ai.validation.harness import ValidationRun


@dataclass
class RunStabilityRecord:
    run_id: str
    target_name: str
    status: str
    duration_seconds: float
    phases_attempted: int
    phases_completed: int
    verification_rate: float
    artifact_count: int
    error_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "target_name": self.target_name,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "phases_attempted": self.phases_attempted,
            "phases_completed": self.phases_completed,
            "verification_rate": round(self.verification_rate, 3),
            "artifact_count": self.artifact_count,
            "error_count": self.error_count,
        }


@dataclass
class RuntimeStabilityReport:
    total_runs: int
    crash_free_rate: float
    error_rate: float
    mean_duration_seconds: float
    mean_verification_rate: float
    mean_artifact_yield: float
    per_run: List[RunStabilityRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_runs": self.total_runs,
            "crash_free_rate": round(self.crash_free_rate, 3),
            "error_rate": round(self.error_rate, 3),
            "mean_duration_seconds": round(self.mean_duration_seconds, 2),
            "mean_verification_rate": round(self.mean_verification_rate, 3),
            "mean_artifact_yield": round(self.mean_artifact_yield, 3),
            "per_run": [r.to_dict() for r in self.per_run],
        }


class RuntimeStabilityAnalyzer:
    """Compute stability metrics from a list of ValidationRun results."""

    def analyze(self, runs: List[ValidationRun]) -> RuntimeStabilityReport:
        if not runs:
            return RuntimeStabilityReport(
                total_runs=0,
                crash_free_rate=0.0,
                error_rate=0.0,
                mean_duration_seconds=0.0,
                mean_verification_rate=0.0,
                mean_artifact_yield=0.0,
            )

        records: List[RunStabilityRecord] = []
        for run in runs:
            attempted = max(run.phases_attempted, 1)
            completed = run.phases_completed
            ver_rate = completed / attempted
            artifact_yield = len(run.artifacts) / attempted

            records.append(RunStabilityRecord(
                run_id=run.run_id,
                target_name=run.target.name,
                status=run.status,
                duration_seconds=run.duration_seconds,
                phases_attempted=run.phases_attempted,
                phases_completed=run.phases_completed,
                verification_rate=ver_rate,
                artifact_count=len(run.artifacts),
                error_count=len(run.errors),
            ))

        n = len(records)
        crash_free = sum(1 for r in records if r.status != "error") / n
        error_rate = sum(1 for r in records if r.error_count > 0) / n
        mean_dur = sum(r.duration_seconds for r in records) / n
        mean_ver = sum(r.verification_rate for r in records) / n
        mean_yield = sum(len(run.artifacts) / max(run.phases_attempted, 1) for run in runs) / n

        return RuntimeStabilityReport(
            total_runs=n,
            crash_free_rate=crash_free,
            error_rate=error_rate,
            mean_duration_seconds=mean_dur,
            mean_verification_rate=mean_ver,
            mean_artifact_yield=mean_yield,
            per_run=records,
        )
