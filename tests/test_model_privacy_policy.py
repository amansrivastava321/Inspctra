from dataclasses import replace

from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.openrouter_client import OpenRouterResult
from qa_ai.config.settings import Settings


class _CloudRecorder:
    def __init__(self):
        self.calls = []

    def chat(self, model: str, prompt: str, system=None, temperature=0.1):
        self.calls.append(prompt)
        return OpenRouterResult(success=True, content="cloud-ok", model=model, provider="openrouter", latency_ms=1.0)

    def chat_json(self, model: str, prompt: str, system=None, temperature=0.1, schema_hint=None):
        self.calls.append(prompt)
        return OpenRouterResult(success=True, content='{"ok":true}', model=model, provider="openrouter", latency_ms=1.0)


class _Local:
    def chat(self, model: str, prompt: str, system=None, temperature=0.2):
        return "local"

    def chat_json(self, model: str, prompt: str, system=None, temperature=0.1):
        return {"ok": True}

    def embed(self, model: str, text: str):
        return [0.0]


def _settings(**overrides):
    s = Settings()
    for k, v in overrides.items():
        s = replace(s, **{k: v})
    return s


def test_private_code_without_permission_blocks_cloud_calls():
    cloud = _CloudRecorder()
    router = ModelRouter(
        settings=_settings(
            allow_cloud_models=False,
            private_code_mode=True,
            require_cloud_permission_for_private_code=True,
            openrouter_api_key="sk-test",
        ),
        openrouter_client=cloud,
        ollama_client=_Local(),
    )
    result = router.route(
        component=RoutingComponent.MASTER_ORCHESTRATION,
        prompt="sensitive code",
        context={"contains_private_code": True},
    )
    assert result.provider == "ollama"
    assert cloud.calls == []


def test_redaction_mode_sends_redacted_context_to_cloud():
    cloud = _CloudRecorder()
    router = ModelRouter(
        settings=_settings(
            allow_cloud_models=True,
            private_code_mode=True,
            redact_cloud_context=True,
            require_cloud_permission_for_private_code=False,
            openrouter_api_key="sk-test",
            model_routing_mode="specialist_cloud_first",
        ),
        openrouter_client=cloud,
        ollama_client=_Local(),
    )
    router.route(
        component=RoutingComponent.MASTER_ORCHESTRATION,
        prompt="raw secret text",
        context={"contains_private_code": True, "graphify_summary": "safe summary"},
    )
    assert cloud.calls
    assert "raw secret text" not in cloud.calls[0]
    assert "safe summary" in cloud.calls[0]
