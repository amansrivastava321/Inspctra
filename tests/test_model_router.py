from dataclasses import replace

from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.openrouter_client import OpenRouterResult
from qa_ai.config.settings import Settings


class _FakeOpenRouter:
    def __init__(self, result: OpenRouterResult):
        self._result = result
        self.calls = []

    def chat(self, model: str, prompt: str, system=None, temperature=0.1):
        self.calls.append((model, prompt))
        return self._result

    def chat_json(self, model: str, prompt: str, system=None, temperature=0.1, schema_hint=None):
        self.calls.append((model, prompt))
        return self._result


class _FakeOllama:
    def __init__(self):
        self.chat_calls = []

    def chat(self, model: str, prompt: str, system=None, temperature=0.2):
        self.chat_calls.append((model, prompt))
        return "local-ok"

    def chat_json(self, model: str, prompt: str, system=None, temperature=0.1):
        self.chat_calls.append((model, prompt))
        return {"ok": True}

    def embed(self, model: str, text: str):
        return [0.1, 0.2]


class _AlwaysFailOllama(_FakeOllama):
    def chat(self, model: str, prompt: str, system=None, temperature=0.2):
        raise RuntimeError("local fail")



def _settings(**overrides):
    s = Settings()
    for k, v in overrides.items():
        s = replace(s, **{k: v})
    return s


def test_router_prefers_openrouter_then_local_fallback():
    settings = _settings(
        allow_cloud_models=True,
        openrouter_api_key="sk-test",
        private_code_mode=False,
        model_routing_mode="specialist_cloud_first",
    )
    openrouter = _FakeOpenRouter(
        OpenRouterResult(
            success=False,
            content="",
            model="openai/gpt-oss-120b:free",
            provider="openrouter",
            latency_ms=10.0,
            error_type="rate_limited",
            fallback_reason="rate_limited",
        )
    )
    ollama = _FakeOllama()
    router = ModelRouter(settings=settings, openrouter_client=openrouter, ollama_client=ollama)
    result = router.route(component=RoutingComponent.STRUCTURED_REASONING, prompt="hello", context={})
    assert result.success is True
    assert result.provider == "ollama"
    assert openrouter.calls
    assert ollama.chat_calls


def test_router_uses_deterministic_fallback_when_cloud_and_local_fail():
    settings = _settings(allow_cloud_models=True, openrouter_api_key="sk-test", private_code_mode=False)
    openrouter = _FakeOpenRouter(
        OpenRouterResult(
            success=False,
            content="",
            model="openai/gpt-oss-120b:free",
            provider="openrouter",
            latency_ms=10.0,
            error_type="provider_unavailable",
            fallback_reason="provider_unavailable",
        )
    )
    router = ModelRouter(settings=settings, openrouter_client=openrouter, ollama_client=_AlwaysFailOllama())
    result = router.route(
        component=RoutingComponent.STRUCTURED_REASONING,
        prompt="hello",
        context={},
        deterministic_fallback=lambda: "deterministic",
    )
    assert result.success is True
    assert result.provider == "deterministic"
    assert result.content == "deterministic"


def test_route_embedding_always_local():
    settings = _settings(allow_cloud_models=True, openrouter_api_key="sk-test")
    openrouter = _FakeOpenRouter(
        OpenRouterResult(success=True, content="cloud", model="x", provider="openrouter", latency_ms=1.0)
    )
    router = ModelRouter(settings=settings, openrouter_client=openrouter, ollama_client=_FakeOllama())
    vectors = router.route_embedding(["a", "b"])
    assert len(vectors) == 2
    assert openrouter.calls == []
