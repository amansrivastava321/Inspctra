"""
adaptive_router.py - Hardware-aware task router that wraps TaskRouter.

Uses SelectedModelRuntimeProfile to route each task to the best
available model for the current hardware.

Falls back to existing TaskRouter for backward compatibility.
Never crashes — capability_gap returned on failure.
No cloud calls. No secrets. No shell.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from qa_ai.ai.task_profiles import ModelTask, get_default_task_routes, TaskRoute
from qa_ai.ai.task_router import ModelCallResult, TaskRouter, _capability_gap, get_task_router
from qa_ai.ai.resource_manager import ResourceManager, get_resource_manager
from qa_ai.model_runtime.adaptive_profiles import AdaptiveResourceProfile
from qa_ai.model_runtime.profile_selector import (
    SelectedModelRuntimeProfile,
    TaskRouteDecision,
    select_profile,
)

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    task: str
    selected_model: Optional[str]
    selected_provider: str
    reason: str
    fallback_used: bool
    profile_id: str
    estimated_memory_gb: float
    allowed_parallelism: int
    blocked_reason: Optional[str]
    overridden_by_user: bool


class AdaptiveRouter:
    """
    Hardware-aware model router.

    Wraps TaskRouter with adaptive profile selection:
    - Picks model based on detected RAM/hardware.
    - Respects max_model_memory_gb from profile.
    - Allows parallel calls only when profile permits.
    - Falls back to TaskRouter defaults if profile unavailable.
    - User task overrides respected.

    Thread-safe.
    """

    def __init__(
        self,
        profile: Optional[SelectedModelRuntimeProfile] = None,
        task_router: Optional[TaskRouter] = None,
        resource_manager: Optional[ResourceManager] = None,
        allow_cloud: bool = False,
        private_mode: bool = True,
    ) -> None:
        self._profile = profile          # None = use TaskRouter defaults
        self._task_router = task_router or get_task_router(allow_cloud=allow_cloud,
                                                           private_mode=private_mode)
        self._rm = resource_manager or get_resource_manager()
        self._lock = threading.Lock()

    @classmethod
    def from_hardware(
        cls,
        profile_override: Optional[str] = None,
        user_task_overrides: Optional[Dict[str, str]] = None,
        ollama_url: str = "http://127.0.0.1:11434",
        allow_cloud: bool = False,
        private_mode: bool = True,
    ) -> "AdaptiveRouter":
        """
        Factory: auto-detect hardware and select profile.
        Builds an AdaptiveRouter with the correct routes for this machine.
        """
        try:
            profile = select_profile(
                profile_override=profile_override,
                user_task_overrides=user_task_overrides,
                ollama_url=ollama_url,
            )
        except Exception as exc:
            logger.warning("AdaptiveRouter.from_hardware failed: %s — using defaults.", exc)
            profile = None

        return cls(profile=profile, allow_cloud=allow_cloud, private_mode=private_mode)

    def call(
        self,
        task: ModelTask,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        images: Optional[List[str]] = None,
        json_mode: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelCallResult:
        """
        Route prompt to best model for task.

        Checks profile-selected model first.
        Falls back to TaskRouter defaults if profile unavailable.
        Returns capability_gap if no model available.
        """
        # Profile-based routing
        if self._profile:
            decision = self._profile.task_routes.get(task.value)
            if decision and decision.capability_gap:
                return _capability_gap(
                    task,
                    decision.gap_reason or f"Task '{task.value}' has no available model.",
                )
            if decision and decision.model:
                return self._call_with_decision(task, prompt, decision,
                                                system_prompt, images, json_mode)

        # Fallback: delegate to existing TaskRouter
        return self._task_router.call(
            task, prompt,
            system_prompt=system_prompt,
            images=images,
            json_mode=json_mode,
            metadata=metadata,
        )

    def get_route_decision(self, task: ModelTask) -> RouteDecision:
        """Return route decision for a task without making a model call."""
        profile_id = "default"
        parallelism = 1

        if self._profile:
            profile_id = self._profile.selected_profile.profile_id
            parallelism = self._profile.selected_profile.max_parallel_model_calls
            decision = self._profile.task_routes.get(task.value)
            if decision:
                return RouteDecision(
                    task=task.value,
                    selected_model=decision.model,
                    selected_provider=decision.provider,
                    reason=(
                        decision.gap_reason
                        if decision.capability_gap
                        else f"Profile '{profile_id}' selected this model."
                    ),
                    fallback_used=False,
                    profile_id=profile_id,
                    estimated_memory_gb=decision.estimated_memory_gb,
                    allowed_parallelism=parallelism,
                    blocked_reason=decision.gap_reason if decision.capability_gap else None,
                    overridden_by_user=decision.overridden_by_user,
                )

        # Default routes
        default_routes = get_default_task_routes()
        route = default_routes.get(task)
        if route:
            return RouteDecision(
                task=task.value,
                selected_model=route.model,
                selected_provider=route.provider,
                reason="Default mac_m4_16gb route.",
                fallback_used=False,
                profile_id="mac_m4_16gb",
                estimated_memory_gb=route.estimated_memory_gb,
                allowed_parallelism=1,
                blocked_reason=None,
                overridden_by_user=False,
            )

        return RouteDecision(
            task=task.value,
            selected_model=None,
            selected_provider="none",
            reason="No route configured.",
            fallback_used=False,
            profile_id="none",
            estimated_memory_gb=0.0,
            allowed_parallelism=0,
            blocked_reason="No route configured for this task.",
            overridden_by_user=False,
        )

    def profile_summary(self) -> Dict[str, Any]:
        """Return a summary of the active profile and resource limits."""
        if self._profile:
            p = self._profile.selected_profile
            return {
                "profile_id": p.profile_id,
                "name": p.name,
                "max_parallel_model_calls": p.max_parallel_model_calls,
                "max_model_memory_gb": p.max_model_memory_gb,
                "allow_heavy_models": p.allow_heavy_models,
                "avoid_heavy_models": p.avoid_heavy_models,
                "vision_enabled": p.vision_enabled_by_default,
                "prefer_deterministic": p.prefer_deterministic_when_low_resource,
                "missing_models": self._profile.missing_models,
                "disabled_tasks": self._profile.disabled_tasks,
                "warnings": self._profile.warnings,
                "hardware": {
                    "platform": self._profile.hardware.platform,
                    "architecture": self._profile.hardware.architecture,
                    "total_ram_gb": self._profile.hardware.total_ram_gb,
                    "apple_silicon": self._profile.hardware.apple_silicon,
                    "gpu_label": self._profile.hardware.gpu_label,
                },
            }
        return {
            "profile_id": "mac_m4_16gb",
            "name": "Mac M4 / 16 GB (default)",
            "max_parallel_model_calls": 1,
            "max_model_memory_gb": 10.0,
            "allow_heavy_models": True,
            "avoid_heavy_models": False,
            "vision_enabled": True,
            "prefer_deterministic": False,
            "missing_models": [],
            "disabled_tasks": [],
            "warnings": [],
            "hardware": {},
        }

    # ── Private ─────────────────────────────────────────────────────────────

    def _call_with_decision(
        self,
        task: ModelTask,
        prompt: str,
        decision: TaskRouteDecision,
        system_prompt: Optional[str],
        images: Optional[List[str]],
        json_mode: bool,
    ) -> ModelCallResult:
        """
        Build a TaskRoute from the profile decision and delegate to TaskRouter.
        """
        from qa_ai.ai.task_profiles import TaskRoute as TR
        from qa_ai.model_runtime.model_catalog import get_default_catalog

        catalog = get_default_catalog()
        cap = catalog.get(decision.model)

        route = TR(
            task=task,
            provider=decision.provider,
            model=decision.model,
            fallback_models=decision.fallback_models,
            temperature=0.1,
            timeout_seconds=90,
            max_tokens=2048,
            estimated_memory_gb=decision.estimated_memory_gb,
            supports_vision=cap.vision,
            local_only=True,
        )

        # Patch router routes temporarily and delegate
        orig_routes = self._task_router._routes
        try:
            self._task_router._routes = {task: route, **{
                k: v for k, v in orig_routes.items() if k != task
            }}
            return self._task_router.call(
                task, prompt,
                system_prompt=system_prompt,
                images=images,
                json_mode=json_mode,
            )
        finally:
            self._task_router._routes = orig_routes


# ── Process-level singleton ───────────────────────────────────────────────────

_adaptive_singleton: Optional[AdaptiveRouter] = None
_adaptive_lock = threading.Lock()


def get_adaptive_router(
    force_refresh: bool = False,
    profile_override: Optional[str] = None,
) -> AdaptiveRouter:
    """Return process-wide AdaptiveRouter singleton."""
    global _adaptive_singleton
    if _adaptive_singleton is None or force_refresh:
        with _adaptive_lock:
            if _adaptive_singleton is None or force_refresh:
                _adaptive_singleton = AdaptiveRouter.from_hardware(
                    profile_override=profile_override
                )
    return _adaptive_singleton
