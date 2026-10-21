"""AI features use a configured cloud provider without requiring a ready local Ollama model.

Evidence evaluation and root-cause suggestions used to probe a specific local model first and fall back
to the built-in logic when it was missing, so configured Gemini/Groq keys were never tried.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from qa_ai.ai import evidence_evaluator as evidence_module
from qa_ai.ai import root_cause_suggester as rca_module
from qa_ai.ai.evidence_evaluator import AIEvidenceEvaluator
from qa_ai.ai.llm_router import ModelCapability
from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.openrouter_client import OpenRouterResult
from qa_ai.ai.root_cause_suggester import AIRootCauseSuggester
from qa_ai.config.settings import Settings
from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.models import LiveRunRecord
from qa_ai.product_backend.storage import ProductStorage

CLOUD_ON = {"allow_cloud_models": True, "model_routing_mode": "specialist_cloud_first"}
COMPONENT = RoutingComponent.STRUCTURED_REASONING

EVALUATION = {
    "verdict_assessment": "supports_verdict",
    "suggested_verdict": "fail",
    "confidence": 0.8,
    "summary": "Answered by the cloud model",
    "evidence_used": [],
    "missing_evidence": [],
    "risk_flags": [],
    "rationale": "ok",
}


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "QA_AI_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "QA_AI_GROQ_API_KEY", "GROQ_API_KEY",
        "QA_AI_OPENROUTER_API_KEY", "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


class _Cloud:
    def __init__(self, payload: dict) -> None:
        self.payload, self.calls = payload, []

    def chat_json(self, model, prompt, system=None, temperature=0.1, schema_hint=None):
        self.calls.append((model, prompt))
        return OpenRouterResult(True, json.dumps(self.payload), model, "gemini", 1.0)

    chat = chat_json


class _Local:
    def chat(self, model, prompt, system=None, temperature=0.2):
        raise ConnectionError("ollama is not running")

    chat_json = chat

    def embed(self, model, text):
        return [0.0]


def _settings(**overrides) -> Settings:
    return replace(Settings(), **overrides)


def _router(settings: Settings, cloud: _Cloud | None = None) -> ModelRouter:
    clients = {"gemini": cloud} if cloud else {}
    return ModelRouter(settings=settings, ollama_client=_Local(), cloud_clients=clients)


# ── ModelRouter.cloud_route_available ────────────────────────────────────────

@pytest.mark.parametrize(
    ("overrides", "context", "expected"),
    [
        ({**CLOUD_ON, "gemini_api_key": "g"}, {}, True),
        ({**CLOUD_ON}, {}, False),  # no key
        ({"allow_cloud_models": False, "gemini_api_key": "g"}, {}, False),
        ({"model_routing_mode": "local_first", "gemini_api_key": "g"}, {}, False),
        # private-code mode withholds the prompt, so a cloud model could not do the job
        ({**CLOUD_ON, "gemini_api_key": "g", "private_code_mode": True, "redact_cloud_context": True}, {}, False),
        ({**CLOUD_ON, "gemini_api_key": "g", "redact_cloud_context": True}, {"contains_private_code": True}, False),
        # private mode without redaction still sends the real prompt
        ({**CLOUD_ON, "gemini_api_key": "g", "private_code_mode": True, "redact_cloud_context": False}, {}, True),
    ],
)
def test_cloud_route_available_only_when_the_real_prompt_would_reach_a_cloud_model(
    overrides: dict, context: dict, expected: bool
) -> None:
    assert _router(_settings(**overrides)).cloud_route_available(COMPONENT, context) is expected


# ── evidence evaluation ──────────────────────────────────────────────────────

@pytest.fixture
def storage(tmp_path: Path) -> ProductStorage:
    return ProductStorage(db_path=str(tmp_path / "test.db"))


def _failed_run(storage: ProductStorage) -> str:
    run = LiveRunRecord(pack_id="p1", app_target_id="a1", status="failed")
    storage.create_run(run.model_dump())
    return run.id


def _no_ollama(monkeypatch: pytest.MonkeyPatch, module) -> MagicMock:
    health = MagicMock(return_value=(False, None, "connection refused"))
    monkeypatch.setattr(module, "check_ollama_health", health)
    monkeypatch.setattr(module, "probe_ollama_chat_ready", MagicMock(return_value=(False, "not installed")))
    return health


def test_evidence_evaluation_uses_the_cloud_model_when_ollama_is_down(storage, monkeypatch) -> None:
    run_id = _failed_run(storage)
    health = _no_ollama(monkeypatch, evidence_module)
    cloud = _Cloud(EVALUATION)
    evaluator = AIEvidenceEvaluator(storage)
    monkeypatch.setattr(evaluator.router, "specialist_router", _router(_settings(**CLOUD_ON, gemini_api_key="g"), cloud))

    note = evaluator.evaluate_run(run_id)

    assert note["generation_source"] == "gemini"
    assert note["summary"] == "Answered by the cloud model"
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
def test_evidence_evaluation_keeps_the_local_gate_when_the_cloud_would_not_get_the_prompt(
    storage, monkeypatch, settings_overrides
) -> None:
    run_id = _failed_run(storage)
    health = _no_ollama(monkeypatch, evidence_module)
    cloud = _Cloud(EVALUATION)
    evaluator = AIEvidenceEvaluator(storage)
    monkeypatch.setattr(evaluator.router, "specialist_router", _router(_settings(**settings_overrides), cloud))

    note = evaluator.evaluate_run(run_id)

    assert note["generation_source"] == "local_fallback"
    assert cloud.calls == []
    health.assert_called()


# ── root-cause suggestions ───────────────────────────────────────────────────

def _suggester(tmp_path: Path, specialist: ModelRouter) -> tuple[AIRootCauseSuggester, str]:
    storage = ProductStorage(str(tmp_path / "rca.db"))
    index = ArtifactIndex(tmp_path / "artifacts")
    run = LiveRunRecord(id="run-1", pack_id="p1", app_target_id="a1", status="failed", error="AssertionError")
    storage.create_run(run.model_dump())
    router = SimpleNamespace(
        client=SimpleNamespace(base_url="http://127.0.0.1:1"),
        model_registry={ModelCapability.QA_REASONING: [SimpleNamespace(name="qwen3.5:9b")]},
        specialist_router=specialist,
        _extract_json=lambda text: json.loads(text),
    )
    return AIRootCauseSuggester(storage, index, router=router), run.id


def test_root_cause_uses_the_cloud_model_when_ollama_is_down(tmp_path, monkeypatch) -> None:
    health = _no_ollama(monkeypatch, rca_module)
    cloud = _Cloud({"suggestions": []})
    suggester, run_id = _suggester(tmp_path, _router(_settings(**CLOUD_ON, gemini_api_key="g"), cloud))

    output = suggester._try_model(suggester.build_context(run_id))

    assert output == {"suggestions": []}
    assert len(cloud.calls) == 1
    assert suggester._last_model_metadata["provider"] == "gemini"
    health.assert_not_called()


def test_root_cause_keeps_the_local_gate_without_a_usable_cloud_route(tmp_path, monkeypatch) -> None:
    health = _no_ollama(monkeypatch, rca_module)
    cloud = _Cloud({"suggestions": []})
    suggester, run_id = _suggester(tmp_path, _router(_settings(**CLOUD_ON), cloud))  # no key

    output = suggester._try_model(suggester.build_context(run_id))

    assert output is None
    assert cloud.calls == []
    health.assert_called()
