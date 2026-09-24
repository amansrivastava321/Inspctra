"""Tests for qa_ai.interactive_runtime.function_coverage_tracker.FunctionCoverageTracker."""
import json
from pathlib import Path

import pytest

from qa_ai.interactive_runtime.function_coverage_tracker import FunctionCoverageTracker
from qa_ai.interactive_runtime.schemas import (
    FunctionCoverageItem,
    FunctionStatus,
    VerificationStatus,
)


def _make_item(label: str, screen: str = "LoginScreen", item_id: str = None) -> FunctionCoverageItem:
    return FunctionCoverageItem(
        item_id=item_id or label,
        screen=screen,
        element_label=label,
        element_type="button",
    )


class TestFunctionCoverageTrackerDiscover:
    def test_discover_registers_item(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Login Button")
        tracker.discover(item)
        assert tracker.get("Login Button") is not None

    def test_discovered_item_has_discovered_status(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Login Button")
        tracker.discover(item)
        assert tracker.get("Login Button").status == FunctionStatus.DISCOVERED

    def test_discover_many(self):
        tracker = FunctionCoverageTracker()
        items = [_make_item(f"btn_{i}") for i in range(5)]
        tracker.discover_many(items)
        assert len(tracker.all_items()) == 5

    def test_find_by_label(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Submit", screen="Form")
        tracker.discover(item)
        found = tracker.find_by_label("Form", "Submit")
        assert found is not None
        assert found.element_label == "Submit"

    def test_find_by_label_wrong_screen_returns_none(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Submit", screen="Form")
        tracker.discover(item)
        assert tracker.find_by_label("OtherScreen", "Submit") is None


class TestFunctionCoverageTrackerStatusLifecycle:
    def test_mark_attempted_transitions_status(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Login")
        tracker.discover(item)
        tracker.mark_attempted("Login", action="click")
        assert tracker.get("Login").status == FunctionStatus.ATTEMPTED

    def test_mark_by_verification_passed(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Login")
        tracker.discover(item)
        tracker.mark_attempted("Login")
        tracker.mark_by_verification("Login", VerificationStatus.PASSED)
        assert tracker.get("Login").status == FunctionStatus.PASSED

    def test_mark_by_verification_failed(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Submit")
        tracker.discover(item)
        tracker.mark_attempted("Submit")
        tracker.mark_by_verification("Submit", VerificationStatus.FAILED)
        assert tracker.get("Submit").status == FunctionStatus.FAILED

    def test_mark_by_verification_inconclusive(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Generate")
        tracker.discover(item)
        tracker.mark_attempted("Generate")
        tracker.mark_by_verification("Generate", VerificationStatus.INCONCLUSIVE)
        assert tracker.get("Generate").status == FunctionStatus.INCONCLUSIVE

    def test_mark_by_verification_blocked(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Delete")
        tracker.discover(item)
        tracker.mark_by_verification("Delete", VerificationStatus.BLOCKED)
        assert tracker.get("Delete").status == FunctionStatus.BLOCKED

    def test_mark_blocked(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Dangerous")
        tracker.discover(item)
        tracker.mark_blocked("Dangerous", reason="permission denied")
        result = tracker.get("Dangerous")
        assert result.status == FunctionStatus.BLOCKED
        assert "permission denied" in result.notes

    def test_mark_skipped(self):
        tracker = FunctionCoverageTracker()
        item = _make_item("Export")
        tracker.discover(item)
        tracker.mark_skipped("Export", reason="out of scope")
        result = tracker.get("Export")
        assert result.status == FunctionStatus.SKIPPED
        assert "out of scope" in result.notes

    def test_mark_unknown_item_does_not_raise(self):
        tracker = FunctionCoverageTracker()
        tracker.mark_attempted("nonexistent")  # should not raise
        tracker.mark_blocked("nonexistent")
        tracker.mark_skipped("nonexistent")


class TestFunctionCoverageTrackerStats:
    def test_summary_counts_by_status(self):
        tracker = FunctionCoverageTracker()
        tracker.discover(_make_item("a"))
        tracker.discover(_make_item("b"))
        tracker.discover(_make_item("c"))
        tracker.mark_by_verification("a", VerificationStatus.PASSED)
        tracker.mark_by_verification("b", VerificationStatus.FAILED)
        summary = tracker.summary()
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["discovered"] == 1

    def test_coverage_pct_zero_when_all_discovered(self):
        tracker = FunctionCoverageTracker()
        for i in range(4):
            tracker.discover(_make_item(f"btn_{i}"))
        assert tracker.coverage_pct == 0.0

    def test_coverage_pct_100_when_all_tested(self):
        tracker = FunctionCoverageTracker()
        for i in range(3):
            item = _make_item(f"btn_{i}")
            tracker.discover(item)
            tracker.mark_attempted(f"btn_{i}")
        assert tracker.coverage_pct == 100.0

    def test_coverage_pct_partial(self):
        tracker = FunctionCoverageTracker()
        tracker.discover(_make_item("a"))
        tracker.discover(_make_item("b"))
        tracker.mark_attempted("a")
        pct = tracker.coverage_pct
        assert 40 < pct < 60  # roughly 50%

    def test_coverage_pct_zero_for_empty_tracker(self):
        tracker = FunctionCoverageTracker()
        assert tracker.coverage_pct == 0.0


class TestFunctionCoverageTrackerPersistence:
    def test_save_creates_json_file(self, tmp_path):
        tracker = FunctionCoverageTracker(output_dir=str(tmp_path))
        tracker.discover(_make_item("Login"))
        path = tracker.save()
        assert path.exists()

    def test_saved_json_has_correct_structure(self, tmp_path):
        tracker = FunctionCoverageTracker(output_dir=str(tmp_path))
        tracker.discover(_make_item("Login"))
        tracker.mark_by_verification("Login", VerificationStatus.PASSED)
        path = tracker.save()
        data = json.loads(path.read_text())
        assert "items" in data
        assert "summary" in data
        assert "coverage_pct" in data
        assert data["total"] == 1

    def test_saved_json_items_include_status(self, tmp_path):
        tracker = FunctionCoverageTracker(output_dir=str(tmp_path))
        tracker.discover(_make_item("Login"))
        tracker.mark_by_verification("Login", VerificationStatus.PASSED)
        path = tracker.save()
        data = json.loads(path.read_text())
        item = data["items"][0]
        assert item["status"] == "passed"

    def test_save_filename_is_correct(self, tmp_path):
        tracker = FunctionCoverageTracker(output_dir=str(tmp_path))
        path = tracker.save()
        assert path.name == "interactive_function_coverage.json"
