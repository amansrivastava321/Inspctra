"""Every prompt the router sends to a cloud provider has credentials stripped; local prompts are untouched."""

from __future__ import annotations

from dataclasses import replace

import pytest

from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.openrouter_client import OpenRouterResult
from qa_ai.ai.prompt_safety import make_safe, redact_secrets
from qa_ai.config.settings import Settings

GOOGLE_KEY = "AIza" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r"
GROQ_KEY = "gsk_" + "a1B2c3D4e5F6g7H8i9J0k1L2"
OPENAI_KEY = "sk-" + "proj1234567890abcdefghijkl"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r"
DB_URL = "postgres://admin:hunter2pass@db.internal:5432/app"
SECRETS = [GOOGLE_KEY, GROQ_KEY, OPENAI_KEY, JWT, "hunter2pass"]

CLOUD_ON = {"allow_cloud_models": True, "model_routing_mode": "specialist_cloud_first"}


# ── redact_secrets ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text, secret",
    [
        (f"google key {GOOGLE_KEY}", GOOGLE_KEY),
        (f"groq key {GROQ_KEY}", GROQ_KEY),
        (f"openai key {OPENAI_KEY}", OPENAI_KEY),
        (f"session {JWT}", JWT),
        (f"Authorization: Bearer {OPENAI_KEY}", OPENAI_KEY),
        (f"connect to {DB_URL}", "hunter2pass"),
        ("password = hunter2pass", "hunter2pass"),
    ],
)
def test_known_credentials_are_removed(text: str, secret: str) -> None:
    assert secret not in redact_secrets(text)


def test_text_without_credentials_is_returned_unchanged() -> None:
    text = "Login page returns 500 on POST /api/login\n  at handler (app.py:42)"

    assert redact_secrets(text) == text


def test_commit_hashes_and_long_digests_survive() -> None:
    """The generic long-token rule in make_safe() also eats these; redact_secrets must not."""
    digest = "9fceb02d0ae598e95dc970b74767f19372d61af8" + "0123456789abcdef"

    assert redact_secrets(f"regressed in {digest}") == f"regressed in {digest}"
    assert digest not in make_safe(f"regressed in {digest}").safe_prompt


def test_long_prompts_are_not_truncated() -> None:
    text = "line of log output\n" * 2_000

    assert redact_secrets(text) == text


def test_private_key_blocks_are_removed() -> None:
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"

    out = redact_secrets(f"before\n{pem}\nafter")

    assert "MIIEowIBAAKCAQEA" not in out and "before" in out and "after" in out


# ── router ───────────────────────────────────────────────────────────────────

class _Cloud:
    def __init__(self, provider: str, succeed: bool = True) -> None:
        self.provider, self.succeed, self.prompts = provider, succeed, []

    def _result(self, model: str, prompt: str) -> OpenRouterResult:
        self.prompts.append(prompt)
        if not self.succeed:
            return OpenRouterResult(False, "", model, self.provider, 1.0, "rate_limited", "rate_limited")
        return OpenRouterResult(True, "ok", model, self.provider, 1.0)

    def chat(self, model, prompt, system=None, temperature=0.1):
        return self._result(model, prompt)

    def chat_json(self, model, prompt, system=None, temperature=0.1, schema_hint=None):
        return self._result(model, prompt)


class _Local:
    def __init__(self) -> None:
        self.prompts = []

    def chat(self, model, prompt, system=None, temperature=0.2):
        self.prompts.append(prompt)
        return "local"

    def chat_json(self, model, prompt, system=None, temperature=0.1):
        self.prompts.append(prompt)
        return {"ok": True}

    def embed(self, model, text):
        return [0.0]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "QA_AI_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "QA_AI_GROQ_API_KEY", "GROQ_API_KEY",
        "QA_AI_OPENROUTER_API_KEY", "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def _settings(**overrides) -> Settings:
    return replace(Settings(), **{**CLOUD_ON, **overrides})


PROMPT = f"Why does login fail? env GOOGLE={GOOGLE_KEY} GROQ={GROQ_KEY} OPENAI={OPENAI_KEY} DB={DB_URL}"


@pytest.mark.parametrize(
    "provider, setting",
    [("gemini", "gemini_api_key"), ("groq", "groq_api_key"), ("openrouter", "openrouter_api_key")],
)
def test_prompt_is_redacted_for_every_cloud_provider(provider: str, setting: str) -> None:
    cloud = _Cloud(provider)
    router = ModelRouter(
        settings=_settings(**{setting: "key"}), ollama_client=_Local(), cloud_clients={provider: cloud}
    )

    result = router.route(RoutingComponent.STRUCTURED_REASONING, PROMPT, {})

    assert result.provider == provider
    sent = cloud.prompts[0]
    assert not any(secret in sent for secret in SECRETS)
    assert "Why does login fail?" in sent


def test_redaction_applies_on_every_cloud_attempt_in_the_fallback_chain() -> None:
    gemini, groq = _Cloud("gemini", succeed=False), _Cloud("groq")
    router = ModelRouter(
        settings=_settings(gemini_api_key="g", groq_api_key="q"),
        ollama_client=_Local(),
        cloud_clients={"gemini": gemini, "groq": groq},
    )

    router.route(RoutingComponent.STRUCTURED_REASONING, PROMPT, {})

    for sent in gemini.prompts + groq.prompts:
        assert not any(secret in sent for secret in SECRETS)
    assert len(gemini.prompts) == len(groq.prompts) == 1


def test_graphify_summary_sent_in_private_mode_is_redacted_too() -> None:
    gemini = _Cloud("gemini")
    router = ModelRouter(
        settings=_settings(
            gemini_api_key="g", private_code_mode=True, redact_cloud_context=True,
            require_cloud_permission_for_private_code=False,
        ),
        ollama_client=_Local(),
        cloud_clients={"gemini": gemini},
    )

    router.route(
        RoutingComponent.MASTER_ORCHESTRATION, "raw source",
        {"contains_private_code": True, "graphify_summary": f"module uses {GOOGLE_KEY}"},
    )

    assert GOOGLE_KEY not in gemini.prompts[0] and "raw source" not in gemini.prompts[0]


def test_local_models_still_receive_the_prompt_unchanged() -> None:
    """Nothing leaves the machine on the local path, so the model keeps full context."""
    local = _Local()
    router = ModelRouter(settings=replace(Settings(), allow_cloud_models=False), ollama_client=local)

    router.route(RoutingComponent.STRUCTURED_REASONING, PROMPT, {})

    assert local.prompts == [PROMPT]
