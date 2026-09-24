"""
resource_manager.py - Prevent memory overload on 16 GB Mac M4 Pro.

Rules:
- Maximum one concurrent model call (sequential by default).
- Heavy models (≥ 6 GB) cannot run while another model is loaded.
- Lightweight tracking only — no OS-level memory queries.
- Conservative fixed memory estimates per model.
- Thread-safe via RLock.
- Graceful degradation: if resource check fails, route to lighter model.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from qa_ai.ai.task_profiles import (
    MAC_M4_16GB,
    ModelTask,
    ResourceProfile,
    TaskRoute,
    get_default_task_routes,
)

logger = logging.getLogger(__name__)

_DEFAULT_PROFILE = MAC_M4_16GB


@dataclass
class SlotState:
    task: str
    model: str
    acquired_at: float = field(default_factory=time.time)


class ResourceManager:
    """
    Serialise model calls on memory-constrained hardware.

    Mac M4 Pro 16 GB: max one model call at a time.
    Heavy models (gemma4:e4b, qwen3.5:9b, qwen2.5vl:7b) are blocked
    if any other model is active.
    """

    def __init__(
        self,
        profile: ResourceProfile = _DEFAULT_PROFILE,
        _routes: Optional[Dict[ModelTask, TaskRoute]] = None,
    ) -> None:
        self._profile = profile
        self._routes = _routes or get_default_task_routes()
        self._lock = threading.RLock()
        self._active: Optional[SlotState] = None

    # ── Public interface ───────────────────────────────────────────────────────

    def acquire_model_slot(self, task: ModelTask | str, model: str) -> bool:
        """
        Mark a model as active.

        Returns True if slot acquired, False if blocked.
        Single-slot policy: if any model is active, block.
        """
        task_str = task.value if isinstance(task, ModelTask) else str(task)
        with self._lock:
            if self._active is not None:
                logger.debug(
                    "ResourceManager: slot occupied by %s/%s, blocking %s/%s",
                    self._active.task, self._active.model, task_str, model,
                )
                return False
            self._active = SlotState(task=task_str, model=model)
            logger.debug("ResourceManager: acquired slot for %s/%s", task_str, model)
            return True

    def release_model_slot(self, task: ModelTask | str, model: str) -> None:
        """Release the active slot."""
        task_str = task.value if isinstance(task, ModelTask) else str(task)
        with self._lock:
            if self._active and self._active.task == task_str and self._active.model == model:
                logger.debug("ResourceManager: released slot for %s/%s", task_str, model)
                self._active = None
            else:
                # Mismatched release (e.g., timeout path) — clear anyway to unblock
                if self._active:
                    logger.warning(
                        "ResourceManager: release mismatch: active=%s/%s, releasing=%s/%s — clearing",
                        self._active.task, self._active.model, task_str, model,
                    )
                self._active = None

    def can_run(self, model: str) -> bool:
        """True if no model is currently active."""
        with self._lock:
            return self._active is None

    def should_defer(self, model: str) -> bool:
        """True if this model should wait for the current slot to free."""
        return not self.can_run(model)

    def route_to_lighter_model_if_needed(self, task: ModelTask) -> Optional[str]:
        """
        If the preferred model for task is heavy and slot is occupied,
        suggest a lighter fallback if available.

        Returns fallback model name, or None if preferred model is free.
        """
        with self._lock:
            if self._active is None:
                return None  # Preferred model is fine

        route = self._routes.get(task)
        if not route:
            return None

        tier = self._profile.tier(route.model)
        if tier != "heavy":
            return None  # Not heavy, no rerouting needed

        # Find lighter fallback
        for fallback in route.fallback_models:
            fb_tier = self._profile.tier(fallback)
            if fb_tier in ("medium", "light"):
                logger.info(
                    "ResourceManager: heavy model %s deferred, routing to %s for task %s",
                    route.model, fallback, task.value,
                )
                return fallback

        return None

    def memory_policy_summary(self) -> dict:
        """Return human-readable summary of the memory policy."""
        with self._lock:
            active_info = (
                {"task": self._active.task, "model": self._active.model,
                 "held_for_s": round(time.time() - self._active.acquired_at, 1)}
                if self._active else None
            )
        return {
            "profile": self._profile.name,
            "max_parallel_model_calls": self._profile.max_parallel_model_calls,
            "prefer_sequential_calls": self._profile.prefer_sequential_calls,
            "unload_between_heavy_tasks": self._profile.unload_between_heavy_tasks,
            "total_ram_gb": self._profile.total_ram_gb,
            "slot_occupied": self._active is not None,
            "active_slot": active_info,
            "heavy_models": sorted(self._profile.heavy_models),
            "medium_models": sorted(self._profile.medium_models),
            "light_models": sorted(self._profile.light_models),
        }

    def estimated_memory_gb(self, model: str) -> float:
        return self._profile.estimated_memory_gb(model)


# ── Process-level singleton ────────────────────────────────────────────────────

_singleton: Optional[ResourceManager] = None
_singleton_lock = threading.Lock()


def get_resource_manager(profile: ResourceProfile = _DEFAULT_PROFILE) -> ResourceManager:
    """Return the process-wide ResourceManager singleton."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = ResourceManager(profile=profile)
    return _singleton
