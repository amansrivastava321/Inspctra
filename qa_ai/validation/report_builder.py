"""
report_builder.py - Aggregates ValidationRun results into the 5 report files.

Outputs written to the validation session directory:
  validation_summary.json           - per-run stats + aggregate quality metrics
  validation_findings_quality.json  - per-finding completeness scores
  validation_false_positive_review.json - false-positive candidates
  validation_runtime_stability.json - phase completion rates, timing, crash-free rate
  validation_report.html            - human-readable dashboard combining all above
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.validation.harness import ValidationRun
from qa_ai.validation.findings_quality import FindingsQualityAnalyzer, FindingsQualityReport
from qa_ai.validation.false_positive_detector import FalsePositiveDetector, FalsePositiveReport
from qa_ai.validation.runtime_stability import RuntimeStabilityAnalyzer, RuntimeStabilityReport

logger = logging.getLogger(__name__)


class ValidationReportBuilder:
    """
    Reads findings from completed ValidationRuns, runs analyzers, and
    writes the 5 validation report files to a session output directory.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir or "validation_runs")
        self.quality_analyzer = FindingsQualityAnalyzer()
        self.fp_detector = FalsePositiveDetector()
        self.stability_analyzer = RuntimeStabilityAnalyzer()

    def build(self, runs: List[ValidationRun], session_id: Optional[str] = None) -> Path:
        """
        Build all 5 report files from a list of completed ValidationRuns.

        Args:
            runs: Completed ValidationRun objects from ValidationHarness.run_all()
            session_id: Optional label for this validation session directory

        Returns:
            Path to the session output directory containing the 5 files
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        session_label = session_id or f"session_{ts}"
        session_dir = self.output_dir / session_label
        session_dir.mkdir(parents=True, exist_ok=True)

        all_findings = self._collect_all_findings(runs)

        quality_report = self.quality_analyzer.analyze(all_findings)
        fp_report = self.fp_detector.detect(all_findings)
        stability_report = self.stability_analyzer.analyze(runs)

        self._write_summary(session_dir, runs, quality_report, fp_report, stability_report)
        self._write_findings_quality(session_dir, quality_report)
        self._write_false_positive_review(session_dir, fp_report)
        self._write_runtime_stability(session_dir, stability_report)
        self._write_html_report(session_dir, runs, quality_report, fp_report, stability_report)

        logger.info(
            "Validation reports written to %s (%d runs, %d findings, %d FP candidates)",
            session_dir, len(runs), len(all_findings), fp_report.candidate_count,
        )
        return session_dir

    # ------------------------------------------------------------------ writers

    def _write_summary(
        self,
        out: Path,
        runs: List[ValidationRun],
        quality: FindingsQualityReport,
        fp: FalsePositiveReport,
        stability: RuntimeStabilityReport,
    ) -> None:
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_runs": len(runs),
            "total_findings": quality.total_findings,
            "false_positive_candidates": fp.candidate_count,
            "false_positive_rate": fp.candidate_rate,
            "mean_completeness_score": quality.mean_completeness_score,
            "evidence_completeness_pct": quality.findings_with_evidence_pct,
            "remediation_usefulness_score": quality.remediation_usefulness_score,
            "runtime_verification_rate": stability.mean_verification_rate,
            "crash_free_rate": stability.crash_free_rate,
            "mean_execution_time_seconds": stability.mean_duration_seconds,
            "runs": [r.to_dict() for r in runs],
        }
        _write_json(out / "validation_summary.json", summary)

    def _write_findings_quality(self, out: Path, report: FindingsQualityReport) -> None:
        _write_json(out / "validation_findings_quality.json", report.to_dict())

    def _write_false_positive_review(self, out: Path, report: FalsePositiveReport) -> None:
        _write_json(out / "validation_false_positive_review.json", report.to_dict())

    def _write_runtime_stability(self, out: Path, report: RuntimeStabilityReport) -> None:
        _write_json(out / "validation_runtime_stability.json", report.to_dict())

    def _write_html_report(
        self,
        out: Path,
        runs: List[ValidationRun],
        quality: FindingsQualityReport,
        fp: FalsePositiveReport,
        stability: RuntimeStabilityReport,
    ) -> None:
        html = _build_html(runs, quality, fp, stability)
        (out / "validation_report.html").write_text(html, encoding="utf-8")

    # ------------------------------------------------------------------ helpers

    def _collect_all_findings(self, runs: List[ValidationRun]) -> List[Dict[str, Any]]:
        """Gather findings from all run output directories."""
        all_findings: List[Dict[str, Any]] = []
        for run in runs:
            run_dir = Path(run.output_dir)
            if not run_dir.exists():
                continue
            for json_file in run_dir.rglob("*.json"):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and "findings" in data:
                        findings = data["findings"]
                        if isinstance(findings, list):
                            for f in findings:
                                if isinstance(f, dict):
                                    f.setdefault("_source_run", run.run_id)
                                    f.setdefault("_target", run.target.name)
                                    all_findings.append(f)
                except Exception as e:
                    logger.debug("Could not read findings from %s: %s", json_file, e)
        return all_findings


# ------------------------------------------------------------------ HTML builder

def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _score_color(value: float) -> str:
    if value >= 0.8:
        return "#22c55e"   # green
    if value >= 0.5:
        return "#f59e0b"   # amber
    return "#ef4444"       # red


def _build_html(
    runs: List[ValidationRun],
    quality: FindingsQualityReport,
    fp: FalsePositiveReport,
    stability: RuntimeStabilityReport,
) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Metric cards
    metrics = [
        ("Total Findings", str(quality.total_findings), ""),
        ("FP Candidates", str(fp.candidate_count), _score_color(1 - fp.candidate_rate)),
        ("Evidence Completeness", _pct(quality.findings_with_evidence_pct),
         _score_color(quality.findings_with_evidence_pct)),
        ("Remediation Usefulness", _pct(quality.remediation_usefulness_score),
         _score_color(quality.remediation_usefulness_score)),
        ("Mean Completeness", _pct(quality.mean_completeness_score),
         _score_color(quality.mean_completeness_score)),
        ("Verification Rate", _pct(stability.mean_verification_rate),
         _score_color(stability.mean_verification_rate)),
        ("Crash-Free Rate", _pct(stability.crash_free_rate),
         _score_color(stability.crash_free_rate)),
        ("Mean Exec Time", f"{stability.mean_duration_seconds:.1f}s", ""),
    ]

    _default_color = "#1e293b"
    cards_html = "\n".join(
        f'<div class="card">'
        f'<div class="card-label">{label}</div>'
        f'<div class="card-value" style="color:{color or _default_color}">{value}</div>'
        f'</div>'
        for label, value, color in metrics
    )

    # Runs table
    run_rows = "\n".join(
        f"<tr>"
        f"<td>{r.target.name}</td>"
        f"<td>{r.target.profile}</td>"
        f"<td><span class='badge badge-{r.status}'>{r.status}</span></td>"
        f"<td>{r.finding_count}</td>"
        f"<td>{r.duration_seconds:.1f}s</td>"
        f"<td>{len(r.errors)}</td>"
        f"</tr>"
        for r in runs
    )

    # FP candidates table
    fp_rows = "\n".join(
        f"<tr>"
        f"<td>{c.finding_id}</td>"
        f"<td>{_escape(c.title[:80])}</td>"
        f"<td>{c.severity.upper()}</td>"
        f"<td>{', '.join(c.reasons)}</td>"
        f"<td>{_pct(c.confidence)}</td>"
        f"</tr>"
        for c in fp.candidates[:50]  # cap at 50 rows
    ) or "<tr><td colspan='5'>No false-positive candidates detected.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QA-AI Validation Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #f8fafc;
          color: #1e293b; line-height: 1.5; padding: 2rem; }}
  h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }}
  h2 {{ font-size: 1.2rem; font-weight: 600; margin: 2rem 0 0.75rem; color: #334155; }}
  .meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 2rem; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; }}
  .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
           padding: 1rem 1.25rem; min-width: 160px; }}
  .card-label {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase;
                 letter-spacing: 0.05em; margin-bottom: 0.25rem; }}
  .card-value {{ font-size: 1.5rem; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;
           margin-bottom: 1.5rem; font-size: 0.875rem; }}
  th {{ background: #f1f5f9; padding: 0.6rem 0.75rem; text-align: left;
        font-weight: 600; border-bottom: 1px solid #e2e8f0; }}
  td {{ padding: 0.55rem 0.75rem; border-bottom: 1px solid #f1f5f9; }}
  tr:last-child td {{ border-bottom: none; }}
  .badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px;
            font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }}
  .badge-completed {{ background: #dcfce7; color: #166534; }}
  .badge-failed {{ background: #fee2e2; color: #991b1b; }}
  .badge-error {{ background: #fef3c7; color: #92400e; }}
  footer {{ color: #94a3b8; font-size: 0.75rem; margin-top: 2rem; }}
</style>
</head>
<body>
<h1>QA-AI Validation Report</h1>
<p class="meta">Generated {generated} &nbsp;·&nbsp; {len(runs)} target(s) validated</p>

<h2>Quality Metrics</h2>
<div class="cards">{cards_html}</div>

<h2>Validation Runs</h2>
<table>
  <thead><tr>
    <th>Target</th><th>Profile</th><th>Status</th>
    <th>Findings</th><th>Duration</th><th>Errors</th>
  </tr></thead>
  <tbody>{run_rows}</tbody>
</table>

<h2>False-Positive Review ({fp.candidate_count} candidates, {_pct(fp.candidate_rate)} rate)</h2>
<table>
  <thead><tr>
    <th>ID</th><th>Title</th><th>Severity</th><th>Reasons</th><th>Confidence</th>
  </tr></thead>
  <tbody>{fp_rows}</tbody>
</table>

<h2>Runtime Stability</h2>
<table>
  <thead><tr>
    <th>Run</th><th>Target</th><th>Status</th>
    <th>Phases Attempted</th><th>Phases Completed</th>
    <th>Verification Rate</th><th>Artifacts</th><th>Duration</th>
  </tr></thead>
  <tbody>
  {"".join(
    f"<tr><td>{r.run_id}</td><td>{r.target_name}</td>"
    f"<td><span class='badge badge-{r.status}'>{r.status}</span></td>"
    f"<td>{r.phases_attempted}</td><td>{r.phases_completed}</td>"
    f"<td>{_pct(r.verification_rate)}</td>"
    f"<td>{r.artifact_count}</td><td>{r.duration_seconds:.1f}s</td></tr>"
    for r in stability.per_run
  ) or "<tr><td colspan='8'>No runs.</td></tr>"}
  </tbody>
</table>

<footer>QA-AI Validation Harness &mdash; {generated}</footer>
</body>
</html>"""


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
