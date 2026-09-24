"""
task_profiles.py - Task-based routing profiles for interactive runtime AI calls.

Maps each AI task to a specific local Ollama model with fallback.
Optimised for Mac M4 Pro 16 GB — one model at a time, sequential.

Default routing: all tasks → local Ollama only.
Cloud providers: disabled by default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional


# ── Task taxonomy ──────────────────────────────────────────────────────────────

class ModelTask(str, Enum):
    VISION_SCREEN_ANALYSIS = "vision_screen_analysis"
    UI_ACTION_PLANNING     = "ui_action_planning"
    AI_ORACLE              = "ai_oracle"
    ROOT_CAUSE_ANALYSIS    = "root_cause_analysis"
    STEP_NARRATION         = "step_narration"
    REPORT_SUMMARY         = "report_summary"
    CODE_LOG_ANALYSIS      = "code_log_analysis"
    EMBEDDINGS             = "embeddings"
    FALLBACK_CHAT          = "fallback_chat"


# ── Per-task route ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TaskRoute:
    task: ModelTask
    provider: str          # "ollama" | "openai_compatible" | "openrouter"
    model: str
    fallback_models: List[str]
    temperature: float
    timeout_seconds: int
    max_tokens: int
    estimated_memory_gb: float
    supports_vision: bool = False
    local_only: bool = True
    requires_approval: bool = False


# ── Resource profile ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResourceProfile:
    name: str
    max_parallel_model_calls: int
    prefer_sequential_calls: bool
    unload_between_heavy_tasks: bool
    heavy_models: FrozenSet[str]
    medium_models: FrozenSet[str]
    light_models: FrozenSet[str]
    total_ram_gb: float

    def tier(self, model: str) -> str:
        if model in self.heavy_models:
            return "heavy"
        if model in self.medium_models:
            return "medium"
        if model in self.light_models:
            return "light"
        return "unknown"

    def estimated_memory_gb(self, model: str) -> float:
        return _MODEL_MEMORY_GB.get(model, 4.0)


# ── Memory estimates (GB VRAM/RAM for Ollama on Apple Silicon) ─────────────────

_MODEL_MEMORY_GB: Dict[str, float] = {
    "qwen2.5vl:7b":          6.0,
    "qwen3.5:9b":             6.6,
    "gemma4:e4b":             9.6,
    "deepseek-r1:7b":         4.7,
    "dolphincoder:7b":        4.2,
    "dolphin-mistral:7b":     4.1,
    "phi4-mini:latest":       2.5,
    "bge-m3:latest":          1.2,
}


# ── Mac M4 Pro 16 GB resource profile ─────────────────────────────────────────

MAC_M4_16GB = ResourceProfile(
    name="mac_m4_16gb",
    max_parallel_model_calls=1,
    prefer_sequential_calls=True,
    unload_between_heavy_tasks=True,
    heavy_models=frozenset({
        "gemma4:e4b",
        "qwen3.5:9b",
        "qwen2.5vl:7b",
    }),
    medium_models=frozenset({
        "deepseek-r1:7b",
        "dolphincoder:7b",
        "dolphin-mistral:7b",
    }),
    light_models=frozenset({
        "phi4-mini:latest",
        "bge-m3:latest",
    }),
    total_ram_gb=16.0,
)


# ── Default task routing (local Ollama only) ───────────────────────────────────

def get_default_task_routes() -> Dict[ModelTask, TaskRoute]:
    """
    Default routes for all AI tasks.

    All routes point to local Ollama only.
    Cloud disabled by default.
    """
    return {
        ModelTask.VISION_SCREEN_ANALYSIS: TaskRoute(
            task=ModelTask.VISION_SCREEN_ANALYSIS,
            provider="ollama",
            model="qwen2.5vl:7b",
            fallback_models=[],
            temperature=0.1,
            timeout_seconds=60,
            max_tokens=1024,
            estimated_memory_gb=6.0,
            supports_vision=True,
            local_only=True,
        ),
        ModelTask.UI_ACTION_PLANNING: TaskRoute(
            task=ModelTask.UI_ACTION_PLANNING,
            provider="ollama",
            model="qwen3.5:9b",
            fallback_models=["phi4-mini:latest"],
            temperature=0.15,
            timeout_seconds=90,
            max_tokens=2048,
            estimated_memory_gb=6.6,
            local_only=True,
        ),
        ModelTask.AI_ORACLE: TaskRoute(
            task=ModelTask.AI_ORACLE,
            provider="ollama",
            model="deepseek-r1:7b",
            fallback_models=["qwen3.5:9b"],
            temperature=0.1,
            timeout_seconds=90,
            max_tokens=1024,
            estimated_memory_gb=4.7,
            local_only=True,
        ),
        ModelTask.ROOT_CAUSE_ANALYSIS: TaskRoute(
            task=ModelTask.ROOT_CAUSE_ANALYSIS,
            provider="ollama",
            model="deepseek-r1:7b",
            fallback_models=["dolphincoder:7b"],
            temperature=0.1,
            timeout_seconds=120,
            max_tokens=2048,
            estimated_memory_gb=4.7,
            local_only=True,
        ),
        ModelTask.STEP_NARRATION: TaskRoute(
            task=ModelTask.STEP_NARRATION,
            provider="ollama",
            model="phi4-mini:latest",
            fallback_models=["dolphin-mistral:7b"],
            temperature=0.2,
            timeout_seconds=30,
            max_tokens=512,
            estimated_memory_gb=2.5,
            local_only=True,
        ),
        ModelTask.REPORT_SUMMARY: TaskRoute(
            task=ModelTask.REPORT_SUMMARY,
            provider="ollama",
            model="gemma4:e4b",
            fallback_models=["qwen3.5:9b"],
            temperature=0.2,
            timeout_seconds=120,
            max_tokens=4096,
            estimated_memory_gb=9.6,
            local_only=True,
        ),
        ModelTask.CODE_LOG_ANALYSIS: TaskRoute(
            task=ModelTask.CODE_LOG_ANALYSIS,
            provider="ollama",
            model="dolphincoder:7b",
            fallback_models=["deepseek-r1:7b"],
            temperature=0.1,
            timeout_seconds=90,
            max_tokens=2048,
            estimated_memory_gb=4.2,
            local_only=True,
        ),
        ModelTask.EMBEDDINGS: TaskRoute(
            task=ModelTask.EMBEDDINGS,
            provider="ollama",
            model="bge-m3:latest",
            fallback_models=[],
            temperature=0.0,
            timeout_seconds=30,
            max_tokens=0,
            estimated_memory_gb=1.2,
            local_only=True,
        ),
        ModelTask.FALLBACK_CHAT: TaskRoute(
            task=ModelTask.FALLBACK_CHAT,
            provider="ollama",
            model="dolphin-mistral:7b",
            fallback_models=["phi4-mini:latest"],
            temperature=0.2,
            timeout_seconds=60,
            max_tokens=1024,
            estimated_memory_gb=4.1,
            local_only=True,
        ),
    }


# ── Required models for full route coverage ────────────────────────────────────

REQUIRED_LOCAL_MODELS: FrozenSet[str] = frozenset({
    "qwen2.5vl:7b",
    "qwen3.5:9b",
    "deepseek-r1:7b",
    "phi4-mini:latest",
    "gemma4:e4b",
    "dolphincoder:7b",
    "dolphin-mistral:7b",
    "bge-m3:latest",
})
