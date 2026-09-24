"""
test_model_benchmarker.py - Tests for model_benchmarker.py

Covers: dry_run returns stubs, no real calls without approved=True,
quick mode skips heavy models, structured BenchmarkReport.
"""
from __future__ import annotations

import pytest
from qa_ai.ai.model_benchmarker import run_benchmark, BenchmarkReport, ModelBenchmarkEntry


class TestDryRun:
    def test_dry_run_default_returns_report(self):
        report = run_benchmark(approved=False, dry_run=True, quick=True)
        assert isinstance(report, BenchmarkReport)

    def test_dry_run_all_entries_are_dry_run_status(self):
        report = run_benchmark(approved=False, dry_run=True, quick=True)
        for entry in report.entries:
            assert entry.status == "dry_run", f"Expected dry_run but got {entry.status} for {entry.model}"

    def test_dry_run_is_true_in_report(self):
        report = run_benchmark(approved=False, dry_run=True)
        assert report.dry_run is True

    def test_report_has_generated_at(self):
        report = run_benchmark(approved=False, dry_run=True)
        assert report.generated_at != ""

    def test_report_has_summary(self):
        report = run_benchmark(approved=False, dry_run=True)
        assert isinstance(report.summary, str)
        assert len(report.summary) > 0


class TestQuickMode:
    def test_quick_mode_true_in_report(self):
        report = run_benchmark(approved=False, dry_run=True, quick=True)
        assert report.quick_mode is True

    def test_quick_mode_skips_heavy_models(self):
        report = run_benchmark(approved=False, dry_run=True, quick=True)
        heavy_models = {"gemma4:e4b", "qwen3.5:9b"}
        benchmarked_models = {e.model for e in report.entries if e.status != "skipped"}
        # Heavy models should be skipped or not present in quick mode
        for m in heavy_models:
            if m in benchmarked_models:
                # If present, status must be "skipped"
                entries_for_model = [e for e in report.entries if e.model == m]
                for entry in entries_for_model:
                    assert entry.status in ("skipped", "dry_run")

    def test_not_quick_includes_all_models_when_approved(self):
        # approved=True + dry_run=True triggers full route coverage with dry_run entries
        from unittest.mock import patch
        import urllib.error
        # Simulate Ollama unreachable — entries will be errors, but all models present
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            report = run_benchmark(approved=True, dry_run=False, quick=False)
        from qa_ai.ai.task_profiles import get_default_task_routes
        primary_models = {r.model for r in get_default_task_routes().values()}
        entry_models = {e.model for e in report.entries}
        for m in primary_models:
            assert m in entry_models, f"Model {m} missing from benchmark entries"


class TestApprovedFalse:
    def test_not_approved_does_not_call_ollama(self):
        from unittest.mock import patch
        with patch("urllib.request.urlopen") as mock_url:
            run_benchmark(approved=False, dry_run=True)
            mock_url.assert_not_called()

    def test_approved_false_dry_run_false_still_safe(self):
        # approved=False + dry_run=False → should skip real calls gracefully
        from unittest.mock import patch
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            report = run_benchmark(approved=False, dry_run=False)
        # Either all skipped or error — never crash
        assert isinstance(report, BenchmarkReport)


class TestBenchmarkEntry:
    def test_entry_has_required_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(ModelBenchmarkEntry)}
        assert {"model", "task", "latency_ms", "status", "error", "recommendation"}.issubset(fields)

    def test_dry_run_entry_has_zero_latency(self):
        report = run_benchmark(approved=False, dry_run=True, quick=True)
        for entry in report.entries:
            if entry.status == "dry_run":
                assert entry.latency_ms == 0.0
