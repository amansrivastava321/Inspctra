"""
utility_scorer.py - Score evidence utility for retention decisions.

Formula: U = (Impact * Frequency * Specificity * RecencyBoost * Reuse) / TimeDecay

Configurable weights. Returns 0-100 score + retention class.
No hardcoded app logic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class UtilityWeights:
    impact: float = 0.35
    frequency: float = 0.25
    specificity: float = 0.20
    reuse: float = 0.15
    recency: float = 0.05


@dataclass
class UtilityResult:
    raw_score: float      # 0.0 – 1.0
    utility_score: float  # 0 – 100
    retention_class: str  # hot|warm|cold|delete_candidate
    factors: Dict[str, float] = field(default_factory=dict)


_DEFAULT_WEIGHTS = UtilityWeights()

# Retention class thresholds
_HOT_THRESHOLD = 70.0
_WARM_THRESHOLD = 40.0
_COLD_THRESHOLD = 15.0


def _days_old(created_at_iso: Optional[str]) -> float:
    if not created_at_iso:
        return 30.0
    try:
        dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0.0, (now - dt).total_seconds() / 86400.0)
    except Exception:
        return 30.0


def score_evidence(
    evidence_type: str,
    verdict: str,
    frequency: int = 1,
    used_in_fix: bool = False,
    used_in_report: bool = False,
    is_duplicate: bool = False,
    days_old: Optional[float] = None,
    created_at: Optional[str] = None,
    severity: str = "medium",
    weights: Optional[UtilityWeights] = None,
) -> UtilityResult:
    """
    Score evidence utility.

    Returns UtilityResult with 0-100 score and retention_class.
    """
    w = weights or _DEFAULT_WEIGHTS

    # Impact factor (0–1)
    impact = _impact_factor(verdict, evidence_type, severity)

    # Frequency factor (0–1)
    freq = _frequency_factor(frequency)

    # Specificity (0–1): duplicates are low
    specificity = 0.1 if is_duplicate else _specificity_factor(evidence_type, verdict)

    # Reuse (0–1): cited in fix or report
    reuse = 0.0
    if used_in_fix:
        reuse = 1.0
    elif used_in_report:
        reuse = 0.7

    # Recency boost (0–1)
    age = days_old if days_old is not None else _days_old(created_at)
    recency = _recency_factor(age, verdict)

    # Time decay divisor
    decay = _time_decay(age, verdict)

    # Weighted product
    numerator = (
        w.impact * impact
        + w.frequency * freq
        + w.specificity * specificity
        + w.reuse * reuse
        + w.recency * recency
    )
    raw = min(1.0, numerator / decay)
    score = round(raw * 100, 1)

    cls = (
        "hot" if score >= _HOT_THRESHOLD
        else "warm" if score >= _WARM_THRESHOLD
        else "cold" if score >= _COLD_THRESHOLD
        else "delete_candidate"
    )

    return UtilityResult(
        raw_score=raw,
        utility_score=score,
        retention_class=cls,
        factors={
            "impact": impact,
            "frequency": freq,
            "specificity": specificity,
            "reuse": reuse,
            "recency": recency,
            "time_decay": decay,
            "age_days": round(age, 1),
        },
    )


def _impact_factor(verdict: str, evidence_type: str, severity: str) -> float:
    v = verdict.lower()
    sev_map = {"critical": 1.0, "high": 0.85, "medium": 0.6, "low": 0.35, "info": 0.15}
    base = sev_map.get(severity.lower(), 0.5)

    if v in ("fail", "failed", "failure"):
        return min(1.0, base * 1.5)
    if v in ("unclear", "blocked"):
        return min(1.0, base * 1.1)
    if v in ("pass", "passed"):
        return base * 0.3
    return base * 0.5


def _frequency_factor(frequency: int) -> float:
    if frequency <= 1:
        return 0.3
    if frequency <= 3:
        return 0.5
    if frequency <= 10:
        return 0.75
    return min(1.0, 0.75 + 0.005 * frequency)


def _specificity_factor(evidence_type: str, verdict: str) -> float:
    t = evidence_type.lower()
    v = verdict.lower()
    # Screenshots of failures are highly specific
    if t == "screenshot" and v in ("fail", "unclear"):
        return 0.9
    if t in ("screenshot",) and v in ("pass",):
        return 0.2
    if t in ("log", "trace"):
        return 0.7 if v in ("fail", "unclear") else 0.3
    if t in ("api", "db"):
        return 0.8 if v in ("fail",) else 0.5
    if t == "connector":
        return 0.6
    return 0.5


def _recency_factor(age_days: float, verdict: str) -> float:
    if age_days <= 1:
        return 1.0
    if age_days <= 7:
        return 0.8
    if age_days <= 30:
        return 0.5
    return 0.2


def _time_decay(age_days: float, verdict: str) -> float:
    v = verdict.lower()
    if v in ("fail", "unclear", "blocked"):
        # Slow decay for failure evidence
        return 1.0 + 0.005 * age_days
    # Faster decay for passing evidence
    return 1.0 + 0.02 * age_days


def score_summary(
    source_type: str,
    severity: str,
    frequency: int = 1,
    used_in_report: bool = False,
    created_at: Optional[str] = None,
    weights: Optional[UtilityWeights] = None,
) -> UtilityResult:
    verdict_map = {
        "finding": "fail",
        "pattern": "fail",
        "trajectory": "fail",
        "run": "pass",
        "report": "pass",
    }
    return score_evidence(
        evidence_type=source_type,
        verdict=verdict_map.get(source_type, "pass"),
        frequency=frequency,
        used_in_report=used_in_report,
        severity=severity,
        created_at=created_at,
        weights=weights,
    )
