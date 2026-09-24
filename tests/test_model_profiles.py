from qa_ai.ai.model_profiles import (
    RoutingComponent,
    ModelPrivacyClass,
    ProviderKind,
    get_component_profiles,
    get_model_catalog,
)


def test_component_profiles_cover_required_components() -> None:
    profiles = get_component_profiles()
    expected = {
        RoutingComponent.MASTER_ORCHESTRATION,
        RoutingComponent.HUGE_REPO_REASONING,
        RoutingComponent.STRUCTURED_REASONING,
        RoutingComponent.LONG_STRATEGY,
        RoutingComponent.REPORT_SYNTHESIS,
        RoutingComponent.VISUAL_ANALYSIS,
        RoutingComponent.EMBEDDINGS,
        RoutingComponent.DETERMINISTIC_FALLBACK,
    }
    assert expected.issubset(set(profiles.keys()))


def test_cloud_first_specialist_models_mapped_by_component() -> None:
    profiles = get_component_profiles()
    assert profiles[RoutingComponent.MASTER_ORCHESTRATION].primary_model_id == "openrouter:nousresearch/hermes-3-llama-3.1-405b:free"
    assert profiles[RoutingComponent.HUGE_REPO_REASONING].primary_model_id == "openrouter:deepseek/deepseek-v4-flash:free"
    assert profiles[RoutingComponent.STRUCTURED_REASONING].primary_model_id == "openrouter:openai/gpt-oss-120b:free"
    assert profiles[RoutingComponent.LONG_STRATEGY].primary_model_id == "openrouter:arcee-ai/trinity-large-thinking:free"
    assert profiles[RoutingComponent.REPORT_SYNTHESIS].primary_model_id == "openrouter:google/gemma-4-31b-it:free"


def test_embeddings_are_local_only() -> None:
    catalog = get_model_catalog()
    bge = catalog["ollama:bge-m3"]
    assert bge.provider == ProviderKind.OLLAMA
    assert bge.privacy_class == ModelPrivacyClass.LOCAL_ONLY


def test_no_size_based_routing_labels_present() -> None:
    profiles = get_component_profiles()
    labels = {component.value for component in profiles.keys()}
    assert "small" not in labels
    assert "medium" not in labels
    assert "large" not in labels
