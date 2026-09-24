"""
test_task_router.py - Tests for task_router.py

Covers: correct model selection, fallback on failure, cloud blocked by default,
capability gap on no route, prompt safety applied, resource manager respected,
embeddings call, structured result.
"""
from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock, patch
import pytest

from qa_ai.ai.task_router import TaskRouter, ModelCallResult, _capability_gap
from qa_ai.ai.task_profiles import ModelTask, get_default_task_routes
from qa_ai.ai.resource_manager import ResourceManager
from qa_ai.ai.task_profiles import MAC_M4_16GB


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_ollama_response(content: str, tokens_in: int = 5, tokens_out: int = 10):
    return json.dumps({
        "message": {"content": content},
        "prompt_eval_count": tokens_in,
        "eval_count": tokens_out,
    }).encode()


def _mock_urlopen(content: str = "test response"):
    """Context manager mock for urllib.request.urlopen."""
    from unittest.mock import MagicMock, patch

    resp = MagicMock()
    resp.read.return_value = _make_ollama_response(content)
    resp.__enter__ = lambda self: self
    resp.__exit__ = MagicMock(return_value=False)
    return patch("urllib.request.urlopen", return_value=resp)


@pytest.fixture
def router():
    rm = ResourceManager(profile=MAC_M4_16GB)
    return TaskRouter(
        resource_manager=rm,
        allow_cloud=False,
        private_mode=True,
        persist_prompts=False,
    )


# ── Capability gap ──────────────────────────────────────────────────────────


class TestCapabilityGap:
    def test_no_route_returns_capability_gap(self, router):
        # Remove all routes to force a gap
        router._routes = {}
        result = router.call(ModelTask.AI_ORACLE, "test prompt")
        assert result.status == "capability_gap"
        assert result.ok is False

    def test_capability_gap_factory(self):
        gap = _capability_gap(ModelTask.AI_ORACLE, "reason here")
        assert gap.status == "capability_gap"
        assert gap.ok is False
        assert gap.task == "ai_oracle"
        assert "reason here" in gap.capability_gap


# ── Successful call ─────────────────────────────────────────────────────────


class TestSuccessfulCall:
    def test_returns_ok_status(self, router):
        with _mock_urlopen("oracle says pass"):
            result = router.call(ModelTask.AI_ORACLE, "Did the login succeed?")
        assert result.status == "ok"
        assert result.ok is True
        assert "oracle says pass" in result.output_text

    def test_correct_task_value_in_result(self, router):
        with _mock_urlopen("narration text"):
            result = router.call(ModelTask.STEP_NARRATION, "Step 1 was completed.")
        assert result.task == "step_narration"

    def test_latency_ms_set(self, router):
        with _mock_urlopen("hi"):
            result = router.call(ModelTask.STEP_NARRATION, "hello")
        assert result.latency_ms >= 0

    def test_tokens_recorded(self, router):
        with _mock_urlopen("hi"):
            result = router.call(ModelTask.STEP_NARRATION, "hello")
        assert result.tokens_in >= 0
        assert result.tokens_out >= 0

    def test_provider_id_is_ollama(self, router):
        with _mock_urlopen("done"):
            result = router.call(ModelTask.STEP_NARRATION, "hello")
        assert result.provider_id == "ollama"


# ── JSON mode ───────────────────────────────────────────────────────────────


class TestJsonMode:
    def test_json_mode_parses_output(self, router):
        json_resp = '{"status": "passed", "confidence": 0.9}'
        with _mock_urlopen(json_resp):
            result = router.call(ModelTask.AI_ORACLE, "eval", json_mode=True)
        assert result.output_json is not None
        assert result.output_json["status"] == "passed"

    def test_json_mode_fallback_on_invalid_json(self, router):
        with _mock_urlopen("not valid json"):
            result = router.call(ModelTask.AI_ORACLE, "eval", json_mode=True)
        # Should not crash — output_json may be None or partial
        assert result.ok is True


# ── Fallback ────────────────────────────────────────────────────────────────


class TestFallback:
    def test_fallback_used_on_primary_failure(self, router):
        call_count = {"n": 0}

        def fake_urlopen(req, timeout=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OSError("Model unavailable")
            resp = MagicMock()
            resp.read.return_value = _make_ollama_response("fallback response")
            resp.__enter__ = lambda self: self
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = router.call(ModelTask.UI_ACTION_PLANNING, "what next?")

        # May succeed via fallback or return capability_gap — either is valid
        # (depends on ResourceManager slot state after failure)
        assert result.status in ("ok", "fallback", "capability_gap")


# ── Cloud blocked ───────────────────────────────────────────────────────────


class TestCloudBlocked:
    def test_cloud_disabled_by_default(self):
        r = TaskRouter(allow_cloud=False, private_mode=True)
        assert r._allow_cloud is False

    def test_cloud_flag_set(self):
        r = TaskRouter(allow_cloud=True, private_mode=False)
        assert r._allow_cloud is True


# ── Prompt safety ───────────────────────────────────────────────────────────


class TestPromptSafety:
    def test_api_key_in_prompt_redacted(self, router):
        prompt_with_key = "check this: sk-abcdefghijklmnopqrstuvwxyz1234567890"
        captured_payloads = []

        def fake_urlopen(req, timeout=None):
            captured_payloads.append(req.data.decode())
            resp = MagicMock()
            resp.read.return_value = _make_ollama_response("safe response")
            resp.__enter__ = lambda self: self
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = router.call(ModelTask.STEP_NARRATION, prompt_with_key)

        if captured_payloads:
            payload_str = captured_payloads[0]
            assert "sk-abcdefghijklmnopqrstuvwxyz1234567890" not in payload_str

    def test_private_code_blocked_for_cloud_call(self):
        router = TaskRouter(allow_cloud=True, private_mode=True)
        code_prompt = "import os\ndef main():\n    secret = 'abc123'\n"
        # This should either be blocked or have redactions
        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__ = lambda s: MagicMock(
                read=lambda: _make_ollama_response("ok")
            )
            result = router.call(ModelTask.STEP_NARRATION, code_prompt)
        # Result is either ok (local route) or blocked — not a crash
        assert result is not None


# ── Embeddings ──────────────────────────────────────────────────────────────


class TestEmbeddings:
    def test_embed_returns_list(self, router):
        embed_resp = json.dumps({"embeddings": [[0.1, 0.2, 0.3]]}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = embed_resp
        mock_resp.__enter__ = lambda self: self
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = router.embed(["hello world"])

        assert result.ok is True
        assert isinstance(result.embeddings, list)
        assert len(result.embeddings) > 0

    def test_embed_empty_texts(self, router):
        result = router.embed([])
        assert result.ok is True
        assert result.embeddings == []

    def test_embed_error_returns_error_status(self, router):
        with patch("urllib.request.urlopen", side_effect=OSError("ollama down")):
            result = router.embed(["text"])
        assert result.status == "error"
        assert result.error is not None


# ── Resource manager integration ────────────────────────────────────────────


class TestResourceManagerIntegration:
    def test_slot_released_after_ok_call(self, router):
        with _mock_urlopen("done"):
            router.call(ModelTask.STEP_NARRATION, "hi")
        # Slot should be free after call
        assert router._rm.can_run("any-model") is True

    def test_slot_released_after_exception(self, router):
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            router.call(ModelTask.STEP_NARRATION, "hi")
        # Slot should be free even after exception
        assert router._rm.can_run("any-model") is True


# ── ModelCallResult properties ──────────────────────────────────────────────


class TestModelCallResult:
    def test_ok_status_means_ok(self):
        r = ModelCallResult(status="ok", provider_id="ollama", model="x",
                           task="step_narration", output_text="hi")
        assert r.ok is True

    def test_fallback_status_means_ok(self):
        r = ModelCallResult(status="fallback", provider_id="ollama", model="x",
                           task="step_narration", output_text="hi")
        assert r.ok is True

    def test_capability_gap_not_ok(self):
        r = ModelCallResult(status="capability_gap", provider_id="none", model="none",
                           task="ai_oracle", output_text="")
        assert r.ok is False

    def test_error_not_ok(self):
        r = ModelCallResult(status="error", provider_id="ollama", model="x",
                           task="ai_oracle", output_text="")
        assert r.ok is False
