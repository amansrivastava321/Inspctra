from dataclasses import replace

from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_routing_policy import ModelRoutingPolicy
from qa_ai.config.settings import Settings


def _settings(**overrides):
    base = Settings()
    for key, value in overrides.items():
        base = replace(base, **{key: value})
    return base


def test_policy_cloud_first_when_allowed() -> None:
    policy = ModelRoutingPolicy(
        settings=_settings(
            model_routing_mode="specialist_cloud_first",
            allow_cloud_models=True,
            openrouter_api_key="sk-test",
            private_code_mode=False,
        )
    )
    decision = policy.decide(component=RoutingComponent.MASTER_ORCHESTRATION, context={"contains_private_code": False})
    assert decision.selected_provider == "openrouter"
    assert decision.selected_model.endswith("hermes-3-llama-3.1-405b:free")


def test_policy_local_first_when_private_mode_blocks_cloud() -> None:
    policy = ModelRoutingPolicy(
        settings=_settings(
            allow_cloud_models=False,
            openrouter_api_key="sk-test",
            private_code_mode=True,
            require_cloud_permission_for_private_code=True,
        )
    )
    decision = policy.decide(component=RoutingComponent.STRUCTURED_REASONING, context={"contains_private_code": True})
    assert decision.selected_provider == "ollama"
    assert decision.privacy_decision == "private_local_only"


def test_policy_missing_api_key_forces_local() -> None:
    policy = ModelRoutingPolicy(
        settings=_settings(
            allow_cloud_models=True,
            openrouter_api_key="",
            private_code_mode=False,
        )
    )
    decision = policy.decide(component=RoutingComponent.HUGE_REPO_REASONING, context={})
    assert decision.selected_provider == "ollama"
    assert decision.reason == "missing_openrouter_api_key"


def test_embeddings_always_local() -> None:
    policy = ModelRoutingPolicy(settings=_settings())
    decision = policy.decide(component=RoutingComponent.EMBEDDINGS, context={})
    assert decision.selected_provider == "ollama"
    assert decision.selected_model == "bge-m3"


def test_visual_local_first_with_optional_cloud_backup() -> None:
    policy = ModelRoutingPolicy(
        settings=_settings(
            allow_cloud_models=True,
            openrouter_api_key="sk-test",
            enable_visual_cloud_backup=True,
        )
    )
    decision = policy.decide(component=RoutingComponent.VISUAL_ANALYSIS, context={})
    assert decision.selected_provider == "ollama"
    assert decision.fallback_chain[1]["provider"] == "openrouter"
