"""
test_model_health.py - Tests for model_health.py

Covers: health report structure, ollama reachable/unreachable,
route coverage, missing models reported, recommendations.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from qa_ai.ai.model_health import build_health_report, ModelHealthReport


def _mock_ollama_tags(models: list[str]):
    """Mock urlopen for /api/tags returning given model names."""
    resp = MagicMock()
    resp.read.return_value = json.dumps({
        "models": [{"name": m} for m in models]
    }).encode()
    resp.__enter__ = lambda self: self
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestBuildHealthReport:
    def test_returns_health_report_type(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            report = build_health_report()
        assert isinstance(report, ModelHealthReport)

    def test_ollama_unreachable_flagged(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            report = build_health_report()
        assert report.ollama_reachable is False

    def test_missing_models_listed_when_ollama_down(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            report = build_health_report()
        # All required models are missing when Ollama is down
        assert len(report.missing_models) > 0

    def test_overall_readiness_unavailable_when_offline(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            report = build_health_report()
        assert report.overall_readiness in ("unavailable", "degraded", "partial")

    def test_ollama_reachable_with_all_models(self):
        from qa_ai.ai.task_profiles import REQUIRED_LOCAL_MODELS
        all_models = list(REQUIRED_LOCAL_MODELS)
        mock_resp = _mock_ollama_tags(all_models)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            report = build_health_report()
        assert report.ollama_reachable is True
        assert len(report.missing_models) == 0
        assert len(report.present_models) == len(all_models)

    def test_partial_models_shows_missing(self):
        partial_models = ["qwen2.5vl:7b", "phi4-mini:latest"]
        mock_resp = _mock_ollama_tags(partial_models)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            report = build_health_report()
        assert report.ollama_reachable is True
        assert len(report.missing_models) > 0
        # The full set minus partial should be missing
        from qa_ai.ai.task_profiles import REQUIRED_LOCAL_MODELS
        expected_missing = REQUIRED_LOCAL_MODELS - set(partial_models)
        assert set(report.missing_models) == expected_missing

    def test_route_coverage_has_all_tasks(self):
        from qa_ai.ai.task_profiles import ModelTask
        all_models = ["qwen2.5vl:7b", "qwen3.5:9b", "deepseek-r1:7b",
                      "phi4-mini:latest", "gemma4:e4b", "dolphincoder:7b",
                      "dolphin-mistral:7b", "bge-m3:latest"]
        mock_resp = _mock_ollama_tags(all_models)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            report = build_health_report()
        covered_tasks = {r.task for r in report.route_coverage}
        for task in ModelTask:
            assert task.value in covered_tasks

    def test_recommendations_list_present(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            report = build_health_report()
        assert isinstance(report.recommendations, list)

    def test_cloud_providers_disabled_by_default(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            report = build_health_report()
        assert report.cloud_providers_disabled is True

    def test_generated_at_present(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            report = build_health_report()
        assert report.generated_at != ""


class TestModelHealthReport:
    def test_dataclass_fields_present(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(ModelHealthReport)}
        required = {
            "generated_at", "ollama_reachable", "ollama_base_url",
            "installed_models", "required_models", "missing_models",
            "present_models", "route_coverage", "cloud_providers_disabled",
            "overall_readiness", "recommendations",
        }
        assert required.issubset(fields)
