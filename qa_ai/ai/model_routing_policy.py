"""
model_routing_policy.py - Policy engine for specialist component routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from qa_ai.ai.model_profiles import (
    CLOUD_PROVIDER_NAMES,
    GEMINI_BACKUP_ID,
    GEMINI_PRIMARY_ID,
    GROQ_PRIMARY_ID,
    RoutingComponent,
    get_component_profiles,
    get_model_catalog,
    get_preferred_cloud_model_ids,
)
from qa_ai.config.settings import Settings, cloud_provider_keys, get_settings


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
        self.preferred_cloud = get_preferred_cloud_model_ids()

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

        configured_cloud = cloud_provider_keys(self.settings)

        if cloud_circuit_open:
            cloud_allowed = False
            cloud_reason = "cloud_circuit_breaker_open"
        elif not configured_cloud:
            cloud_allowed = False
            cloud_reason = "missing_cloud_api_key"
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
            if self.settings.enable_visual_cloud_backup and self.settings.allow_cloud_models and "openrouter" in configured_cloud:
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
            # Configured premium providers first, then the component's own models. Cloud entries whose
            # provider has no key are dropped so a request never waits on a call that cannot succeed.
            candidate_ids = [
                *self.preferred_cloud.get(component, []),
                profile.primary_model_id,
                *profile.fallback_model_ids,
            ]
            seen: set[str] = set()
            seen_calls: set[tuple[str, str]] = set()
            for model_id in candidate_ids:
                entry_provider = self.catalog[model_id].provider.value
                if model_id in seen or (entry_provider in CLOUD_PROVIDER_NAMES and entry_provider not in configured_cloud):
                    continue
                seen.add(model_id)
                entry = self._entry(model_id)
                # Overrides can make two entries resolve to the same provider and model: call it once.
                call = (entry["provider"], entry["model"])
                if call in seen_calls:
                    continue
                seen_calls.add(call)
                chain.append(entry)
            if chain:
                selected = chain[0]
                return RoutingDecision(
                    component=component.value,
                    selected_model=selected["model"],
                    selected_provider=selected["provider"],
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
        name = model.model_name
        # The default Gemini/Groq models can be overridden without touching the catalog. Each override
        # applies to its own catalog entry only, so the Gemini backup is not rewritten to the primary.
        if model.model_id == GEMINI_PRIMARY_ID:
            name = self.settings.gemini_model or name
        elif model.model_id == GEMINI_BACKUP_ID:
            name = self.settings.gemini_fallback_model or name
        elif model.model_id == GROQ_PRIMARY_ID:
            name = self.settings.groq_model or name
        return {
            "provider": model.provider.value,
            "model": name,
            "model_id": model.model_id,
        }
