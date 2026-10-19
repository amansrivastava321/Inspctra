"""Gemini and Groq are optional cloud providers behind the same opt-in and redaction gates."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
import requests

from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.model_routing_policy import ModelRoutingPolicy
from qa_ai.ai.openrouter_client import OpenRouterClient, OpenRouterResult
from qa_ai.ai.prompt_safety import make_safe
from qa_ai.config.settings import Settings, cloud_provider_keys

_KEY_ENV_VARS = (
    "QA_AI_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "QA_AI_GROQ_API_KEY", "GROQ_API_KEY",
    "QA_AI_OPENROUTER_API_KEY", "QA_AI_GEMINI_MODEL", "QA_AI_GROQ_MODEL",
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _KEY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _settings(**overrides) -> Settings:
    return replace(Settings(), **overrides)


CLOUD_ON = {"allow_cloud_models": True, "model_routing_mode": "specialist_cloud_first"}


def _chain(settings: Settings, component: RoutingComponent = RoutingComponent.STRUCTURED_REASONING):
    decision = ModelRoutingPolicy(settings=settings).decide(component, {})
    return decision.reason, [f"{e['provider']}:{e['model']}" for e in decision.fallback_chain]


# ── settings ─────────────────────────────────────────────────────────────────

def test_no_keys_means_no_cloud_providers() -> None:
    assert cloud_provider_keys(Settings()) == {}


def test_keys_are_read_from_the_usual_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("GROQ_API_KEY", "q-key")

    assert cloud_provider_keys(Settings()) == {"gemini": "g-key", "groq": "q-key"}


def test_project_specific_variable_wins_over_the_generic_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "generic")
    monkeypatch.setenv("QA_AI_GEMINI_API_KEY", "specific")

    assert Settings().gemini_api_key == "specific"


def test_google_api_key_is_accepted_for_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "from-google")

    assert Settings().gemini_api_key == "from-google"


# ── routing policy ───────────────────────────────────────────────────────────

def test_behaviour_is_unchanged_without_the_new_keys() -> None:
    assert _chain(_settings(**CLOUD_ON, openrouter_api_key="k")) == (
        "cloud_first_specialist", ["openrouter:openai/gpt-oss-120b:free", "ollama:qwen3.5:9b"],
    )
    assert _chain(_settings(**CLOUD_ON)) == ("missing_cloud_api_key", ["ollama:qwen3.5:9b"])


def test_gemini_is_tried_first_for_reasoning_when_configured() -> None:
    reason, chain = _chain(_settings(**CLOUD_ON, gemini_api_key="k"))

    assert reason == "cloud_first_specialist"
    assert chain == ["gemini:gemini-3.8-flash", "ollama:qwen3.5:9b"]


def test_every_configured_provider_appears_in_preference_order() -> None:
    _, chain = _chain(_settings(**CLOUD_ON, gemini_api_key="g", groq_api_key="q", openrouter_api_key="o"))

    assert chain == [
        "gemini:gemini-3.8-flash", "groq:openai/gpt-oss-120b", "openrouter:openai/gpt-oss-120b:free", "ollama:qwen3.5:9b",
    ]


def test_groq_leads_for_report_synthesis_where_speed_matters() -> None:
    _, chain = _chain(_settings(**CLOUD_ON, gemini_api_key="g", groq_api_key="q"), RoutingComponent.REPORT_SYNTHESIS)

    assert chain[:2] == ["groq:openai/gpt-oss-120b", "gemini:gemini-3.8-flash"]


def test_model_names_can_be_overridden() -> None:
    _, chain = _chain(_settings(**CLOUD_ON, gemini_api_key="g", gemini_model="gemini-2.5-flash"))

    assert chain[0] == "gemini:gemini-2.5-flash"


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"allow_cloud_models": False}, "cloud_models_disabled"),
    ({"model_routing_mode": "local_first"}, "cloud_allowed"),
])
def test_cloud_stays_off_unless_explicitly_enabled(overrides: dict, reason: str) -> None:
    settings = _settings(**{**CLOUD_ON, **overrides}, gemini_api_key="g", groq_api_key="q")

    assert _chain(settings) == (reason, ["ollama:qwen3.5:9b"])


@pytest.mark.parametrize("component", [RoutingComponent.EMBEDDINGS, RoutingComponent.VISUAL_ANALYSIS])
def test_embeddings_and_vision_never_go_to_the_new_providers(component: RoutingComponent) -> None:
    _, chain = _chain(_settings(**CLOUD_ON, gemini_api_key="g", groq_api_key="q"), component)

    assert not any(entry.startswith(("gemini:", "groq:")) for entry in chain)


# ── router ───────────────────────────────────────────────────────────────────

class _Cloud:
    def __init__(self, provider: str, succeed: bool = True) -> None:
        self.provider, self.succeed, self.prompts = provider, succeed, []

    def _result(self, model: str, prompt: str) -> OpenRouterResult:
        self.prompts.append(prompt)
        if not self.succeed:
            return OpenRouterResult(False, "", model, self.provider, 1.0, "rate_limited", "rate_limited")
        return OpenRouterResult(True, "cloud-ok", model, self.provider, 1.0)

    def chat(self, model, prompt, system=None, temperature=0.1):
        return self._result(model, prompt)

    def chat_json(self, model, prompt, system=None, temperature=0.1, schema_hint=None):
        return self._result(model, prompt)


class _Local:
    def chat(self, model, prompt, system=None, temperature=0.2):
        return "local"

    def chat_json(self, model, prompt, system=None, temperature=0.1):
        return {"ok": True}

    def embed(self, model, text):
        return [0.0]


def _router(settings: Settings, **clients) -> ModelRouter:
    return ModelRouter(settings=settings, ollama_client=_Local(), cloud_clients=clients)


def test_router_calls_gemini_and_reports_the_provider() -> None:
    gemini = _Cloud("gemini")
    router = _router(_settings(**CLOUD_ON, gemini_api_key="g"), gemini=gemini)

    result = router.route(RoutingComponent.STRUCTURED_REASONING, "question", {})

    assert (result.success, result.provider, result.model) == (True, "gemini", "gemini-3.8-flash")
    assert gemini.prompts == ["question"]


def test_router_falls_back_from_gemini_to_groq_then_local() -> None:
    gemini, groq = _Cloud("gemini", succeed=False), _Cloud("groq", succeed=False)
    router = _router(_settings(**CLOUD_ON, gemini_api_key="g", groq_api_key="q"), gemini=gemini, groq=groq)

    result = router.route(RoutingComponent.STRUCTURED_REASONING, "question", {})

    assert (result.provider, len(gemini.prompts), len(groq.prompts)) == ("ollama", 1, 1)


def test_private_code_is_redacted_before_it_reaches_gemini_or_groq() -> None:
    gemini = _Cloud("gemini")
    router = _router(
        _settings(**CLOUD_ON, gemini_api_key="g", private_code_mode=True, redact_cloud_context=True,
                  require_cloud_permission_for_private_code=False),
        gemini=gemini,
    )

    router.route(RoutingComponent.MASTER_ORCHESTRATION, "raw secret source", {"contains_private_code": True, "graphify_summary": "safe summary"})

    assert "raw secret source" not in gemini.prompts[0] and "safe summary" in gemini.prompts[0]


def test_unconfigured_providers_get_no_client_and_are_never_called() -> None:
    router = ModelRouter(settings=_settings(**CLOUD_ON), ollama_client=_Local())

    assert set(router.cloud_clients) == {"openrouter"}


def test_configured_providers_get_their_own_endpoint() -> None:
    router = ModelRouter(settings=_settings(gemini_api_key="g", groq_api_key="q"), ollama_client=_Local())

    assert router.cloud_clients["gemini"].base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert router.cloud_clients["groq"].base_url == "https://api.groq.com/openai/v1"


def test_doctor_reports_which_cloud_providers_are_configured() -> None:
    report = _router(_settings(gemini_api_key="g")).doctor()

    assert (report["cloud_configured"], report["gemini_configured"], report["groq_configured"]) == (True, True, False)
    assert report["cloud_providers_configured"] == ["gemini"]
    assert "g" not in str(report.values()).replace("gemini", "")  # key values are never reported


# ── client ───────────────────────────────────────────────────────────────────

def _response(payload: dict, status: int = 200) -> MagicMock:
    response = MagicMock(status_code=status)
    response.json.return_value = payload
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"status={status}")
    return response


@pytest.mark.parametrize("provider", ["gemini", "groq"])
def test_client_posts_to_the_openai_compatible_endpoint_and_names_the_provider(provider: str) -> None:
    client = OpenRouterClient(api_key="secret", base_url="https://example.test/v1/", provider_name=provider)

    with patch("requests.post", return_value=_response({"choices": [{"message": {"content": "hi"}}]})) as post:
        result = client.chat(model="m", prompt="hello")

    assert (result.success, result.provider) == (True, provider)
    assert post.call_args.args[0] == "https://example.test/v1/chat/completions"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer secret"


def test_failures_are_attributed_to_the_provider_not_to_openrouter() -> None:
    client = OpenRouterClient(api_key="k", base_url="https://example.test/v1", max_retries=1, provider_name="groq")

    with patch("requests.post", return_value=_response({}, status=429)):
        limited = client.chat(model="m", prompt="x")
    missing_key = OpenRouterClient(api_key="", base_url="https://example.test/v1", provider_name="gemini").chat(model="m", prompt="x")

    assert (limited.provider, limited.error_type) == ("groq", "rate_limited")
    assert (missing_key.provider, missing_key.fallback_reason) == ("gemini", "missing_api_key")


# ── redaction ────────────────────────────────────────────────────────────────

def test_google_and_groq_keys_are_redacted_from_prompts() -> None:
    google_key = "AIza" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r"
    groq_key = "gsk_" + "a1B2c3D4e5F6g7H8i9J0k1L2"

    safe = make_safe(f"google={google_key} groq={groq_key}", private_mode=True, cloud_target=True)
    text = getattr(safe, "text", safe)

    assert google_key not in str(text) and groq_key not in str(text)
