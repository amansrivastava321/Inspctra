"""
profile_selector.py - Select best runtime profile given hardware + installed models.

Inputs: hardware, installed models, configured providers, user overrides.
Output: SelectedModelRuntimeProfile with per-task routes.

Selection rules:
1. Detect hardware → get recommended profile.
2. Discover installed models via provider discovery.
3. For each task: pick best available model within profile memory limit.
4. If primary model not installed: try fallback models.
5. If no model found for task: mark capability_gap.
6. Apply user overrides last.
7. Low-RAM: avoid heavy models.
8. High-RAM: allow better models if installed.

No app-specific logic. No cloud calls. No secrets.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from qa_ai.model_runtime.adaptive_profiles import (
    AdaptiveResourceProfile,
    get_all_profiles,
    get_profile_by_id,
    MAC_M4_16GB_ADAPTIVE,
)
from qa_ai.model_runtime.hardware_detector import HardwareProfile, detect_hardware
from qa_ai.model_runtime.model_catalog import ModelCatalog, get_default_catalog
from qa_ai.ai.task_profiles import ModelTask, get_default_task_routes

logger = logging.getLogger(__name__)


@dataclass
class TaskRouteDecision:
    task: str
    model: Optional[str]           # None if capability_gap
    provider: str
    fallback_models: List[str]
    estimated_memory_gb: float
    capability_gap: bool
    gap_reason: Optional[str]
    overridden_by_user: bool


@dataclass
class SelectedModelRuntimeProfile:
    selected_profile: AdaptiveResourceProfile
    reason: str
    hardware: HardwareProfile
    task_routes: Dict[str, TaskRouteDecision]
    missing_models: List[str]
    available_models: List[str]
    disabled_tasks: List[str]
    warnings: List[str]


# ── Default model preferences per profile ─────────────────────────────────────
# For each profile_id, list preferred model names per task (ordered by preference).
# These are suggestions — actual selection requires the model to be installed.

_PROFILE_MODEL_PREFS: Dict[str, Dict[str, List[str]]] = {
    "low_ram_8gb": {
        "vision_screen_analysis": [],        # disabled
        "ui_action_planning":     ["phi4-mini:latest", "phi3:mini", "mistral:7b"],
        "ai_oracle":              ["phi4-mini:latest", "phi3:mini"],
        "root_cause_analysis":    ["phi4-mini:latest", "phi3:mini"],
        "step_narration":         ["phi4-mini:latest", "phi3:mini"],
        "report_summary":         ["phi4-mini:latest", "phi3:mini"],
        "code_log_analysis":      ["phi4-mini:latest", "phi3:mini"],
        "embeddings":             ["bge-m3:latest", "nomic-embed-text:latest",
                                   "mxbai-embed-large:latest"],
        "fallback_chat":          ["phi4-mini:latest", "phi3:mini"],
    },
    "mac_m4_16gb": {
        "vision_screen_analysis": ["qwen2.5vl:7b"],
        "ui_action_planning":     ["qwen3.5:9b", "phi4-mini:latest"],
        "ai_oracle":              ["deepseek-r1:7b", "qwen3.5:9b"],
        "root_cause_analysis":    ["deepseek-r1:7b", "dolphincoder:7b"],
        "step_narration":         ["phi4-mini:latest", "dolphin-mistral:7b"],
        "report_summary":         ["gemma4:e4b", "qwen3.5:9b"],
        "code_log_analysis":      ["dolphincoder:7b", "deepseek-r1:7b"],
        "embeddings":             ["bge-m3:latest", "nomic-embed-text:latest",
                                   "mxbai-embed-large:latest"],
        "fallback_chat":          ["dolphin-mistral:7b", "phi4-mini:latest"],
    },
    "pro_32gb": {
        "vision_screen_analysis": ["qwen2.5vl:7b", "llava:7b"],
        "ui_action_planning":     ["qwen3.5:9b", "llama3.1:8b", "deepseek-r1:7b"],
        "ai_oracle":              ["deepseek-r1:7b", "qwen3.5:9b"],
        "root_cause_analysis":    ["deepseek-r1:7b", "dolphincoder:7b"],
        "step_narration":         ["phi4-mini:latest", "dolphin-mistral:7b"],
        "report_summary":         ["gemma4:e4b", "qwen3.5:9b", "llama3.1:8b"],
        "code_log_analysis":      ["dolphincoder:7b", "deepseek-r1:7b"],
        "embeddings":             ["bge-m3:latest", "nomic-embed-text:latest",
                                   "mxbai-embed-large:latest"],
        "fallback_chat":          ["dolphin-mistral:7b", "llama3.1:8b", "phi4-mini:latest"],
    },
    "workstation_64gb": {
        "vision_screen_analysis": ["qwen2.5vl:7b", "llava:34b", "llava:7b"],
        "ui_action_planning":     ["qwen3.5:9b", "deepseek-r1:7b", "llama3.1:8b"],
        "ai_oracle":              ["deepseek-r1:7b", "qwen3.5:9b"],
        "root_cause_analysis":    ["deepseek-r1:7b", "dolphincoder:7b"],
        "step_narration":         ["phi4-mini:latest", "dolphin-mistral:7b"],
        "report_summary":         ["gemma4:e4b", "qwen3.5:9b"],
        "code_log_analysis":      ["dolphincoder:7b", "deepseek-r1:7b"],
        "embeddings":             ["bge-m3:latest", "nomic-embed-text:latest"],
        "fallback_chat":          ["dolphin-mistral:7b", "phi4-mini:latest"],
    },
    "remote_gpu": {
        "vision_screen_analysis": ["qwen2.5vl:7b", "llava:7b"],
        "ui_action_planning":     ["qwen3.5:9b", "deepseek-r1:7b"],
        "ai_oracle":              ["deepseek-r1:7b", "qwen3.5:9b"],
        "root_cause_analysis":    ["deepseek-r1:7b", "dolphincoder:7b"],
        "step_narration":         ["phi4-mini:latest", "dolphin-mistral:7b"],
        "report_summary":         ["gemma4:e4b", "qwen3.5:9b"],
        "code_log_analysis":      ["dolphincoder:7b", "deepseek-r1:7b"],
        "embeddings":             ["bge-m3:latest", "nomic-embed-text:latest"],
        "fallback_chat":          ["dolphin-mistral:7b", "phi4-mini:latest"],
    },
}


def _pick_model(
    task: str,
    profile: AdaptiveResourceProfile,
    installed: List[str],
    catalog: ModelCatalog,
    user_override: Optional[str] = None,
) -> TaskRouteDecision:
    """Pick best available model for a task given constraints."""
    max_mem = profile.max_model_memory_gb

    # User override takes priority
    if user_override:
        cap = catalog.get(user_override)
        if user_override in installed:
            return TaskRouteDecision(
                task=task,
                model=user_override,
                provider="ollama",
                fallback_models=[],
                estimated_memory_gb=cap.estimated_memory_gb,
                capability_gap=False,
                gap_reason=None,
                overridden_by_user=True,
            )
        else:
            logger.warning("User-overridden model %r not installed.", user_override)

    # Disabled task
    prefs = _PROFILE_MODEL_PREFS.get(profile.profile_id, {})
    task_prefs = prefs.get(task, [])
    if not task_prefs and profile.profile_id == "low_ram_8gb":
        # Vision disabled on low_ram
        return TaskRouteDecision(
            task=task,
            model=None,
            provider="none",
            fallback_models=[],
            estimated_memory_gb=0.0,
            capability_gap=True,
            gap_reason=f"Task '{task}' disabled on {profile.profile_id} profile.",
            overridden_by_user=False,
        )

    # Try each preferred model in order
    installed_set = set(installed)
    fallbacks: List[str] = []
    primary: Optional[str] = None

    for m in task_prefs:
        cap = catalog.get(m)
        if cap.estimated_memory_gb > max_mem:
            continue
        if m in installed_set:
            if primary is None:
                primary = m
            else:
                fallbacks.append(m)
                if len(fallbacks) >= 2:
                    break

    if primary:
        cap = catalog.get(primary)
        return TaskRouteDecision(
            task=task,
            model=primary,
            provider="ollama",
            fallback_models=fallbacks,
            estimated_memory_gb=cap.estimated_memory_gb,
            capability_gap=False,
            gap_reason=None,
            overridden_by_user=False,
        )

    # No preferred model found — try catalog-based search
    candidates = catalog.models_for_task(task, installed, max_mem)
    if candidates:
        c = candidates[0]
        return TaskRouteDecision(
            task=task,
            model=c.model,
            provider="ollama",
            fallback_models=[x.model for x in candidates[1:3]],
            estimated_memory_gb=c.estimated_memory_gb,
            capability_gap=False,
            gap_reason=None,
            overridden_by_user=False,
        )

    return TaskRouteDecision(
        task=task,
        model=None,
        provider="none",
        fallback_models=[],
        estimated_memory_gb=0.0,
        capability_gap=True,
        gap_reason=(
            f"No installed model found for task '{task}' "
            f"within {max_mem} GB memory limit. "
            f"Install one of: {task_prefs[:3]}"
        ),
        overridden_by_user=False,
    )


def select_profile(
    hardware: Optional[HardwareProfile] = None,
    installed_models: Optional[List[str]] = None,
    profile_override: Optional[str] = None,
    user_task_overrides: Optional[Dict[str, str]] = None,
    ollama_url: str = "http://127.0.0.1:11434",
) -> SelectedModelRuntimeProfile:
    """
    Select best runtime profile and per-task routes.

    Args:
        hardware: Pre-detected hardware. Detected if None.
        installed_models: Pre-fetched model list. Discovered if None.
        profile_override: Force a specific profile_id.
        user_task_overrides: {task: model} user-specified overrides.
        ollama_url: Ollama base URL for model discovery.

    Returns SelectedModelRuntimeProfile.
    """
    from qa_ai.model_runtime.provider_discovery import get_installed_models

    # 1. Hardware detection
    if hardware is None:
        try:
            hardware = detect_hardware()
        except Exception as exc:
            logger.warning("Hardware detection failed: %s — using conservative defaults.", exc)
            from qa_ai.model_runtime.hardware_detector import HardwareProfile as HP
            hardware = HP(
                platform="unknown", architecture="unknown",
                total_ram_gb=0.0, available_ram_gb=0.0,
                apple_silicon=False, cuda_available=False,
                metal_available=False, gpu_label="unknown",
                inside_container=False,
                recommended_profile="mac_m4_16gb",
                detection_confidence="low",
                warnings=["Hardware detection failed — using conservative defaults."],
            )

    # 2. Profile selection
    profile_id = profile_override or hardware.recommended_profile
    profile = get_profile_by_id(profile_id)
    if profile is None:
        profile = MAC_M4_16GB_ADAPTIVE
        profile_id = profile.profile_id

    reason = (
        f"Profile '{profile_id}' selected: "
        f"RAM={hardware.total_ram_gb:.1f}GB, "
        f"arch={hardware.architecture}, "
        f"confidence={hardware.detection_confidence}"
    )
    if profile_override:
        reason = f"User-overridden to '{profile_id}'."

    # 3. Installed models
    warnings = list(hardware.warnings)
    if installed_models is None:
        try:
            installed_models = get_installed_models(ollama_url)
        except Exception as exc:
            logger.warning("Model discovery failed: %s", exc)
            installed_models = []
            warnings.append(f"Model discovery failed: {exc}")

    # 4. Catalog
    catalog = get_default_catalog()

    # 5. Per-task route selection
    user_overrides = user_task_overrides or {}
    task_routes: Dict[str, TaskRouteDecision] = {}
    missing: List[str] = []
    disabled: List[str] = []

    for task in ModelTask:
        override = user_overrides.get(task.value)
        decision = _pick_model(task.value, profile, installed_models, catalog, override)
        task_routes[task.value] = decision
        if decision.capability_gap:
            disabled.append(task.value)
            if decision.gap_reason:
                warnings.append(decision.gap_reason)

    # Collect missing primary models (models in prefs but not installed)
    prefs = _PROFILE_MODEL_PREFS.get(profile_id, {})
    installed_set = set(installed_models)
    for task_prefs in prefs.values():
        for m in task_prefs[:1]:   # only primary preference
            if m and m not in installed_set and m not in missing:
                missing.append(m)

    return SelectedModelRuntimeProfile(
        selected_profile=profile,
        reason=reason,
        hardware=hardware,
        task_routes=task_routes,
        missing_models=missing,
        available_models=installed_models,
        disabled_tasks=disabled,
        warnings=warnings,
    )
