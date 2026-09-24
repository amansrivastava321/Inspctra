"""
profile_reporter.py - Build a human-readable profile + routing report.

Used by CLI models doctor and /api/models/profile/current.
No network calls. No secrets. No shell.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.model_runtime.hardware_detector import HardwareProfile
from qa_ai.model_runtime.profile_selector import SelectedModelRuntimeProfile


def build_profile_report(
    selected: SelectedModelRuntimeProfile,
) -> Dict[str, Any]:
    """
    Build a structured report dict from a SelectedModelRuntimeProfile.

    Safe to return from API — no secrets, no raw prompts.
    """
    p = selected.selected_profile
    hw = selected.hardware

    task_table = []
    for task, dec in selected.task_routes.items():
        task_table.append({
            "task": task,
            "model": dec.model,
            "provider": dec.provider,
            "fallback_models": dec.fallback_models,
            "estimated_memory_gb": dec.estimated_memory_gb,
            "capability_gap": dec.capability_gap,
            "gap_reason": dec.gap_reason,
            "overridden_by_user": dec.overridden_by_user,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "profile_id": p.profile_id,
            "name": p.name,
            "description": p.description,
            "max_parallel_model_calls": p.max_parallel_model_calls,
            "max_model_memory_gb": p.max_model_memory_gb,
            "allow_heavy_models": p.allow_heavy_models,
            "avoid_heavy_models": p.avoid_heavy_models,
            "vision_enabled_by_default": p.vision_enabled_by_default,
            "prefer_deterministic_when_low_resource": p.prefer_deterministic_when_low_resource,
            "recommended_context_tokens": p.recommended_context_tokens,
            "notes": p.notes,
        },
        "hardware": {
            "platform": hw.platform,
            "architecture": hw.architecture,
            "total_ram_gb": hw.total_ram_gb,
            "available_ram_gb": hw.available_ram_gb,
            "apple_silicon": hw.apple_silicon,
            "cuda_available": hw.cuda_available,
            "metal_available": hw.metal_available,
            "gpu_label": hw.gpu_label,
            "inside_container": hw.inside_container,
            "recommended_profile": hw.recommended_profile,
            "detection_confidence": hw.detection_confidence,
        },
        "selection_reason": selected.reason,
        "available_models": selected.available_models,
        "missing_models": selected.missing_models,
        "disabled_tasks": selected.disabled_tasks,
        "task_routes": task_table,
        "warnings": selected.warnings,
        "cloud_disabled": True,   # Cloud always disabled unless explicitly configured
    }


def format_profile_summary_text(selected: SelectedModelRuntimeProfile) -> str:
    """
    Return a compact CLI-friendly summary string.
    """
    p = selected.selected_profile
    hw = selected.hardware
    lines: List[str] = []

    lines.append(f"  Profile     : {p.profile_id} — {p.name}")
    lines.append(f"  RAM         : {hw.total_ram_gb:.1f} GB "
                 f"(available: {hw.available_ram_gb:.1f} GB)")
    lines.append(f"  Platform    : {hw.platform} / {hw.architecture}")
    if hw.apple_silicon:
        lines.append(f"  GPU         : {hw.gpu_label}")
    elif hw.cuda_available:
        lines.append(f"  GPU         : {hw.gpu_label} (CUDA)")
    lines.append(f"  Parallel    : max {p.max_parallel_model_calls} model call(s) at a time")
    lines.append(f"  Heavy models: {'✅ allowed' if p.allow_heavy_models else '❌ disabled'}")
    lines.append(f"  Vision AI   : {'✅ enabled' if p.vision_enabled_by_default else '❌ disabled'}")
    lines.append(f"  Max mem/call: {p.max_model_memory_gb:.1f} GB")
    lines.append("")

    lines.append("  Task routing:")
    for task, dec in selected.task_routes.items():
        if dec.capability_gap:
            lines.append(f"    {task:<28} ❌  (capability gap)")
        else:
            fb = f"  [fb: {','.join(dec.fallback_models[:2])}]" if dec.fallback_models else ""
            tag = " [user override]" if dec.overridden_by_user else ""
            lines.append(f"    {task:<28} ✅  {dec.model}{fb}{tag}")

    if selected.missing_models:
        lines.append("")
        lines.append("  Missing models (not installed):")
        for m in selected.missing_models[:8]:
            lines.append(f"    - {m}")

    if selected.warnings:
        lines.append("")
        lines.append("  Warnings:")
        for w in selected.warnings[:5]:
            lines.append(f"    ⚠️  {w}")

    return "\n".join(lines)
