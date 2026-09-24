"""
tests/test_validation_report_builder.py - Integration tests for ValidationReportBuilder.

Tests the full pipeline: ValidationRun objects → 5 report files written to disk.
Uses synthetic ValidationRun objects (no real AuditCommand call needed).
"""
import json
import pytest
from pathlib import Path

from qa_ai.validation.harness import ValidationRun, ValidationTarget
from qa_ai.validation.report_builder import ValidationReportBuilder


def _make_run(
    name="myapp",
    status="completed",
    finding_count=3,
    duration=7.5,
    errors=None,
    findings_data=None,
    tmp_path: Path = None,
) -> ValidationRun:
    target = ValidationTarget(name=name, path=f"/tmp/{name}", profile="api")
    run_dir = tmp_path / f"val_{name}" if tmp_path else Path(f"/tmp/val_{name}")
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write a synthetic findings artifact so the builder can collect them
    if findings_data is None:
        findings_data = [
            {
                "id": f"F-{i:04d}",
                "title": f"Finding {i} in {name}: unexpected behavior",
                "severity": "high",
                "category": "security",
                "evidence": [{"evidence_type": "request", "filename": f"req_{i}.json"}],
                "steps_to_reproduce": [f"Step {i}.1", f"Step {i}.2"],
                "expected_behavior": f"Should return 403 for unauthenticated call {i}",
                "actual_behavior": f"Returns 200 with sensitive data on call {i}",
                "tags": ["auth", "security"],
                "api_endpoint": f"/api/resource/{i}",
                "test_case_id": f"TC-{i:03d}",
            }
            for i in range(1, finding_count + 1)
        ]
    (run_dir / "findings.json").write_text(
        json.dumps({"findings": findings_data}, indent=2), encoding="utf-8"
    )

    return ValidationRun(
        run_id=f"val_{name}",
        target=target,
        started_at="2026-05-16T00:00:00Z",
        completed_at="2026-05-16T00:00:07Z",
        duration_seconds=duration,
        output_dir=str(run_dir),
        status=status,
        phases_executed=["discovery", "code_quality", "security_analysis"],
        phases_attempted=3,
        phases_completed=3,
        finding_count=finding_count,
        evidence_count=finding_count,
        errors=errors or [],
        artifacts=[f"findings.json"],
        raw_summary={"status": status},
    )


class TestValidationReportBuilder:
    def test_builds_all_five_files(self, tmp_path):
        runs = [_make_run(tmp_path=tmp_path)]
        builder = ValidationReportBuilder(output_dir=tmp_path / "reports")
        session_dir = builder.build(runs, session_id="test_session")

        assert (session_dir / "validation_summary.json").exists()
        assert (session_dir / "validation_findings_quality.json").exists()
        assert (session_dir / "validation_false_positive_review.json").exists()
        assert (session_dir / "validation_runtime_stability.json").exists()
        assert (session_dir / "validation_report.html").exists()

    def test_summary_json_structure(self, tmp_path):
        runs = [_make_run(name="alpha", finding_count=5, tmp_path=tmp_path)]
        builder = ValidationReportBuilder(output_dir=tmp_path / "out")
        session_dir = builder.build(runs, session_id="s1")

        summary = json.loads((session_dir / "validation_summary.json").read_text())
        assert summary["total_runs"] == 1
        assert summary["total_findings"] == 5
        assert "mean_completeness_score" in summary
        assert "crash_free_rate" in summary
        assert "runtime_verification_rate" in summary
        assert "false_positive_candidates" in summary
        assert isinstance(summary["runs"], list)

    def test_findings_quality_json_structure(self, tmp_path):
        runs = [_make_run(name="beta", finding_count=3, tmp_path=tmp_path)]
        builder = ValidationReportBuilder(output_dir=tmp_path / "out")
        session_dir = builder.build(runs, session_id="s2")

        quality = json.loads((session_dir / "validation_findings_quality.json").read_text())
        assert quality["total_findings"] == 3
        assert "findings_with_evidence_pct" in quality
        assert "remediation_usefulness_score" in quality
        assert "per_finding" in quality
        assert len(quality["per_finding"]) == 3

    def test_false_positive_review_json_structure(self, tmp_path):
        # Findings with no evidence → should have FP candidates
        bad_findings = [
            {"id": "F-0001", "title": "test failed: test_login",
             "severity": "critical", "evidence": [],
             "steps_to_reproduce": [], "api_endpoint": "", "test_case_id": "",
             "tags": [], "expected_behavior": "ok", "actual_behavior": "ok"},
        ]
        runs = [_make_run(name="gamma", findings_data=bad_findings, tmp_path=tmp_path)]
        builder = ValidationReportBuilder(output_dir=tmp_path / "out")
        session_dir = builder.build(runs, session_id="s3")

        fp_report = json.loads(
            (session_dir / "validation_false_positive_review.json").read_text()
        )
        assert fp_report["total_findings"] == 1
        assert fp_report["candidate_count"] >= 1
        assert len(fp_report["candidates"]) >= 1
        c = fp_report["candidates"][0]
        assert "reasons" in c
        assert "confidence" in c

    def test_runtime_stability_json_structure(self, tmp_path):
        runs = [_make_run(name="delta", status="completed", tmp_path=tmp_path)]
        builder = ValidationReportBuilder(output_dir=tmp_path / "out")
        session_dir = builder.build(runs, session_id="s4")

        stability = json.loads(
            (session_dir / "validation_runtime_stability.json").read_text()
        )
        assert stability["total_runs"] == 1
        assert stability["crash_free_rate"] == 1.0
        assert "mean_verification_rate" in stability
        assert len(stability["per_run"]) == 1

    def test_html_report_contains_key_sections(self, tmp_path):
        runs = [_make_run(name="epsilon", finding_count=2, tmp_path=tmp_path)]
        builder = ValidationReportBuilder(output_dir=tmp_path / "out")
        session_dir = builder.build(runs, session_id="s5")

        html = (session_dir / "validation_report.html").read_text(encoding="utf-8")
        assert "QA-AI Validation Report" in html
        assert "Quality Metrics" in html
        assert "Validation Runs" in html
        assert "False-Positive Review" in html
        assert "Runtime Stability" in html
        assert "epsilon" in html

    def test_multiple_runs_aggregated(self, tmp_path):
        runs = [
            _make_run(name="app1", finding_count=2, tmp_path=tmp_path),
            _make_run(name="app2", finding_count=5, tmp_path=tmp_path),
        ]
        builder = ValidationReportBuilder(output_dir=tmp_path / "out")
        session_dir = builder.build(runs, session_id="multi")

        summary = json.loads((session_dir / "validation_summary.json").read_text())
        assert summary["total_runs"] == 2
        assert summary["total_findings"] == 7

    def test_empty_findings_handled_gracefully(self, tmp_path):
        runs = [_make_run(name="empty", finding_count=0, findings_data=[], tmp_path=tmp_path)]
        builder = ValidationReportBuilder(output_dir=tmp_path / "out")
        session_dir = builder.build(runs, session_id="empty_run")

        summary = json.loads((session_dir / "validation_summary.json").read_text())
        assert summary["total_findings"] == 0
        assert summary["mean_completeness_score"] == 0.0

    def test_failed_run_tracked_in_stability(self, tmp_path):
        runs = [
            _make_run(name="ok_run", status="completed", tmp_path=tmp_path),
            _make_run(name="bad_run", status="error", errors=["crash"], tmp_path=tmp_path),
        ]
        builder = ValidationReportBuilder(output_dir=tmp_path / "out")
        session_dir = builder.build(runs, session_id="mixed")

        stability = json.loads(
            (session_dir / "validation_runtime_stability.json").read_text()
        )
        assert stability["total_runs"] == 2
        assert stability["crash_free_rate"] == 0.5
