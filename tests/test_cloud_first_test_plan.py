"""AI test-plan generation uses a configured cloud provider without requiring a ready local Ollama model.

Same bug class fixed for evidence evaluation and root-cause suggestions (test_cloud_first_ai_features.py):
the local-model readiness gate blocked the call entirely, so a configured Gemini/Groq key was never tried.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from qa_ai.ai import test_plan_generator as test_plan_module
from qa_ai.ai.llm_router import LLMRouter
from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.openrouter_client import OpenRouterResult
from qa_ai.ai.test_plan_generator import AITestPlanGenerator
from qa_ai.config.settings import Settings
from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.storage import ProductStorage

CLOUD_ON = {"allow_cloud_models": True, "model_routing_mode": "specialist_cloud_first"}

PLAN_JSON = json.dumps({
    "test_cases": [
        {
            "title": "Cloud-generated case",
            "confidence": 0.9,
            "rationale": "from the cloud model",
            "test_steps": [
                {"action_type": "navigate", "target": "/", "confidence": 0.9, "rationale": "r"},
            ],
        }
    ]
})


class _Cloud:
    def __init__(self, content: str, succeed: bool = True) -> None:
        self.content, self.succeed, self.calls = content, succeed, []

    def chat_json(self, model, prompt, system=None, temperature=0.1, schema_hint=None):
        self.calls.append((model, prompt))
        if not self.succeed:
            return OpenRouterResult(False, "", model, "gemini", 1.0, "rate_limited", "rate_limited")
        return OpenRouterResult(True, self.content, model, "gemini", 1.0)

    chat = chat_json


class _Local:
    """Stands in for OllamaClient: chat_json returns a parsed dict, like the real client."""

    def __init__(self, raise_on_chat: bool = True) -> None:
        self.raise_on_chat = raise_on_chat
        self.calls = []

    def chat(self, model, prompt, system=None, temperature=0.2):
        self.calls.append(prompt)
        if self.raise_on_chat:
            raise ConnectionError("ollama is not running")
        return PLAN_JSON

    def chat_json(self, model, prompt, system=None, temperature=0.1):
        self.calls.append(prompt)
        if self.raise_on_chat:
            raise ConnectionError("ollama is not running")
        return json.loads(PLAN_JSON)

    def embed(self, model, text):
        return [0.0]


def _settings(**overrides) -> Settings:
    return replace(Settings(), **overrides)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "QA_AI_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "QA_AI_GROQ_API_KEY", "GROQ_API_KEY",
        "QA_AI_OPENROUTER_API_KEY", "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def test_env(tmp_path: Path):
    db_path = str(tmp_path / "test_ai.db")
    artifacts_dir = str(tmp_path / "artifacts")
    app = create_product_app(artifacts_dir=artifacts_dir, db_path=db_path)
    storage = ProductStorage(db_path)
    with TestClient(app) as client:
        proj = client.post("/api/projects", json={"name": "Test Project", "description": ""}).json()
        pack = client.post("/api/validation-packs", json={
            "project_id": proj["id"], "name": "Cloud Pack", "description": "",
        }).json()
        yield storage, pack


def _wire_cloud(generator: AITestPlanGenerator, settings: Settings, cloud: _Cloud, local: _Local) -> None:
    router = LLMRouter(client=local)
    router.specialist_router = ModelRouter(settings=settings, ollama_client=local, cloud_clients={"gemini": cloud})
    generator.router = router


def test_uses_the_cloud_model_when_ollama_is_down(test_env) -> None:
    storage, pack = test_env
    generator = AITestPlanGenerator(storage)
    cloud, local = _Cloud(PLAN_JSON), _Local(raise_on_chat=True)
    _wire_cloud(generator, _settings(**CLOUD_ON, gemini_api_key="g"), cloud, local)

    with patch.object(test_plan_module, "check_ollama_health") as health:
        preview = generator.generate_preview(pack["id"])

    assert preview.generation_source == "gemini"
    assert preview.test_cases[0].title == "Cloud-generated case"
    assert len(cloud.calls) == 1
    health.assert_not_called()  # the local-model gate is skipped when the cloud will answer


@pytest.mark.parametrize(
    "settings_overrides",
    [
        {},  # cloud not configured
        {**CLOUD_ON},  # cloud on but no key
        {**CLOUD_ON, "gemini_api_key": "g", "private_code_mode": True, "redact_cloud_context": True},  # prompt withheld
    ],
)
def test_keeps_the_local_gate_when_the_cloud_would_not_get_the_prompt(test_env, settings_overrides) -> None:
    storage, pack = test_env
    generator = AITestPlanGenerator(storage)
    cloud, local = _Cloud(PLAN_JSON), _Local(raise_on_chat=True)
    _wire_cloud(generator, _settings(**settings_overrides), cloud, local)

    with patch.object(test_plan_module, "check_ollama_health", return_value=(False, None, "down")) as health:
        preview = generator.generate_preview(pack["id"])

    assert preview.generation_source == "local_fallback"
    assert cloud.calls == []
    health.assert_called()


def test_falls_through_to_local_ollama_when_cloud_fails(test_env) -> None:
    storage, pack = test_env
    generator = AITestPlanGenerator(storage)
    cloud, local = _Cloud(PLAN_JSON, succeed=False), _Local(raise_on_chat=False)
    _wire_cloud(generator, _settings(**CLOUD_ON, gemini_api_key="g"), cloud, local)

    preview = generator.generate_preview(pack["id"])

    assert preview.generation_source == "ollama"
    # Primary Gemini model, then the lighter Gemini backup (both fail), then the local model answers.
    assert len(cloud.calls) == 2 and len(local.calls) == 1


def test_mocked_llm_router_is_unaffected_by_the_cloud_gate(test_env) -> None:
    """A test that replaces LLMRouter.generate_test_plan entirely (the existing test style) must keep
    working exactly as before: the extra parameter is ignored and the local-model check is skipped
    the same way it always was for a Mock."""
    storage, pack = test_env
    generator = AITestPlanGenerator(storage)

    with patch("qa_ai.ai.llm_router.LLMRouter.generate_test_plan", return_value=PLAN_JSON) as mock_gen:
        preview = generator.generate_preview(pack["id"])

    assert preview.generation_source == "ollama"
    mock_gen.assert_called_once()
    assert mock_gen.call_args[0][0]  # the prompt is still the first positional argument


def test_no_state_leaks_between_calls_on_a_shared_router(test_env) -> None:
    """generate_test_plan reports its provider through a dict the CALLER owns, not state on the
    router, so a second call on the same router instance cannot see a stale provider from the first."""
    storage, pack = test_env
    generator = AITestPlanGenerator(storage)
    cloud, local = _Cloud(PLAN_JSON), _Local(raise_on_chat=True)
    _wire_cloud(generator, _settings(**CLOUD_ON, gemini_api_key="g"), cloud, local)

    first = generator.generate_preview(pack["id"])
    assert first.generation_source == "gemini"

    # Second call, same router instance, cloud now unconfigured (so the local-model gate applies):
    # must not report "gemini" again just because the first call did.
    generator.router.specialist_router = ModelRouter(settings=_settings(), ollama_client=_Local(raise_on_chat=False))
    with patch.object(test_plan_module, "check_ollama_health", return_value=(True, None, None)), \
         patch.object(test_plan_module, "probe_ollama_chat_ready", return_value=(True, None)):
        second = generator.generate_preview(pack["id"])
    assert second.generation_source == "ollama"
