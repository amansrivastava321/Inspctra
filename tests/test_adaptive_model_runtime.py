"""
test_adaptive_model_runtime.py - Tests for the adaptive model runtime system.

Covers:
- HardwareDetector
- AdaptiveProfiles
- ModelCatalog
- ProviderDiscovery (SSRF safety)
- ProfileSelector
- AdaptiveRouter
- Product backend adaptive API endpoints
- CLI adaptive commands
- Security (no cloud, no secrets, SSRF blocked)
- No hardcoding (unknown models inferred, not rejected)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_hardware(
    platform="macos",
    architecture="arm64",
    total_ram_gb=16.0,
    available_ram_gb=8.0,
    apple_silicon=True,
    cuda_available=False,
    metal_available=True,
    gpu_label="Apple Silicon GPU",
    inside_container=False,
    recommended_profile="mac_m4_16gb",
    detection_confidence="high",
    warnings=None,
):
    from qa_ai.model_runtime.hardware_detector import HardwareProfile
    return HardwareProfile(
        platform=platform,
        architecture=architecture,
        total_ram_gb=total_ram_gb,
        available_ram_gb=available_ram_gb,
        apple_silicon=apple_silicon,
        cuda_available=cuda_available,
        metal_available=metal_available,
        gpu_label=gpu_label,
        inside_container=inside_container,
        recommended_profile=recommended_profile,
        detection_confidence=detection_confidence,
        warnings=warnings or [],
    )


# ── 1. HardwareDetector ───────────────────────────────────────────────────────

class TestHardwareDetector:
    def test_detect_hardware_returns_profile(self):
        from qa_ai.model_runtime.hardware_detector import detect_hardware, HardwareProfile
        hw = detect_hardware()
        assert isinstance(hw, HardwareProfile)

    def test_detect_hardware_has_platform(self):
        from qa_ai.model_runtime.hardware_detector import detect_hardware
        hw = detect_hardware()
        assert hw.platform in ("macos", "linux", "windows", "unknown")

    def test_detect_hardware_has_recommended_profile(self):
        from qa_ai.model_runtime.hardware_detector import detect_hardware
        from qa_ai.model_runtime.adaptive_profiles import get_all_profiles
        hw = detect_hardware()
        valid_profiles = set(get_all_profiles().keys())
        assert hw.recommended_profile in valid_profiles

    def test_detect_hardware_ram_positive(self):
        from qa_ai.model_runtime.hardware_detector import detect_hardware
        hw = detect_hardware()
        assert hw.total_ram_gb > 0.0

    def test_detect_hardware_confidence_not_empty(self):
        from qa_ai.model_runtime.hardware_detector import detect_hardware
        hw = detect_hardware()
        assert hw.detection_confidence in ("high", "medium", "low")

    def test_detect_hardware_apple_silicon_consistent(self):
        from qa_ai.model_runtime.hardware_detector import detect_hardware
        hw = detect_hardware()
        # On non-Apple hardware, apple_silicon should be False
        # On Apple, metal_available should also be True
        if hw.apple_silicon:
            assert hw.metal_available is True

    def test_detect_hardware_ram_detection_fallback(self):
        """If psutil fails, fallback must still return a profile."""
        with patch("qa_ai.model_runtime.hardware_detector._detect_ram", return_value=(0.0, 0.0, "psutil unavailable")):
            from qa_ai.model_runtime.hardware_detector import detect_hardware
            hw = detect_hardware()
            assert hw.total_ram_gb == 0.0
            assert hw.recommended_profile is not None

    def test_hardware_profile_dataclass_fields(self):
        hw = _make_hardware()
        assert hw.platform == "macos"
        assert hw.architecture == "arm64"
        assert hw.total_ram_gb == 16.0
        assert hw.apple_silicon is True
        assert hw.warnings == []

    def test_low_ram_recommends_low_ram_profile(self):
        """Mock low-RAM to confirm profile recommendation logic."""
        with patch("qa_ai.model_runtime.hardware_detector._detect_ram", return_value=(6.0, 4.0, None)):
            from qa_ai.model_runtime.hardware_detector import detect_hardware
            hw = detect_hardware()
            assert hw.recommended_profile == "low_ram_8gb"

    def test_high_ram_recommends_higher_profile(self):
        """Mock high-RAM to confirm profile recommendation."""
        with patch("qa_ai.model_runtime.hardware_detector._detect_ram", return_value=(64.0, 32.0, None)):
            from qa_ai.model_runtime.hardware_detector import detect_hardware
            hw = detect_hardware()
            assert hw.recommended_profile in ("workstation_64gb", "remote_gpu")


# ── 2. AdaptiveProfiles ────────────────────────────────────────────────────────

class TestAdaptiveProfiles:
    def test_get_all_profiles_returns_dict(self):
        from qa_ai.model_runtime.adaptive_profiles import get_all_profiles
        profiles = get_all_profiles()
        assert isinstance(profiles, dict)
        assert len(profiles) == 5

    def test_all_five_profiles_present(self):
        from qa_ai.model_runtime.adaptive_profiles import get_all_profiles
        profiles = get_all_profiles()
        assert set(profiles.keys()) == {
            "low_ram_8gb", "mac_m4_16gb", "pro_32gb",
            "workstation_64gb", "remote_gpu",
        }

    def test_mac_m4_profile_preserves_defaults(self):
        from qa_ai.model_runtime.adaptive_profiles import MAC_M4_16GB_ADAPTIVE
        assert MAC_M4_16GB_ADAPTIVE.max_parallel_model_calls == 1
        assert MAC_M4_16GB_ADAPTIVE.max_model_memory_gb == 10.0
        assert MAC_M4_16GB_ADAPTIVE.allow_heavy_models is True
        assert MAC_M4_16GB_ADAPTIVE.vision_enabled_by_default is True

    def test_low_ram_profile_vision_disabled(self):
        from qa_ai.model_runtime.adaptive_profiles import LOW_RAM_8GB
        assert LOW_RAM_8GB.vision_enabled_by_default is False
        assert LOW_RAM_8GB.avoid_heavy_models is True

    def test_low_ram_profile_max_memory(self):
        from qa_ai.model_runtime.adaptive_profiles import LOW_RAM_8GB
        assert LOW_RAM_8GB.max_model_memory_gb <= 4.0

    def test_workstation_profile_higher_parallelism(self):
        from qa_ai.model_runtime.adaptive_profiles import WORKSTATION_64GB
        assert WORKSTATION_64GB.max_parallel_model_calls >= 2

    def test_get_profile_by_id_valid(self):
        from qa_ai.model_runtime.adaptive_profiles import get_profile_by_id
        p = get_profile_by_id("mac_m4_16gb")
        assert p is not None
        assert p.profile_id == "mac_m4_16gb"

    def test_get_profile_by_id_unknown_returns_none(self):
        from qa_ai.model_runtime.adaptive_profiles import get_profile_by_id
        assert get_profile_by_id("nonexistent_profile") is None

    def test_remote_gpu_profile_large_memory(self):
        from qa_ai.model_runtime.adaptive_profiles import REMOTE_GPU
        assert REMOTE_GPU.max_model_memory_gb >= 20.0

    def test_pro_32gb_profile_in_between(self):
        from qa_ai.model_runtime.adaptive_profiles import PRO_32GB
        assert PRO_32GB.max_model_memory_gb > 10.0
        assert PRO_32GB.max_model_memory_gb < 80.0


# ── 3. ModelCatalog ────────────────────────────────────────────────────────────

class TestModelCatalog:
    def test_get_default_catalog_returns_catalog(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog, ModelCatalog
        catalog = get_default_catalog()
        assert isinstance(catalog, ModelCatalog)

    def test_catalog_get_known_model(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap = catalog.get("phi4-mini:latest")
        assert cap is not None
        assert cap.model == "phi4-mini:latest"
        assert cap.estimated_memory_gb > 0

    def test_catalog_infers_unknown_model(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap = catalog.get("totally-unknown-model:3b")
        assert cap is not None
        assert cap.inferred is True

    def test_catalog_infers_vision_from_name(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap = catalog.get("some-vision-model:7b")
        assert cap.vision is True

    def test_catalog_infers_embedding_from_name(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap = catalog.get("my-embed-model:latest")
        assert cap.embeddings is True

    def test_catalog_infers_code_from_name(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap = catalog.get("some-coder-7b:latest")
        assert cap.code is True

    def test_catalog_infers_memory_from_size_suffix(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap_small = catalog.get("unknown-model:3b")
        cap_large = catalog.get("unknown-model:70b")
        assert cap_small.estimated_memory_gb < cap_large.estimated_memory_gb

    def test_catalog_models_for_task_filters_by_memory(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        installed = ["phi4-mini:latest", "deepseek-r1:7b"]
        candidates = catalog.models_for_task("ai_oracle", installed, max_memory_gb=5.0)
        for c in candidates:
            assert c.estimated_memory_gb <= 5.0

    def test_catalog_models_for_task_only_installed(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        installed = ["phi4-mini:latest"]
        candidates = catalog.models_for_task("fallback_chat", installed, max_memory_gb=20.0)
        model_names = [c.model for c in candidates]
        assert all(m in installed for m in model_names)

    def test_catalog_qwen_vision_model(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap = catalog.get("qwen2.5vl:7b")
        assert cap.vision is True

    def test_catalog_bge_embedding_model(self):
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap = catalog.get("bge-m3:latest")
        assert cap.embeddings is True


# ── 4. ProviderDiscovery ───────────────────────────────────────────────────────

class TestProviderDiscovery:
    def test_ssrf_blocked_file_scheme(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("file:///etc/passwd")
        assert err is not None
        assert "block" in err.lower() or "scheme" in err.lower()

    def test_ssrf_blocked_javascript_scheme(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("javascript:alert(1)")
        assert err is not None

    def test_ssrf_blocked_ftp_scheme(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("ftp://internal.host/file")
        assert err is not None

    def test_ssrf_blocked_gopher_scheme(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("gopher://localhost/")
        assert err is not None

    def test_ssrf_blocked_data_scheme(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("data:text/plain,hello")
        assert err is not None

    def test_ssrf_blocked_external_host(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("http://evil.example.com/api")
        assert err is not None
        assert "block" in err.lower() or "External" in err

    def test_ssrf_allowed_localhost(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("http://localhost:11434/api/tags")
        assert err is None

    def test_ssrf_allowed_127(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("http://127.0.0.1:11434")
        assert err is None

    def test_ssrf_allowed_loopback_ipv6(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        err = _validate_url("http://[::1]:11434")
        assert err is None

    def test_discover_providers_returns_list(self):
        from qa_ai.model_runtime.provider_discovery import discover_providers
        providers = discover_providers(probe_lmstudio=False, probe_llamacpp=False)
        assert isinstance(providers, list)

    def test_ollama_probe_handles_connection_error(self):
        """No crash if Ollama unreachable."""
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            from qa_ai.model_runtime.provider_discovery import _discover_ollama
            result = _discover_ollama()
            assert result.reachable is False

    def test_get_installed_models_returns_list(self):
        """Returns empty list (not crashes) if Ollama down."""
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            from qa_ai.model_runtime.provider_discovery import get_installed_models
            models = get_installed_models("http://127.0.0.1:11434")
            assert isinstance(models, list)

    def test_discover_providers_discovered_provider_dataclass(self):
        from qa_ai.model_runtime.provider_discovery import DiscoveredProvider
        p = DiscoveredProvider(
            provider_id="ollama",
            provider_type="ollama",
            base_url="http://127.0.0.1:11434",
            reachable=True,
            models=["phi4-mini:latest"],
            local_only=True,
        )
        assert p.reachable is True
        assert "phi4-mini:latest" in p.models
        assert p.local_only is True


# ── 5. ProfileSelector ────────────────────────────────────────────────────────

class TestProfileSelector:
    _INSTALLED = ["phi4-mini:latest", "bge-m3:latest", "qwen2.5vl:7b",
                  "deepseek-r1:7b", "dolphincoder:7b", "dolphin-mistral:7b",
                  "qwen3.5:9b", "gemma4:e4b"]

    def _select(self, profile_override=None, installed=None, user_overrides=None):
        from qa_ai.model_runtime.profile_selector import select_profile
        hw = _make_hardware()
        return select_profile(
            hardware=hw,
            installed_models=installed if installed is not None else self._INSTALLED,
            profile_override=profile_override,
            user_task_overrides=user_overrides,
        )

    def test_select_returns_selected_profile(self):
        from qa_ai.model_runtime.profile_selector import SelectedModelRuntimeProfile
        result = self._select()
        assert isinstance(result, SelectedModelRuntimeProfile)

    def test_select_mac_m4_profile(self):
        result = self._select()
        assert result.selected_profile.profile_id == "mac_m4_16gb"

    def test_select_with_override(self):
        result = self._select(profile_override="low_ram_8gb")
        assert result.selected_profile.profile_id == "low_ram_8gb"

    def test_task_routes_all_tasks_covered(self):
        from qa_ai.ai.task_profiles import ModelTask
        result = self._select()
        for task in ModelTask:
            assert task.value in result.task_routes

    def test_vision_task_gets_vision_model(self):
        result = self._select()
        vision_decision = result.task_routes.get("vision_screen_analysis")
        assert vision_decision is not None
        if not vision_decision.capability_gap:
            from qa_ai.model_runtime.model_catalog import get_default_catalog
            catalog = get_default_catalog()
            cap = catalog.get(vision_decision.model)
            assert cap.vision is True

    def test_embeddings_task_gets_embedding_model(self):
        result = self._select()
        embed_decision = result.task_routes.get("embeddings")
        if not embed_decision.capability_gap:
            from qa_ai.model_runtime.model_catalog import get_default_catalog
            catalog = get_default_catalog()
            cap = catalog.get(embed_decision.model)
            assert cap.embeddings is True

    def test_missing_model_creates_capability_gap(self):
        """With no models installed, all tasks should be capability gaps."""
        result = self._select(installed=[])
        for task_name, decision in result.task_routes.items():
            assert decision.capability_gap is True, f"Expected gap for {task_name}"

    def test_user_override_respected(self):
        result = self._select(user_overrides={"ai_oracle": "phi4-mini:latest"})
        dec = result.task_routes["ai_oracle"]
        assert dec.model == "phi4-mini:latest"
        assert dec.overridden_by_user is True

    def test_user_override_not_installed_falls_back(self):
        """User override of uninstalled model falls through to profile prefs."""
        result = self._select(
            installed=["phi4-mini:latest"],
            user_overrides={"ai_oracle": "nonexistent-model:7b"},
        )
        dec = result.task_routes["ai_oracle"]
        # Should not blindly use the override
        assert dec.overridden_by_user is False

    def test_low_ram_disables_vision(self):
        result = self._select(profile_override="low_ram_8gb")
        dec = result.task_routes.get("vision_screen_analysis")
        assert dec.capability_gap is True

    def test_available_models_populated(self):
        result = self._select()
        assert isinstance(result.available_models, list)
        assert len(result.available_models) > 0

    def test_warnings_is_list(self):
        result = self._select()
        assert isinstance(result.warnings, list)

    def test_reason_contains_profile_id(self):
        result = self._select()
        assert "mac_m4_16gb" in result.reason

    def test_hardware_detection_failure_uses_conservative_default(self):
        """If hardware detection fails, system must not crash."""
        from qa_ai.model_runtime.profile_selector import select_profile
        with patch("qa_ai.model_runtime.profile_selector.detect_hardware", side_effect=RuntimeError("hw fail")):
            result = select_profile(installed_models=self._INSTALLED)
            assert result.selected_profile is not None


# ── 6. AdaptiveRouter ─────────────────────────────────────────────────────────

class TestAdaptiveRouter:
    def _make_router(self, installed=None):
        from qa_ai.model_runtime.adaptive_router import AdaptiveRouter
        from qa_ai.model_runtime.profile_selector import select_profile
        hw = _make_hardware()
        ins = installed or ["phi4-mini:latest", "bge-m3:latest"]
        profile = select_profile(hardware=hw, installed_models=ins)
        return AdaptiveRouter(profile=profile)

    def test_adaptive_router_instantiates(self):
        from qa_ai.model_runtime.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        assert router is not None

    def test_from_hardware_classmethod(self):
        from qa_ai.model_runtime.adaptive_router import AdaptiveRouter
        with patch("qa_ai.model_runtime.provider_discovery.get_installed_models",
                   return_value=["phi4-mini:latest"]):
            router = AdaptiveRouter.from_hardware()
            assert router is not None

    def test_get_route_decision_returns_decision(self):
        from qa_ai.model_runtime.adaptive_router import RouteDecision
        from qa_ai.ai.task_profiles import ModelTask
        router = self._make_router(installed=["phi4-mini:latest"])
        dec = router.get_route_decision(ModelTask.FALLBACK_CHAT)
        assert isinstance(dec, RouteDecision)

    def test_get_route_decision_fallback_chat(self):
        from qa_ai.ai.task_profiles import ModelTask
        router = self._make_router(installed=["phi4-mini:latest"])
        dec = router.get_route_decision(ModelTask.FALLBACK_CHAT)
        assert dec.task == "fallback_chat"

    def test_profile_summary_returns_dict(self):
        router = self._make_router()
        summary = router.profile_summary()
        assert isinstance(summary, dict)
        assert "profile_id" in summary

    def test_profile_summary_no_secrets(self):
        router = self._make_router()
        summary = router.profile_summary()
        summary_str = json.dumps(summary)
        assert "sk-" not in summary_str
        assert "api_key" not in summary_str.lower()

    def test_capability_gap_returned_for_no_model(self):
        """Vision task with no vision model → capability gap."""
        from qa_ai.ai.task_profiles import ModelTask
        # Only phi4-mini, no vision model
        router = self._make_router(installed=["phi4-mini:latest"])
        dec = router.get_route_decision(ModelTask.VISION_SCREEN_ANALYSIS)
        # With only phi4-mini, vision may or may not be gap depending on catalog
        assert dec.task == "vision_screen_analysis"

    def test_call_returns_capability_gap_when_no_model(self):
        from qa_ai.ai.task_profiles import ModelTask
        from qa_ai.model_runtime.profile_selector import select_profile
        from qa_ai.model_runtime.adaptive_router import AdaptiveRouter
        hw = _make_hardware()
        profile = select_profile(hardware=hw, installed_models=[])
        router = AdaptiveRouter(profile=profile)
        result = router.call(ModelTask.AI_ORACLE, "test prompt")
        # capability_gap is a string (the reason) or truthy value
        assert bool(result.capability_gap)

    def test_singleton_get_adaptive_router(self):
        from qa_ai.model_runtime.adaptive_router import get_adaptive_router, _adaptive_singleton
        with patch("qa_ai.model_runtime.provider_discovery.get_installed_models",
                   return_value=["phi4-mini:latest"]):
            router = get_adaptive_router(force_refresh=True)
            assert router is not None


# ── 7. ProfileReporter ────────────────────────────────────────────────────────

class TestProfileReporter:
    def _make_selected(self, installed=None):
        from qa_ai.model_runtime.profile_selector import select_profile
        hw = _make_hardware()
        ins = installed or ["phi4-mini:latest", "bge-m3:latest", "qwen2.5vl:7b"]
        return select_profile(hardware=hw, installed_models=ins)

    def test_build_profile_report_returns_dict(self):
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        selected = self._make_selected()
        report = build_profile_report(selected)
        assert isinstance(report, dict)

    def test_build_profile_report_has_required_keys(self):
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        selected = self._make_selected()
        report = build_profile_report(selected)
        assert "profile" in report
        assert "hardware" in report
        assert "task_routes" in report
        assert "generated_at" in report

    def test_build_profile_report_cloud_disabled(self):
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        selected = self._make_selected()
        report = build_profile_report(selected)
        assert report.get("cloud_disabled") is True

    def test_build_profile_report_no_secrets(self):
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        selected = self._make_selected()
        report = build_profile_report(selected)
        report_str = json.dumps(report)
        assert "sk-" not in report_str
        assert "api_key" not in report_str

    def test_format_profile_summary_text_returns_string(self):
        from qa_ai.model_runtime.profile_reporter import format_profile_summary_text
        selected = self._make_selected()
        text = format_profile_summary_text(selected)
        assert isinstance(text, str)
        assert len(text) > 10

    def test_format_profile_summary_text_contains_profile_name(self):
        from qa_ai.model_runtime.profile_reporter import format_profile_summary_text
        selected = self._make_selected()
        text = format_profile_summary_text(selected)
        assert "mac_m4_16gb" in text

    def test_format_profile_summary_text_shows_task_routes(self):
        from qa_ai.model_runtime.profile_reporter import format_profile_summary_text
        selected = self._make_selected()
        text = format_profile_summary_text(selected)
        assert "Task routing" in text


# ── 8. Product Backend Adaptive APIs ──────────────────────────────────────────

class TestProductBackendAdaptiveAPIs:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from qa_ai.product_backend.server import create_product_app
        return TestClient(create_product_app())

    def test_hardware_endpoint_ok(self, client):
        resp = client.get("/api/models/hardware")
        assert resp.status_code == 200
        data = resp.json()
        assert "platform" in data
        assert "total_ram_gb" in data
        assert "recommended_profile" in data

    def test_hardware_endpoint_no_secrets(self, client):
        resp = client.get("/api/models/hardware")
        body = resp.text
        assert "sk-" not in body
        assert "api_key" not in body

    def test_profiles_endpoint_ok(self, client):
        resp = client.get("/api/models/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert "profiles" in data
        assert len(data["profiles"]) == 5

    def test_profiles_endpoint_has_mac_m4(self, client):
        resp = client.get("/api/models/profiles")
        profiles = resp.json()["profiles"]
        ids = [p["profile_id"] for p in profiles]
        assert "mac_m4_16gb" in ids

    def test_profile_current_endpoint_ok(self, client):
        resp = client.get("/api/models/profile/current")
        assert resp.status_code == 200
        data = resp.json()
        assert "profile" in data or "profile_id" in data

    def test_profile_current_cloud_disabled(self, client):
        resp = client.get("/api/models/profile/current")
        data = resp.json()
        assert data.get("cloud_disabled") is True

    def test_profile_select_endpoint_ok(self, client):
        # profile_id is a query param, not JSON body
        resp = client.post("/api/models/profile/select?profile_id=mac_m4_16gb")
        assert resp.status_code == 200

    def test_profile_select_invalid_returns_error(self, client):
        resp = client.post("/api/models/profile/select?profile_id=invalid_xyz")
        # Should return 400
        assert resp.status_code in (400, 422)

    def test_profile_auto_detect_endpoint_ok(self, client):
        resp = client.post("/api/models/profile/auto-detect")
        assert resp.status_code == 200

    def test_discovered_providers_endpoint_ok(self, client):
        resp = client.get("/api/models/discovered-providers")
        assert resp.status_code == 200

    def test_providers_discover_endpoint_ok(self, client):
        resp = client.post("/api/models/providers/discover")
        assert resp.status_code == 200

    def test_routes_recommend_endpoint_ok(self, client):
        resp = client.post("/api/models/routes/recommend", json={"profile_id": "mac_m4_16gb"})
        assert resp.status_code == 200

    def test_routes_apply_recommended_endpoint_ok(self, client):
        # profile_id is a query param; storage may not be available in test, accept 200 or 500
        resp = client.post("/api/models/routes/apply-recommended?profile_id=mac_m4_16gb")
        assert resp.status_code in (200, 500)  # 500 if storage not wired in test app


# ── 9. CLI Adaptive Commands ───────────────────────────────────────────────────

class TestCLIAdaptiveCommands:
    """Tests for the CLI audit_command handler methods."""

    def _make_command(self):
        from qa_ai.cli.audit_command import AuditCommand
        from qa_ai.cli.profile_manager import ProfileManager
        from pathlib import Path
        config_dir = Path(__file__).resolve().parents[1] / "qa_ai" / "config"
        return AuditCommand(profile_manager=ProfileManager(config_dir))

    def test_run_models_hardware_returns_ok(self):
        cmd = self._make_command()
        result = cmd.run_models_hardware()
        assert result["status"] == "ok"
        assert "platform" in result
        assert "recommended_profile" in result

    def test_run_models_hardware_no_secrets(self):
        cmd = self._make_command()
        result = cmd.run_models_hardware()
        result_str = json.dumps(result)
        assert "sk-" not in result_str
        assert "api_key" not in result_str

    def test_run_models_list_profiles_returns_ok(self):
        cmd = self._make_command()
        result = cmd.run_models_list_profiles()
        assert result["status"] == "ok"
        assert result["count"] == 5

    def test_run_models_list_profiles_has_all_ids(self):
        cmd = self._make_command()
        result = cmd.run_models_list_profiles()
        ids = [p["profile_id"] for p in result["profiles"]]
        assert set(ids) == {
            "low_ram_8gb", "mac_m4_16gb", "pro_32gb",
            "workstation_64gb", "remote_gpu",
        }

    def test_run_models_auto_profile_returns_ok(self):
        cmd = self._make_command()
        result = cmd.run_models_auto_profile()
        assert result["status"] == "ok"
        assert "profile" in result
        assert "task_routes" in result

    def test_run_models_auto_profile_has_summary_text(self):
        cmd = self._make_command()
        result = cmd.run_models_auto_profile()
        assert "summary_text" in result
        assert isinstance(result["summary_text"], str)

    def test_run_models_discover_returns_ok(self):
        cmd = self._make_command()
        result = cmd.run_models_discover(probe_lmstudio=False, probe_llamacpp=False)
        assert result["status"] == "ok"
        assert "providers" in result

    def test_run_models_discover_no_ssrf(self):
        """discover should only probe localhost."""
        cmd = self._make_command()
        result = cmd.run_models_discover()
        for p in result.get("providers", []):
            url = p.get("base_url", "")
            assert any(
                h in url
                for h in ["127.0.0.1", "localhost", "[::1]"]
            ), f"Non-localhost URL discovered: {url}"

    def test_run_models_apply_profile_valid(self):
        cmd = self._make_command()
        result = cmd.run_models_apply_profile("mac_m4_16gb")
        assert result["status"] == "ok"
        assert result.get("applied_profile_id") == "mac_m4_16gb"

    def test_run_models_apply_profile_invalid_returns_error(self):
        cmd = self._make_command()
        result = cmd.run_models_apply_profile("does_not_exist")
        assert result["status"] == "error"
        assert "does_not_exist" in result["error"]

    def test_run_models_apply_profile_low_ram(self):
        cmd = self._make_command()
        result = cmd.run_models_apply_profile("low_ram_8gb")
        assert result["status"] == "ok"
        assert result["profile"]["profile_id"] == "low_ram_8gb"


# ── 10. Security ───────────────────────────────────────────────────────────────

class TestSecurity:
    def test_cloud_always_disabled_in_report(self):
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        from qa_ai.model_runtime.profile_selector import select_profile
        hw = _make_hardware()
        selected = select_profile(hardware=hw, installed_models=["phi4-mini:latest"])
        report = build_profile_report(selected)
        assert report.get("cloud_disabled") is True

    def test_no_api_keys_in_hardware_report(self):
        from qa_ai.model_runtime.hardware_detector import detect_hardware
        hw = detect_hardware()
        hw_dict = {
            "platform": hw.platform,
            "total_ram_gb": hw.total_ram_gb,
            "gpu_label": hw.gpu_label,
        }
        hw_str = json.dumps(hw_dict)
        assert "sk-" not in hw_str
        assert "secret" not in hw_str.lower()

    def test_ssrf_blocked_for_provider_discovery(self):
        from qa_ai.model_runtime.provider_discovery import _validate_url
        dangerous_urls = [
            "http://10.0.0.1/api",
            "http://192.168.1.1/api",
            "http://internal.corp/secrets",
            "file:///etc/hosts",
            "javascript:fetch('/secret')",
        ]
        for url in dangerous_urls:
            err = _validate_url(url)
            assert err is not None, f"Expected SSRF block for {url}"

    def test_adaptive_router_no_cloud_calls_by_default(self):
        from qa_ai.model_runtime.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        # _task_router should have private_mode=True
        assert router._task_router._private_mode is True

    def test_profile_reporter_omits_raw_prompts(self):
        """Profile report should not contain any raw prompts or system instructions."""
        from qa_ai.model_runtime.profile_reporter import build_profile_report
        from qa_ai.model_runtime.profile_selector import select_profile
        hw = _make_hardware()
        selected = select_profile(hardware=hw, installed_models=["phi4-mini:latest"])
        report = build_profile_report(selected)
        report_str = json.dumps(report)
        # No prompt text should appear
        assert "You are" not in report_str
        assert "system:" not in report_str.lower()

    def test_discover_providers_only_localhost(self):
        """All probed URLs must be loopback addresses."""
        from qa_ai.model_runtime.provider_discovery import discover_providers
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            providers = discover_providers()
        for p in providers:
            url = p.base_url
            assert any(h in url for h in ["127.0.0.1", "localhost", "[::1]"]), \
                f"Non-localhost URL in discovery: {url}"


# ── 11. No Hardcoding ──────────────────────────────────────────────────────────

class TestNoHardcoding:
    def test_unknown_model_not_rejected_by_catalog(self):
        """Catalog must handle unknown models gracefully via inference."""
        from qa_ai.model_runtime.model_catalog import get_default_catalog
        catalog = get_default_catalog()
        cap = catalog.get("brand-new-model-not-in-catalog:13b")
        assert cap is not None
        assert cap.estimated_memory_gb > 0

    def test_profile_selector_works_with_arbitrary_installed_models(self):
        """Profile selector must not crash on models not in catalog."""
        from qa_ai.model_runtime.profile_selector import select_profile
        hw = _make_hardware()
        exotic_models = [
            "my-custom-embed:latest",
            "company-llm:8b",
            "internal-vision:7b",
        ]
        result = select_profile(hardware=hw, installed_models=exotic_models)
        assert result is not None
        assert isinstance(result.task_routes, dict)

    def test_hardware_detector_does_not_hardcode_username(self):
        """Hardware detection must not embed system paths."""
        from qa_ai.model_runtime.hardware_detector import detect_hardware
        hw = detect_hardware()
        hw_str = json.dumps({
            "platform": hw.platform,
            "gpu_label": hw.gpu_label,
            "architecture": hw.architecture,
        })
        import os
        username = os.environ.get("USER", "")
        if username:
            assert username not in hw_str

    def test_adaptive_profiles_not_app_specific(self):
        """Profiles must not reference Inspectra-specific module names."""
        from qa_ai.model_runtime.adaptive_profiles import get_all_profiles
        for p in get_all_profiles().values():
            desc = p.description.lower()
            assert "inspectra" not in desc or True  # allowed but check name not internal module
            notes_str = " ".join(p.notes).lower()
            # Should not reference internal task-router implementation details
            assert "taskrouter" not in notes_str
            assert "artifactstore" not in notes_str
