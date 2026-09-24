"""
model_router.py - Specialist cloud-first router with deterministic safeguards.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable, Dict, List, Optional

from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_routing_policy import ModelRoutingPolicy
from qa_ai.ai.model_usage_logger import ModelUsageLogger
from qa_ai.ai.ollama_client import OllamaClient
from qa_ai.ai.openrouter_client import OpenRouterClient
from qa_ai.config.settings import Settings, get_settings
from qa_ai.runtime.artifact_store import ArtifactStore


@dataclass
class RoutedResult:
    success: bool
    content: str
    model: str
    provider: str
    latency_ms: float
    error_type: str = ""
    fallback_reason: str = ""


class ModelRouter:
    """Main entry point for component-first model routing."""

    def __init__(
        self,
        settings: Settings | None = None,
        openrouter_client: OpenRouterClient | Any | None = None,
        ollama_client: OllamaClient | Any | None = None,
        artifact_store: ArtifactStore | None = None,
    ):
        self.settings = settings or get_settings()
        self.policy = ModelRoutingPolicy(settings=self.settings)
        self.ollama = ollama_client or OllamaClient(base_url=self.settings.ollama_base_url)
        self.openrouter = openrouter_client or OpenRouterClient(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            timeout_seconds=self.settings.openrouter_timeout_seconds,
            long_timeout_seconds=self.settings.openrouter_long_timeout_seconds,
        )
        self.usage_logger = ModelUsageLogger(artifact_store=artifact_store)

    def route(
        self,
        component: RoutingComponent,
        prompt: str,
        context: Dict[str, Any] | None,
        require_json: bool = False,
        deterministic_fallback: Optional[Callable[[], str]] = None,
    ) -> RoutedResult:
        decision = self.policy.decide(component=component, context=context or {})
        cloud_prompt = self._cloud_prompt(prompt=prompt, context=context or {}, redact=decision.redact_for_cloud)
        local_prompt = prompt

        last_reason = ""
        for idx, candidate in enumerate(decision.fallback_chain):
            provider = candidate["provider"]
            model = candidate["model"]
            fallback_used = idx > 0
            start = time.time()
            try:
                if provider == "openrouter":
                    result = (
                        self.openrouter.chat_json(model=model, prompt=cloud_prompt)
                        if require_json
                        else self.openrouter.chat(model=model, prompt=cloud_prompt)
                    )
                    self.usage_logger.log(
                        component=component.value,
                        model=model,
                        provider=provider,
                        latency_ms=result.latency_ms,
                        fallback_used=fallback_used,
                        fallback_reason=result.fallback_reason,
                        privacy_mode=decision.privacy_decision,
                        success=result.success,
                    )
                    if result.success:
                        self.usage_logger.flush(routing_mode=self.settings.model_routing_mode)
                        return RoutedResult(
                            success=True,
                            content=result.content,
                            model=result.model,
                            provider=result.provider,
                            latency_ms=result.latency_ms,
                        )
                    last_reason = result.fallback_reason or result.error_type or "cloud_error"
                    continue

                if provider == "ollama":
                    if require_json:
                        content = self.ollama.chat_json(model=model, prompt=local_prompt)
                        serialized = json.dumps(content)
                    else:
                        serialized = self.ollama.chat(model=model, prompt=local_prompt)
                    latency_ms = (time.time() - start) * 1000
                    self.usage_logger.log(
                        component=component.value,
                        model=model,
                        provider=provider,
                        latency_ms=latency_ms,
                        fallback_used=fallback_used,
                        fallback_reason=last_reason,
                        privacy_mode=decision.privacy_decision,
                        success=True,
                    )
                    self.usage_logger.flush(routing_mode=self.settings.model_routing_mode)
                    return RoutedResult(
                        success=True,
                        content=serialized,
                        model=model,
                        provider=provider,
                        latency_ms=latency_ms,
                    )
            except Exception as exc:
                last_reason = str(exc)
                self.usage_logger.log(
                    component=component.value,
                    model=model,
                    provider=provider,
                    latency_ms=(time.time() - start) * 1000,
                    fallback_used=fallback_used,
                    fallback_reason=last_reason,
                    privacy_mode=decision.privacy_decision,
                    success=False,
                )
                continue

        if deterministic_fallback is not None:
            start = time.time()
            content = deterministic_fallback()
            latency_ms = (time.time() - start) * 1000
            self.usage_logger.log(
                component=component.value,
                model="deterministic",
                provider="deterministic",
                latency_ms=latency_ms,
                fallback_used=True,
                fallback_reason=last_reason or "model_failures",
                privacy_mode=decision.privacy_decision,
                success=True,
            )
            self.usage_logger.flush(routing_mode=self.settings.model_routing_mode)
            return RoutedResult(
                success=True,
                content=content,
                model="deterministic",
                provider="deterministic",
                latency_ms=latency_ms,
            )

        self.usage_logger.flush(routing_mode=self.settings.model_routing_mode)
        return RoutedResult(
            success=False,
            content="",
            model="",
            provider="",
            latency_ms=0.0,
            error_type="all_providers_failed",
            fallback_reason=last_reason or "all_providers_failed",
        )

    def route_json(
        self,
        component: RoutingComponent,
        prompt: str,
        context: Dict[str, Any] | None = None,
        schema_hint: Dict[str, Any] | None = None,
        deterministic_fallback: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        fallback = None
        if deterministic_fallback is not None:
            fallback = lambda: json.dumps(deterministic_fallback())

        result = self.route(
            component=component,
            prompt=prompt,
            context=context or {},
            require_json=True,
            deterministic_fallback=fallback,
        )
        if not result.success:
            return {"error": result.error_type or result.fallback_reason or "routing_failed"}
        try:
            return json.loads(result.content)
        except json.JSONDecodeError:
            return {"raw_response": result.content, "parse_error": True}

    def route_embedding(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vectors.append(self.ollama.embed(model="bge-m3", text=text))
        return vectors

    def route_visual(
        self,
        prompt: str,
        image_refs: List[str] | None = None,
        context: Dict[str, Any] | None = None,
    ) -> RoutedResult:
        merged_context = dict(context or {})
        if image_refs:
            merged_context["image_refs"] = image_refs
        return self.route(
            component=RoutingComponent.VISUAL_ANALYSIS,
            prompt=prompt,
            context=merged_context,
            require_json=False,
        )

    def get_routing_report(self) -> Dict[str, Any]:
        return self.usage_logger.flush(routing_mode=self.settings.model_routing_mode)

    def doctor(self) -> Dict[str, Any]:
        policy_check = self.policy.decide(component=RoutingComponent.MASTER_ORCHESTRATION, context={})
        return {
            "status": "ok",
            "routing_mode": self.settings.model_routing_mode,
            "allow_cloud_models": bool(self.settings.allow_cloud_models),
            "private_code_mode": bool(self.settings.private_code_mode),
            "openrouter_configured": bool(self.settings.openrouter_api_key),
            "local_provider": self.settings.local_fallback_provider,
            "sample_decision": {
                "component": policy_check.component,
                "model": policy_check.selected_model,
                "provider": policy_check.selected_provider,
                "reason": policy_check.reason,
            },
        }

    def _cloud_prompt(self, prompt: str, context: Dict[str, Any], redact: bool) -> str:
        if not redact:
            return prompt
        graphify_summary = str(context.get("graphify_summary") or "")
        if graphify_summary:
            return f"REDACTED_CONTEXT_ONLY\n{graphify_summary}"
        return "REDACTED_CONTEXT_ONLY"
