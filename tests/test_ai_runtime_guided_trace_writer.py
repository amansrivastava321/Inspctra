"""Tests for GuidedTraceWriter — writes markdown and JSON trace."""
import json
import tempfile
from pathlib import Path

import pytest

from qa_ai.interactive_runtime.ai_runtime.guided_trace_writer import GuidedTraceWriter
from qa_ai.interactive_runtime.schemas import AIVerdict, GuidedStep


def _step(n: int = 1, verdict: AIVerdict = AIVerdict.PASS) -> GuidedStep:
    return GuidedStep(
        step_number=n,
        step_id=f"step-{n:03d}",
        screen_title="Dashboard",
        plan=f"Click action {n}",
        why="Test AI feature",
        action_taken=f"clicked button {n}",
        evidence_checked=["log check"],
        evidence_found=["log matched"],
        log_matches=["[AI_RESPONSE] 200"],
        screenshot_after=f"artifacts/step_{n:03d}.png",
        final_verdict=verdict,
        confidence_pct=85.0,
    )


class TestTraceWriter:
    def test_writes_markdown_file(self, tmp_path):
        writer = GuidedTraceWriter(str(tmp_path), write_markdown=True, write_json=False)
        writer.start("TestApp", "test objective", "sess-001")
        writer.add_step(_step(1))
        md = (tmp_path / "live_interactive_trace.md").read_text(encoding="utf-8")
        assert "TestApp" in md
        assert "Step 001" in md

    def test_writes_json_file(self, tmp_path):
        writer = GuidedTraceWriter(str(tmp_path), write_markdown=False, write_json=True)
        writer.start("TestApp", "test objective", "sess-001")
        writer.add_step(_step(1))
        data = json.loads((tmp_path / "live_interactive_trace.json").read_text())
        assert data["app_name"] == "TestApp"
        assert len(data["steps"]) == 1

    def test_multiple_steps(self, tmp_path):
        writer = GuidedTraceWriter(str(tmp_path))
        writer.start("App", "obj", "s1")
        writer.add_step(_step(1))
        writer.add_step(_step(2, AIVerdict.FAIL))
        writer.add_step(_step(3, AIVerdict.UNCLEAR))
        data = json.loads((tmp_path / "live_interactive_trace.json").read_text())
        assert len(data["steps"]) == 3

    def test_includes_verdict_in_markdown(self, tmp_path):
        writer = GuidedTraceWriter(str(tmp_path))
        writer.start("App", "obj")
        writer.add_step(_step(1, AIVerdict.PASS))
        md = (tmp_path / "live_interactive_trace.md").read_text(encoding="utf-8")
        assert "PASS" in md

    def test_includes_screenshots_in_markdown(self, tmp_path):
        writer = GuidedTraceWriter(str(tmp_path))
        writer.start("App", "obj")
        writer.add_step(_step(1))
        md = (tmp_path / "live_interactive_trace.md").read_text(encoding="utf-8")
        assert "step_001.png" in md

    def test_includes_log_matches(self, tmp_path):
        writer = GuidedTraceWriter(str(tmp_path))
        writer.start("App", "obj")
        writer.add_step(_step(1))
        md = (tmp_path / "live_interactive_trace.md").read_text(encoding="utf-8")
        assert "AI_RESPONSE" in md

    def test_finish_writes_summary(self, tmp_path):
        writer = GuidedTraceWriter(str(tmp_path))
        writer.start("App", "obj")
        writer.add_step(_step(1, AIVerdict.PASS))
        writer.add_step(_step(2, AIVerdict.FAIL))
        writer.finish(total_pass=1, total_fail=1, total_unclear=0)
        md = (tmp_path / "live_interactive_trace.md").read_text(encoding="utf-8")
        assert "Summary" in md
