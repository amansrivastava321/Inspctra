"""
model_routing_policy.py - Policy engine for specialist component routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from qa_ai.ai.model_profiles import (
    ProviderKind,
    RoutingComponent,
    get_component_profiles,
    get_model_catalog,
)
from qa_ai.config.settings import Settings, get_settings


@dataclass
class RoutingDecision:
    component: str
    selected_model: str
    selected_provider: str
    fallback_chain: List[Dict[str, str]]
    privacy_decision: str
    reason: str
    redact_for_cloud: bool = False


class ModelRoutingPolicy:
    """Choose model/provider chain by QA-AI function component."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.catalog = get_model_catalog()
        self.profiles = get_component_profiles()

    def decide(
        self,
        component: RoutingComponent,
        context: Dict[str, Any] | None = None,
        cloud_circuit_open: bool = False,
    ) -> RoutingDecision:
        context = context or {}
        profile = self.profiles[component]

        # Embeddings are always local-only.
        if component == RoutingComponent.EMBEDDINGS:
            selected = self.catalog[profile.primary_model_id]
            return RoutingDecision(
                component=component.value,
                selected_model=selected.model_name,
                selected_provider=selected.provider.value,
                fallback_chain=[self._entry(selected.model_id)],
                privacy_decision="local_only_embedding",
                reason="embeddings_local_only",
            )

        contains_private_code = bool(context.get("contains_private_code", False))
        private_mode = bool(self.settings.private_code_mode or contains_private_code)
        cloud_allowed = self._cloud_allowed(private_mode=private_mode)
        redact = bool(private_mode and self.settings.redact_cloud_context)

        if cloud_circuit_open:
            cloud_allowed = False
            cloud_reason = "cloud_circuit_breaker_open"
        elif not self.settings.openrouter_api_key:
            cloud_allowed = False
            cloud_reason = "missing_openrouter_api_key"
        elif not self.settings.allow_cloud_models:
            cloud_allowed = False
            cloud_reason = "cloud_models_disabled"
        else:
            cloud_reason = "cloud_allowed"

        chain: List[Dict[str, str]] = []

        if component == RoutingComponent.VISUAL_ANALYSIS:
            # Visual analysis is local-first with optional cloud backup.
            local_first = self.catalog[profile.primary_model_id]
            chain.append(self._entry(local_first.model_id))
            if self.settings.enable_visual_cloud_backup and self.settings.allow_cloud_models and self.settings.openrouter_api_key:
                backup = self.catalog[profile.fallback_model_ids[0]]
                chain.append(self._entry(backup.model_id))
            return RoutingDecision(
                component=component.value,
                selected_model=local_first.model_name,
                selected_provider=local_first.provider.value,
                fallback_chain=chain,
                privacy_decision="private_local_only" if private_mode and not cloud_allowed else "standard",
                reason="visual_local_first",
                redact_for_cloud=redact,
            )

        if cloud_allowed and self.settings.model_routing_mode == "specialist_cloud_first":
            primary = self.catalog[profile.primary_model_id]
            chain.append(self._entry(primary.model_id))
            for fallback in profile.fallback_model_ids:
                chain.append(self._entry(fallback))
            return RoutingDecision(
                component=component.value,
                selected_model=primary.model_name,
                selected_provider=primary.provider.value,
                fallback_chain=chain,
                privacy_decision="redacted_cloud_context" if redact else "standard",
                reason="cloud_first_specialist",
                redact_for_cloud=redact,
            )

        # Local-first fallback path.
        local_fallback = self.catalog[profile.fallback_model_ids[0]] if profile.fallback_model_ids else None
        if local_fallback is None:
            local_fallback = self.catalog["ollama:qwen3.5:9b"]

        chain.append(self._entry(local_fallback.model_id))
        if self.settings.enable_visual_cloud_backup and component == RoutingComponent.VISUAL_ANALYSIS:
            chain.extend([self._entry(mid) for mid in profile.fallback_model_ids])

        return RoutingDecision(
            component=component.value,
            selected_model=local_fallback.model_name,
            selected_provider=local_fallback.provider.value,
            fallback_chain=chain,
            privacy_decision="private_local_only" if private_mode else "standard",
            reason=cloud_reason,
            redact_for_cloud=redact,
        )

    def _cloud_allowed(self, private_mode: bool) -> bool:
        if not self.settings.allow_cloud_models:
            return False
        if private_mode and self.settings.require_cloud_permission_for_private_code and not self.settings.allow_cloud_models:
            return False
        return True

    def _entry(self, model_id: str) -> Dict[str, str]:
        model = self.catalog[model_id]
        return {
            "provider": model.provider.value,
            "model": model.model_name,
            "model_id": model.model_id,
        }
