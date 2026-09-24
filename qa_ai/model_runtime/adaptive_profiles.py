"""
adaptive_profiles.py - Hardware-aware resource profiles for model routing.

5 standard profiles:
  low_ram_8gb      ≤10GB  — light models only, vision off, deterministic preferred
  mac_m4_16gb      12-24GB — sequential, heavy models allowed one at a time
  pro_32gb         24-48GB — 2 parallel calls, heavier models OK
  workstation_64gb ≥48GB  — 3 parallel calls, large models allowed
  remote_gpu       CUDA+  — configurable parallelism, prefer remote for heavy tasks

The mac_m4_16gb profile preserves existing behavior exactly.
No app-specific logic. No hardcoded model assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AdaptiveResourceProfile:
    profile_id: str
    name: str
    description: str
    min_ram_gb: float
    max_ram_gb: float        # 0 = no upper limit
    max_parallel_model_calls: int
    max_model_memory_gb: float
    avoid_heavy_models: bool
    allow_heavy_models: bool
    allow_parallel_routing: bool
    unload_between_heavy_tasks: bool
    prefer_local: bool
    prefer_deterministic_when_low_resource: bool
    vision_enabled_by_default: bool
    recommended_context_tokens: int
    # task_id → preferred_model_tier  ("light" | "medium" | "heavy" | "any")
    task_preferences: Dict[str, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


# ── Profile 1: Low RAM (≤10 GB) ───────────────────────────────────────────────

LOW_RAM_8GB = AdaptiveResourceProfile(
    profile_id="low_ram_8gb",
    name="Low RAM (≤10 GB)",
    description=(
        "Conservative profile for machines with 8–10 GB RAM. "
        "Only light models allowed. Vision AI disabled by default. "
        "Deterministic verification preferred over LLM-based verdicts."
    ),
    min_ram_gb=0.0,
    max_ram_gb=10.0,
    max_parallel_model_calls=1,
    max_model_memory_gb=3.5,
    avoid_heavy_models=True,
    allow_heavy_models=False,
    allow_parallel_routing=False,
    unload_between_heavy_tasks=True,
    prefer_local=True,
    prefer_deterministic_when_low_resource=True,
    vision_enabled_by_default=False,
    recommended_context_tokens=2048,
    task_preferences={
        "vision_screen_analysis": "disabled",
        "ui_action_planning":     "light",
        "ai_oracle":              "light",
        "root_cause_analysis":    "light",
        "step_narration":         "light",
        "report_summary":         "light",
        "code_log_analysis":      "light",
        "embeddings":             "light",
        "fallback_chat":          "light",
    },
    notes=[
        "Vision AI disabled — accessibility tree used as fallback.",
        "Prefer phi4-mini or bge-m3 for all tasks.",
        "If model memory > 3.5 GB, skip and use deterministic result.",
        "Parallel calls blocked.",
    ],
)

# ── Profile 2: Mac M4 16 GB (12–24 GB) ───────────────────────────────────────
# Preserves all existing defaults exactly.

MAC_M4_16GB_ADAPTIVE = AdaptiveResourceProfile(
    profile_id="mac_m4_16gb",
    name="Mac M4 / 16 GB",
    description=(
        "Balanced profile for Apple Silicon or similar 12–24 GB machines. "
        "Sequential calls, heavy models allowed one at a time. "
        "Matches the original Inspectra routing defaults."
    ),
    min_ram_gb=12.0,
    max_ram_gb=24.0,
    max_parallel_model_calls=1,
    max_model_memory_gb=10.0,
    avoid_heavy_models=False,
    allow_heavy_models=True,
    allow_parallel_routing=False,
    unload_between_heavy_tasks=True,
    prefer_local=True,
    prefer_deterministic_when_low_resource=False,
    vision_enabled_by_default=True,
    recommended_context_tokens=4096,
    task_preferences={
        "vision_screen_analysis": "heavy",
        "ui_action_planning":     "heavy",
        "ai_oracle":              "medium",
        "root_cause_analysis":    "medium",
        "step_narration":         "light",
        "report_summary":         "heavy",
        "code_log_analysis":      "medium",
        "embeddings":             "light",
        "fallback_chat":          "medium",
    },
    notes=[
        "One model call at a time — sequential by design.",
        "Heavy models (qwen2.5vl, qwen3.5, gemma4) allowed sequentially.",
        "Unload between heavy tasks to free memory.",
        "Matches original mac_m4_16gb ResourceProfile behavior.",
    ],
)

# ── Profile 3: Pro 32 GB (24–48 GB) ──────────────────────────────────────────

PRO_32GB = AdaptiveResourceProfile(
    profile_id="pro_32gb",
    name="Pro / 32 GB",
    description=(
        "Performance profile for 24–48 GB machines. "
        "Two parallel calls allowed. Heavy models OK. "
        "Larger context windows. Stronger local models if installed."
    ),
    min_ram_gb=24.0,
    max_ram_gb=48.0,
    max_parallel_model_calls=2,
    max_model_memory_gb=20.0,
    avoid_heavy_models=False,
    allow_heavy_models=True,
    allow_parallel_routing=True,
    unload_between_heavy_tasks=False,
    prefer_local=True,
    prefer_deterministic_when_low_resource=False,
    vision_enabled_by_default=True,
    recommended_context_tokens=8192,
    task_preferences={
        "vision_screen_analysis": "heavy",
        "ui_action_planning":     "heavy",
        "ai_oracle":              "heavy",
        "root_cause_analysis":    "heavy",
        "step_narration":         "medium",
        "report_summary":         "heavy",
        "code_log_analysis":      "heavy",
        "embeddings":             "light",
        "fallback_chat":          "medium",
    },
    notes=[
        "Up to 2 parallel model calls allowed.",
        "Avoid running two heavy models simultaneously.",
        "Vision + light model can run in parallel.",
        "Larger local models recommended if installed (14b, 34b variants).",
    ],
)

# ── Profile 4: Workstation 64 GB (≥48 GB) ────────────────────────────────────

WORKSTATION_64GB = AdaptiveResourceProfile(
    profile_id="workstation_64gb",
    name="Workstation / 64 GB+",
    description=(
        "Maximum profile for high-memory workstations (48 GB+). "
        "Three parallel calls. Large local models allowed. "
        "Recommended for self-hosted LLM serving or large repos."
    ),
    min_ram_gb=48.0,
    max_ram_gb=0.0,
    max_parallel_model_calls=3,
    max_model_memory_gb=64.0,
    avoid_heavy_models=False,
    allow_heavy_models=True,
    allow_parallel_routing=True,
    unload_between_heavy_tasks=False,
    prefer_local=True,
    prefer_deterministic_when_low_resource=False,
    vision_enabled_by_default=True,
    recommended_context_tokens=16384,
    task_preferences={
        "vision_screen_analysis": "any",
        "ui_action_planning":     "any",
        "ai_oracle":              "any",
        "root_cause_analysis":    "any",
        "step_narration":         "any",
        "report_summary":         "any",
        "code_log_analysis":      "any",
        "embeddings":             "any",
        "fallback_chat":          "any",
    },
    notes=[
        "Up to 3 parallel model calls allowed.",
        "70b class models supported if installed.",
        "Large context (16k+) enabled.",
        "Suitable for CI/CD server with persistent model serving.",
    ],
)

# ── Profile 5: Remote GPU ─────────────────────────────────────────────────────

REMOTE_GPU = AdaptiveResourceProfile(
    profile_id="remote_gpu",
    name="Remote GPU / CUDA Server",
    description=(
        "Profile for machines with CUDA GPU or remote LLM serving. "
        "Parallelism configurable via provider settings. "
        "Heavy tasks prefer GPU-accelerated endpoints. "
        "Requires explicit provider trust configuration."
    ),
    min_ram_gb=16.0,
    max_ram_gb=0.0,
    max_parallel_model_calls=4,
    max_model_memory_gb=80.0,
    avoid_heavy_models=False,
    allow_heavy_models=True,
    allow_parallel_routing=True,
    unload_between_heavy_tasks=False,
    prefer_local=True,
    prefer_deterministic_when_low_resource=False,
    vision_enabled_by_default=True,
    recommended_context_tokens=32768,
    task_preferences={
        "vision_screen_analysis": "any",
        "ui_action_planning":     "any",
        "ai_oracle":              "any",
        "root_cause_analysis":    "any",
        "step_narration":         "light",
        "report_summary":         "any",
        "code_log_analysis":      "any",
        "embeddings":             "any",
        "fallback_chat":          "any",
    },
    notes=[
        "CUDA-accelerated inference. Model serving via Ollama or vLLM.",
        "Max parallel calls configurable per provider.",
        "Requires explicit trust_remote_provider=true for non-localhost endpoints.",
        "Cloud providers remain disabled unless explicitly configured.",
    ],
)


# ── Registry ───────────────────────────────────────────────────────────────────

_ALL_PROFILES: Dict[str, AdaptiveResourceProfile] = {
    p.profile_id: p
    for p in [LOW_RAM_8GB, MAC_M4_16GB_ADAPTIVE, PRO_32GB, WORKSTATION_64GB, REMOTE_GPU]
}


def get_all_profiles() -> Dict[str, AdaptiveResourceProfile]:
    return dict(_ALL_PROFILES)


def get_profile_by_id(profile_id: str) -> Optional[AdaptiveResourceProfile]:
    return _ALL_PROFILES.get(profile_id)
