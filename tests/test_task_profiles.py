"""
test_task_profiles.py - Tests for task_profiles.py

Covers: ModelTask enum, TaskRoute, ResourceProfile, MAC_M4_16GB,
get_default_task_routes(), REQUIRED_LOCAL_MODELS.
"""
from __future__ import annotations

import pytest
from qa_ai.ai.task_profiles import (
    MAC_M4_16GB,
    ModelTask,
    REQUIRED_LOCAL_MODELS,
    TaskRoute,
    get_default_task_routes,
    _MODEL_MEMORY_GB,
)


class TestModelTask:
    def test_all_required_tasks_exist(self):
        expected = {
            "vision_screen_analysis",
            "ui_action_planning",
            "ai_oracle",
            "root_cause_analysis",
            "step_narration",
            "report_summary",
            "code_log_analysis",
            "embeddings",
            "fallback_chat",
        }
        actual = {t.value for t in ModelTask}
        assert expected == actual

    def test_task_values_are_strings(self):
        for task in ModelTask:
            assert isinstance(task.value, str)
            assert len(task.value) > 0

    def test_task_is_str_enum(self):
        assert ModelTask.AI_ORACLE == "ai_oracle"


class TestDefaultTaskRoutes:
    def setup_method(self):
        self.routes = get_default_task_routes()

    def test_all_tasks_have_routes(self):
        for task in ModelTask:
            assert task in self.routes, f"No route for task: {task}"

    def test_vision_task_uses_qwen25vl(self):
        r = self.routes[ModelTask.VISION_SCREEN_ANALYSIS]
        assert r.model == "qwen2.5vl:7b"
        assert r.supports_vision is True

    def test_ui_planning_uses_qwen35(self):
        r = self.routes[ModelTask.UI_ACTION_PLANNING]
        assert r.model == "qwen3.5:9b"
        assert "phi4-mini:latest" in r.fallback_models

    def test_ai_oracle_uses_deepseek(self):
        r = self.routes[ModelTask.AI_ORACLE]
        assert r.model == "deepseek-r1:7b"
        assert "qwen3.5:9b" in r.fallback_models

    def test_rca_uses_deepseek(self):
        r = self.routes[ModelTask.ROOT_CAUSE_ANALYSIS]
        assert r.model == "deepseek-r1:7b"
        assert "dolphincoder:7b" in r.fallback_models

    def test_step_narration_uses_phi4mini(self):
        r = self.routes[ModelTask.STEP_NARRATION]
        assert r.model == "phi4-mini:latest"
        assert "dolphin-mistral:7b" in r.fallback_models

    def test_report_summary_uses_gemma4(self):
        r = self.routes[ModelTask.REPORT_SUMMARY]
        assert r.model == "gemma4:e4b"
        assert "qwen3.5:9b" in r.fallback_models

    def test_code_log_uses_dolphincoder(self):
        r = self.routes[ModelTask.CODE_LOG_ANALYSIS]
        assert r.model == "dolphincoder:7b"
        assert "deepseek-r1:7b" in r.fallback_models

    def test_embeddings_uses_bge(self):
        r = self.routes[ModelTask.EMBEDDINGS]
        assert r.model == "bge-m3:latest"

    def test_fallback_chat_uses_dolphin_mistral(self):
        r = self.routes[ModelTask.FALLBACK_CHAT]
        assert r.model == "dolphin-mistral:7b"

    def test_all_routes_are_local_only(self):
        for task, route in self.routes.items():
            assert route.local_only is True, f"Route for {task} must be local_only=True"

    def test_all_routes_have_positive_timeout(self):
        for task, route in self.routes.items():
            assert route.timeout_seconds > 0, f"Route {task} has zero timeout"

    def test_all_routes_have_positive_memory_estimate(self):
        for task, route in self.routes.items():
            assert route.estimated_memory_gb > 0


class TestMacM4Profile:
    def test_max_parallel_calls_is_1(self):
        assert MAC_M4_16GB.max_parallel_model_calls == 1

    def test_prefer_sequential(self):
        assert MAC_M4_16GB.prefer_sequential_calls is True

    def test_heavy_models_identified(self):
        assert "gemma4:e4b" in MAC_M4_16GB.heavy_models
        assert "qwen3.5:9b" in MAC_M4_16GB.heavy_models
        assert "qwen2.5vl:7b" in MAC_M4_16GB.heavy_models

    def test_light_models_identified(self):
        assert "phi4-mini:latest" in MAC_M4_16GB.light_models
        assert "bge-m3:latest" in MAC_M4_16GB.light_models

    def test_tier_heavy(self):
        assert MAC_M4_16GB.tier("gemma4:e4b") == "heavy"

    def test_tier_medium(self):
        assert MAC_M4_16GB.tier("deepseek-r1:7b") == "medium"

    def test_tier_light(self):
        assert MAC_M4_16GB.tier("phi4-mini:latest") == "light"

    def test_tier_unknown(self):
        assert MAC_M4_16GB.tier("unknown-model:3b") == "unknown"

    def test_estimated_memory_for_known_model(self):
        mem = MAC_M4_16GB.estimated_memory_gb("qwen2.5vl:7b")
        assert mem == 6.0

    def test_estimated_memory_for_unknown_model(self):
        # Unknown model falls back to 4.0 GB default
        mem = MAC_M4_16GB.estimated_memory_gb("no-such-model:latest")
        assert mem == 4.0

    def test_total_ram_16gb(self):
        assert MAC_M4_16GB.total_ram_gb == 16.0


class TestRequiredLocalModels:
    def test_all_required_models_listed(self):
        expected = {
            "qwen2.5vl:7b",
            "qwen3.5:9b",
            "deepseek-r1:7b",
            "phi4-mini:latest",
            "gemma4:e4b",
            "dolphincoder:7b",
            "dolphin-mistral:7b",
            "bge-m3:latest",
        }
        assert REQUIRED_LOCAL_MODELS == expected

    def test_required_models_match_routes(self):
        routes = get_default_task_routes()
        primary_models = {r.model for r in routes.values()}
        # Every primary model must be in REQUIRED_LOCAL_MODELS
        for m in primary_models:
            assert m in REQUIRED_LOCAL_MODELS, f"{m} used in route but not in REQUIRED_LOCAL_MODELS"
