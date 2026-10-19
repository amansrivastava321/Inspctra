"""
model_profiles.py - Specialist model catalog and component routing profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set


class RoutingComponent(str, Enum):
    MASTER_ORCHESTRATION = "master_orchestration"
    HUGE_REPO_REASONING = "huge_repo_reasoning"
    STRUCTURED_REASONING = "structured_reasoning"
    LONG_STRATEGY = "long_strategy"
    REPORT_SYNTHESIS = "report_synthesis"
    VISUAL_ANALYSIS = "visual_analysis"
    EMBEDDINGS = "embeddings"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


class ProviderKind(str, Enum):
    OPENROUTER = "openrouter"
    GEMINI = "gemini"
    GROQ = "groq"
    OLLAMA = "ollama"
    DETERMINISTIC = "deterministic"


# Providers that send prompts off the machine (everything except Ollama and the deterministic fallback).
CLOUD_PROVIDER_KINDS = frozenset({ProviderKind.OPENROUTER, ProviderKind.GEMINI, ProviderKind.GROQ})
CLOUD_PROVIDER_NAMES = frozenset(kind.value for kind in CLOUD_PROVIDER_KINDS)


class ModelPrivacyClass(str, Enum):
    CLOUD_ALLOWED = "cloud_allowed"
    LOCAL_ONLY = "local_only"


@dataclass(frozen=True)
class ModelDefinition:
    model_id: str
    provider: ProviderKind
    model_name: str
    capabilities: Set[str] = field(default_factory=set)
    privacy_class: ModelPrivacyClass = ModelPrivacyClass.CLOUD_ALLOWED


@dataclass(frozen=True)
class ComponentProfile:
    component: RoutingComponent
    primary_model_id: str
    fallback_model_ids: List[str]


def get_model_catalog() -> Dict[str, ModelDefinition]:
    return {
        "openrouter:nousresearch/hermes-3-llama-3.1-405b:free": ModelDefinition(
            model_id="openrouter:nousresearch/hermes-3-llama-3.1-405b:free",
            provider=ProviderKind.OPENROUTER,
            model_name="nousresearch/hermes-3-llama-3.1-405b:free",
            capabilities={"orchestration"},
            privacy_class=ModelPrivacyClass.CLOUD_ALLOWED,
        ),
        "openrouter:deepseek/deepseek-v4-flash:free": ModelDefinition(
            model_id="openrouter:deepseek/deepseek-v4-flash:free",
            provider=ProviderKind.OPENROUTER,
            model_name="deepseek/deepseek-v4-flash:free",
            capabilities={"repo_reasoning"},
            privacy_class=ModelPrivacyClass.CLOUD_ALLOWED,
        ),
        "openrouter:openai/gpt-oss-120b:free": ModelDefinition(
            model_id="openrouter:openai/gpt-oss-120b:free",
            provider=ProviderKind.OPENROUTER,
            model_name="openai/gpt-oss-120b:free",
            capabilities={"tool_json"},
            privacy_class=ModelPrivacyClass.CLOUD_ALLOWED,
        ),
        "openrouter:arcee-ai/trinity-large-thinking:free": ModelDefinition(
            model_id="openrouter:arcee-ai/trinity-large-thinking:free",
            provider=ProviderKind.OPENROUTER,
            model_name="arcee-ai/trinity-large-thinking:free",
            capabilities={"long_reasoning"},
            privacy_class=ModelPrivacyClass.CLOUD_ALLOWED,
        ),
        "openrouter:google/gemma-4-31b-it:free": ModelDefinition(
            model_id="openrouter:google/gemma-4-31b-it:free",
            provider=ProviderKind.OPENROUTER,
            model_name="google/gemma-4-31b-it:free",
            capabilities={"report", "visual"},
            privacy_class=ModelPrivacyClass.CLOUD_ALLOWED,
        ),
        # Optional direct providers. Used only when the user has configured a key and opted in to cloud
        # models; the model names here are defaults that QA_AI_GEMINI_MODEL / QA_AI_GROQ_MODEL override.
        "gemini:gemini-2.5-pro": ModelDefinition(
            model_id="gemini:gemini-2.5-pro",
            provider=ProviderKind.GEMINI,
            model_name="gemini-2.5-pro",
            capabilities={"orchestration", "repo_reasoning", "long_reasoning", "tool_json", "report"},
            privacy_class=ModelPrivacyClass.CLOUD_ALLOWED,
        ),
        "groq:llama-3.3-70b-versatile": ModelDefinition(
            model_id="groq:llama-3.3-70b-versatile",
            provider=ProviderKind.GROQ,
            model_name="llama-3.3-70b-versatile",
            capabilities={"orchestration", "repo_reasoning", "tool_json", "report"},
            privacy_class=ModelPrivacyClass.CLOUD_ALLOWED,
        ),
        "ollama:qwen3.5:9b": ModelDefinition(
            model_id="ollama:qwen3.5:9b",
            provider=ProviderKind.OLLAMA,
            model_name="qwen3.5:9b",
            capabilities={"orchestration", "repo_reasoning", "tool_json"},
            privacy_class=ModelPrivacyClass.LOCAL_ONLY,
        ),
        "ollama:deepseek-r1:7b": ModelDefinition(
            model_id="ollama:deepseek-r1:7b",
            provider=ProviderKind.OLLAMA,
            model_name="deepseek-r1:7b",
            capabilities={"repo_reasoning", "long_reasoning"},
            privacy_class=ModelPrivacyClass.LOCAL_ONLY,
        ),
        "ollama:gemma4:e4b": ModelDefinition(
            model_id="ollama:gemma4:e4b",
            provider=ProviderKind.OLLAMA,
            model_name="gemma4:e4b",
            capabilities={"report"},
            privacy_class=ModelPrivacyClass.LOCAL_ONLY,
        ),
        "ollama:qwen2.5vl:7b": ModelDefinition(
            model_id="ollama:qwen2.5vl:7b",
            provider=ProviderKind.OLLAMA,
            model_name="qwen2.5vl:7b",
            capabilities={"visual"},
            privacy_class=ModelPrivacyClass.LOCAL_ONLY,
        ),
        "ollama:bge-m3": ModelDefinition(
            model_id="ollama:bge-m3",
            provider=ProviderKind.OLLAMA,
            model_name="bge-m3",
            capabilities={"embedding"},
            privacy_class=ModelPrivacyClass.LOCAL_ONLY,
        ),
    }


# Tried before a component's own cloud models when the provider is configured: the strongest
# reasoner first for hard reasoning, the fastest first for report synthesis.
_REASONING_FIRST = ["gemini:gemini-2.5-pro", "groq:llama-3.3-70b-versatile"]
_SPEED_FIRST = ["groq:llama-3.3-70b-versatile", "gemini:gemini-2.5-pro"]


def get_preferred_cloud_model_ids() -> Dict[RoutingComponent, List[str]]:
    return {
        RoutingComponent.MASTER_ORCHESTRATION: list(_REASONING_FIRST),
        RoutingComponent.HUGE_REPO_REASONING: list(_REASONING_FIRST),
        RoutingComponent.STRUCTURED_REASONING: list(_REASONING_FIRST),
        RoutingComponent.LONG_STRATEGY: list(_REASONING_FIRST),
        RoutingComponent.REPORT_SYNTHESIS: list(_SPEED_FIRST),
    }


def get_component_profiles() -> Dict[RoutingComponent, ComponentProfile]:
    return {
        RoutingComponent.MASTER_ORCHESTRATION: ComponentProfile(
            component=RoutingComponent.MASTER_ORCHESTRATION,
            primary_model_id="openrouter:nousresearch/hermes-3-llama-3.1-405b:free",
            fallback_model_ids=["ollama:qwen3.5:9b"],
        ),
        RoutingComponent.HUGE_REPO_REASONING: ComponentProfile(
            component=RoutingComponent.HUGE_REPO_REASONING,
            primary_model_id="openrouter:deepseek/deepseek-v4-flash:free",
            fallback_model_ids=["ollama:deepseek-r1:7b", "ollama:qwen3.5:9b"],
        ),
        RoutingComponent.STRUCTURED_REASONING: ComponentProfile(
            component=RoutingComponent.STRUCTURED_REASONING,
            primary_model_id="openrouter:openai/gpt-oss-120b:free",
            fallback_model_ids=["ollama:qwen3.5:9b"],
        ),
        RoutingComponent.LONG_STRATEGY: ComponentProfile(
            component=RoutingComponent.LONG_STRATEGY,
            primary_model_id="openrouter:arcee-ai/trinity-large-thinking:free",
            fallback_model_ids=["ollama:deepseek-r1:7b"],
        ),
        RoutingComponent.REPORT_SYNTHESIS: ComponentProfile(
            component=RoutingComponent.REPORT_SYNTHESIS,
            primary_model_id="openrouter:google/gemma-4-31b-it:free",
            fallback_model_ids=["ollama:gemma4:e4b"],
        ),
        RoutingComponent.VISUAL_ANALYSIS: ComponentProfile(
            component=RoutingComponent.VISUAL_ANALYSIS,
            primary_model_id="ollama:qwen2.5vl:7b",
            fallback_model_ids=["openrouter:google/gemma-4-31b-it:free"],
        ),
        RoutingComponent.EMBEDDINGS: ComponentProfile(
            component=RoutingComponent.EMBEDDINGS,
            primary_model_id="ollama:bge-m3",
            fallback_model_ids=[],
        ),
        RoutingComponent.DETERMINISTIC_FALLBACK: ComponentProfile(
            component=RoutingComponent.DETERMINISTIC_FALLBACK,
            primary_model_id="",
            fallback_model_ids=[],
        ),
    }
