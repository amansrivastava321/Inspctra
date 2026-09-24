"""
test_resource_manager.py - Tests for resource_manager.py

Covers: slot acquire/release, can_run, heavy model blocking,
lighter model routing, memory policy summary.
"""
from __future__ import annotations

import threading
import time
import pytest

from qa_ai.ai.resource_manager import ResourceManager, SlotState
from qa_ai.ai.task_profiles import MAC_M4_16GB, ModelTask, get_default_task_routes


@pytest.fixture
def rm():
    return ResourceManager(profile=MAC_M4_16GB)


class TestAcquireRelease:
    def test_acquire_when_empty_succeeds(self, rm):
        ok = rm.acquire_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        assert ok is True

    def test_can_run_false_while_slot_held(self, rm):
        rm.acquire_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        assert rm.can_run("phi4-mini:latest") is False

    def test_second_acquire_blocked(self, rm):
        rm.acquire_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        ok = rm.acquire_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
        assert ok is False

    def test_release_clears_slot(self, rm):
        rm.acquire_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        rm.release_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        assert rm.can_run("phi4-mini:latest") is True

    def test_can_run_after_release(self, rm):
        rm.acquire_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
        rm.release_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
        ok = rm.acquire_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        assert ok is True

    def test_release_mismatch_still_clears(self, rm):
        rm.acquire_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
        # Release with wrong task/model — should still clear
        rm.release_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        assert rm.can_run("phi4-mini:latest") is True

    def test_string_task_accepted(self, rm):
        ok = rm.acquire_model_slot("step_narration", "phi4-mini:latest")
        assert ok is True

    def test_slot_not_held_initially(self, rm):
        assert rm.can_run("any-model") is True


class TestHeavyModelPolicy:
    def test_heavy_cannot_run_when_medium_active(self, rm):
        rm.acquire_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
        # Heavy model should be blocked
        ok = rm.acquire_model_slot(ModelTask.REPORT_SUMMARY, "gemma4:e4b")
        assert ok is False

    def test_heavy_cannot_run_when_light_active(self, rm):
        rm.acquire_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        ok = rm.acquire_model_slot(ModelTask.VISION_SCREEN_ANALYSIS, "qwen2.5vl:7b")
        assert ok is False


class TestLighterModelRouting:
    def test_route_to_lighter_when_slot_busy(self, rm):
        rm.acquire_model_slot(ModelTask.STEP_NARRATION, "phi4-mini:latest")
        lighter = rm.route_to_lighter_model_if_needed(ModelTask.UI_ACTION_PLANNING)
        # qwen3.5:9b is heavy; fallback is phi4-mini:latest
        assert lighter == "phi4-mini:latest"

    def test_no_reroute_when_slot_free(self, rm):
        # Slot is free → no reroute needed
        lighter = rm.route_to_lighter_model_if_needed(ModelTask.UI_ACTION_PLANNING)
        assert lighter is None

    def test_no_reroute_for_light_task(self, rm):
        rm.acquire_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
        # step_narration primary is phi4-mini (light) — no reroute needed
        lighter = rm.route_to_lighter_model_if_needed(ModelTask.STEP_NARRATION)
        assert lighter is None


class TestMemoryPolicySummary:
    def test_summary_has_required_keys(self, rm):
        summary = rm.memory_policy_summary()
        assert "profile" in summary
        assert "max_parallel_model_calls" in summary
        assert "prefer_sequential_calls" in summary
        assert "slot_occupied" in summary
        assert "heavy_models" in summary

    def test_summary_max_parallel_is_1(self, rm):
        assert rm.memory_policy_summary()["max_parallel_model_calls"] == 1

    def test_summary_slot_occupied_true_when_active(self, rm):
        rm.acquire_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
        assert rm.memory_policy_summary()["slot_occupied"] is True

    def test_summary_slot_occupied_false_when_free(self, rm):
        assert rm.memory_policy_summary()["slot_occupied"] is False


class TestEstimatedMemory:
    def test_known_model_returns_correct_gb(self, rm):
        assert rm.estimated_memory_gb("gemma4:e4b") == 9.6

    def test_unknown_model_returns_default(self, rm):
        assert rm.estimated_memory_gb("not-a-model:3b") == 4.0


class TestShouldDefer:
    def test_should_defer_true_when_active(self, rm):
        rm.acquire_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
        assert rm.should_defer("phi4-mini:latest") is True

    def test_should_defer_false_when_free(self, rm):
        assert rm.should_defer("phi4-mini:latest") is False


class TestThreadSafety:
    def test_only_one_acquires_under_contention(self):
        rm = ResourceManager(profile=MAC_M4_16GB)
        results = []

        def try_acquire():
            ok = rm.acquire_model_slot(ModelTask.AI_ORACLE, "deepseek-r1:7b")
            results.append(ok)

        threads = [threading.Thread(target=try_acquire) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one should have succeeded
        assert results.count(True) == 1
        assert results.count(False) == 4
