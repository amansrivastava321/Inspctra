# Platform Quality Hardening Sprint — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise QA-AI platform quality to 9/10 across LLM integration, error handling, security, configuration, and code structure — without adding features or breaking existing behavior.

**Architecture:** Five independent improvement tracks that share no cross-dependencies and can be verified individually. Each track produces working, tested code on its own. The graph hotspot analysis confirms `ArtifactStore` (989 edges), `WorkflowEngine` (297 edges), and `CapabilityRegistry` (238 edges) are the highest-risk change surfaces — every task avoids touching `ArtifactStore` internals.

**Tech Stack:** Python 3.11+, pytest, pydantic (already a dependency), subprocess/shlex, logging stdlib

---

## Graph Context

From `graphify-out/GRAPH_REPORT.md` (4851 nodes, 33455 edges, 293 communities):

**God nodes / blast-radius risk:**
- `ArtifactStore` — 989 edges. Do NOT refactor internals; only add env-var wiring at usage sites.
- `WorkflowEngine` — 297 edges. Safe to split via mixins; public API (`run()`, `__init__`) must not change.
- `CapabilityRegistry` — 238 edges. Already improved in previous session; leave alone.

**Remaining silent exception handlers (24 total across these files):**
- `live_execution/visual_regression.py:100`
- `live_execution/session_manager.py:97,111,177`
- `live_execution/api_session_manager.py:153`
- `orchestration/workflow_engine.py:1059`
- `runners/api_runner.py:340,344`
- `runners/playwright_runner.py:279`
- `platform_performance/memory_usage_tracker.py:46,61`
- `runtime_lab/docker_runtime.py:34`
- `mobile_runtime/android_emulator_manager.py:107,121,133`
- `mobile_runtime/ios_simulator_manager.py:81,93`
- `ai_reasoning/semantic_rca_engine.py:131`
- `mobile_runtime/device_registry.py:149`
- `ai_reasoning/scenario_generator.py:150`
- `mobile_runtime/device_log_collector.py:95`
- `ai_orchestration/ai_audit_orchestrator.py:99`

**Remaining hardcoded localhost URLs (not yet wired to env vars):**
- `orchestration/workflow_engine.py:1161,1404`
- `runners/api_runner.py:63`
- `runners/playwright_runner.py:56`
- `live_execution/live_scenario_runner.py:60`
- `exploration/ui_explorer.py:31`

---

## File Map

### New files to create:
| File | Purpose |
|------|---------|
| `qa_ai/config/settings.py` | Pydantic/dataclass settings with env var support |
| `qa_ai/utils/safe_subprocess.py` | Allowlist-gated command execution helper |
| `qa_ai/utils/error_handling.py` | Centralized `log_and_fallback` helper |
| `qa_ai/orchestration/phase_handlers/__init__.py` | Package marker |
| `qa_ai/orchestration/phase_handlers/audit_phase_mixin.py` | 13 audit/evidence phase methods |
| `qa_ai/orchestration/phase_handlers/live_phase_mixin.py` | 9 live-execution phase methods |
| `qa_ai/orchestration/phase_handlers/improvement_phase_mixin.py` | 20 improvement/remediation phase methods |
| `qa_ai/orchestration/phase_handlers/cicd_phase_mixin.py` | 13 CI/CD phase methods |
| `qa_ai/orchestration/phase_handlers/extended_phase_mixin.py` | 32 platform-perf/enterprise/bench/self-opt/distributed/mobile phase methods |
| `qa_ai/orchestration/phase_handlers/ai_phase_mixin.py` | 19 AI orchestration + reporting phase methods |
| `tests/test_llm_router_hardening.py` | LLM integration hardening tests |
| `tests/test_ollama_client_hardening.py` | OllamaClient env var / timeout tests |
| `tests/test_error_handling.py` | Error handling helper + patched handler tests |
| `tests/test_safe_subprocess.py` | Safe subprocess utility tests |
| `tests/test_settings.py` | Settings loading / env var override tests |
| `tests/test_god_class_refactor.py` | WorkflowEngine mixin public API tests |

### Files to modify:
| File | Changes |
|------|---------|
| `qa_ai/ai/llm_router.py` | Add env-var timeouts; enhance `ModelHealth` with `last_failure`, `next_retry_at`, `current_state` |
| `qa_ai/ai/ollama_client.py` | Read `QA_AI_OLLAMA_BASE_URL`; configurable timeouts |
| `qa_ai/orchestration/workflow_engine.py` | Import mixins; slim to ~600 lines; wire `settings` for base URLs |
| All 24 silent-exception files | Replace `except Exception:` with `log_and_fallback()` |
| `qa_ai/runners/api_runner.py` | Use `settings.api_base_url` |
| `qa_ai/runners/playwright_runner.py` | Use `settings.app_base_url` |
| `qa_ai/live_execution/live_scenario_runner.py` | Use `settings.app_base_url` |
| `qa_ai/exploration/ui_explorer.py` | Use `settings.app_base_url` |
| `docs/safety/destructive_action_policy.md` | Add safe subprocess policy |
| `docs/architecture/extension_guidelines.md` | Add error handling + configuration policy |
| `README.md` | Add env vars section |

---

## Task 1 — Configuration Settings Module

**Files:**
- Create: `qa_ai/config/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1.1: Write the failing tests**

```python
# tests/test_settings.py
import os
import pytest
from qa_ai.config.settings import Settings, get_settings


def test_defaults_load():
    s = Settings()
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.app_base_url == "http://localhost:3000"
    assert s.api_base_url == "http://localhost:8000"
    assert s.artifact_dir == "artifacts"
    assert s.llm_timeout_seconds == 120
    assert s.llm_long_timeout_seconds == 300
    assert s.llm_health_check_timeout == 2.0
    assert s.log_level == "INFO"
    assert s.enable_live_runtime is False
    assert s.enable_mobile_runtime is False
    assert s.enable_distributed_runtime is False


def test_env_vars_override(monkeypatch):
    monkeypatch.setenv("QA_AI_OLLAMA_BASE_URL", "http://myhost:11434")
    monkeypatch.setenv("QA_AI_APP_BASE_URL", "http://myapp:4000")
    monkeypatch.setenv("QA_AI_API_BASE_URL", "http://myapi:9000")
    monkeypatch.setenv("QA_AI_LLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("QA_AI_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("QA_AI_ENABLE_LIVE_RUNTIME", "true")
    # Re-import to pick up env
    import importlib
    import qa_ai.config.settings as mod
    importlib.reload(mod)
    s = mod.Settings()
    assert s.ollama_base_url == "http://myhost:11434"
    assert s.app_base_url == "http://myapp:4000"
    assert s.api_base_url == "http://myapi:9000"
    assert s.llm_timeout_seconds == 60
    assert s.log_level == "DEBUG"
    assert s.enable_live_runtime is True


def test_invalid_timeout_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("QA_AI_LLM_TIMEOUT_SECONDS", "not_a_number")
    import importlib
    import qa_ai.config.settings as mod
    importlib.reload(mod)
    s = mod.Settings()
    assert s.llm_timeout_seconds == 120  # fallback to default


def test_get_settings_returns_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
```

- [ ] **Step 1.2: Verify tests fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_settings.py -v
```

Expected: `ModuleNotFoundError: No module named 'qa_ai.config.settings'`

- [ ] **Step 1.3: Implement `qa_ai/config/settings.py`**

```python
"""
settings.py - Centralised runtime configuration.
All values read from environment variables with safe defaults.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache

logger = logging.getLogger(__name__)


def _int_env(key: str, default: int) -> int:
    raw = os.environ.get(key, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int for %s=%r, using default %d", key, raw, default)
        return default


def _float_env(key: str, default: float) -> float:
    raw = os.environ.get(key, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default %f", key, raw, default)
        return default


def _bool_env(key: str, default: bool) -> bool:
    raw = os.environ.get(key, "").lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return default


@dataclass
class Settings:
    # URLs
    ollama_base_url: str = field(
        default_factory=lambda: os.environ.get("QA_AI_OLLAMA_BASE_URL", "http://localhost:11434")
    )
    app_base_url: str = field(
        default_factory=lambda: os.environ.get("QA_AI_APP_BASE_URL", "http://localhost:3000")
    )
    api_base_url: str = field(
        default_factory=lambda: os.environ.get("QA_AI_API_BASE_URL", "http://localhost:8000")
    )

    # Paths
    artifact_dir: str = field(
        default_factory=lambda: os.environ.get("QA_AI_ARTIFACT_DIR", "artifacts")
    )

    # LLM timeouts (seconds)
    llm_timeout_seconds: int = field(
        default_factory=lambda: _int_env("QA_AI_LLM_TIMEOUT_SECONDS", 120)
    )
    llm_long_timeout_seconds: int = field(
        default_factory=lambda: _int_env("QA_AI_LLM_LONG_TIMEOUT_SECONDS", 300)
    )
    llm_health_check_timeout: float = field(
        default_factory=lambda: _float_env("QA_AI_LLM_HEALTH_CHECK_TIMEOUT", 2.0)
    )

    # Feature flags
    enable_live_runtime: bool = field(
        default_factory=lambda: _bool_env("QA_AI_ENABLE_LIVE_RUNTIME", False)
    )
    enable_mobile_runtime: bool = field(
        default_factory=lambda: _bool_env("QA_AI_ENABLE_MOBILE_RUNTIME", False)
    )
    enable_distributed_runtime: bool = field(
        default_factory=lambda: _bool_env("QA_AI_ENABLE_DISTRIBUTED_RUNTIME", False)
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.environ.get("QA_AI_LOG_LEVEL", "INFO")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
```

- [ ] **Step 1.4: Run tests — expect pass**

```bash
python -m pytest tests/test_settings.py -v
```

Expected: 4 passed

- [ ] **Step 1.5: Wire remaining localhost URLs to settings**

Edit `qa_ai/ai/ollama_client.py` — replace the `_DEFAULT_BASE_URL` constant:

```python
# Before:
_DEFAULT_BASE_URL = "http://localhost:11434"
class OllamaClient:
    def __init__(self, base_url: str = os.environ.get("OLLAMA_BASE_URL", _DEFAULT_BASE_URL)):

# After (add import at top):
from qa_ai.config.settings import get_settings
class OllamaClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or get_settings().ollama_base_url).rstrip("/")
```

Edit `qa_ai/runners/api_runner.py` line 63:
```python
# Add at top:
from qa_ai.config.settings import get_settings
# Change line 63:
self.base_url = self.config.get("base_url", get_settings().api_base_url)
```

Edit `qa_ai/runners/playwright_runner.py` line 56:
```python
from qa_ai.config.settings import get_settings
self.base_url = self.config.get("base_url", get_settings().app_base_url)
```

Edit `qa_ai/live_execution/live_scenario_runner.py` line 60:
```python
from qa_ai.config.settings import get_settings
base_url = base_url or self.config.get("base_url", get_settings().app_base_url)
```

Edit `qa_ai/exploration/ui_explorer.py` line 31 — change the dataclass field default:
```python
from qa_ai.config.settings import get_settings
# In the dataclass:
base_url: str = field(default_factory=lambda: get_settings().app_base_url)
# Also add: from dataclasses import field  (if not already imported)
```

Edit `qa_ai/orchestration/workflow_engine.py` lines 1161 and 1404:
```python
# Add near other imports (lazy import to avoid circular):
# In _run_execution at line 1161:
from qa_ai.config.settings import get_settings as _get_settings
"base_url": app_url or _get_settings().api_base_url,
# In _run_live_scenario_execution at line 1404:
"base_url": getattr(self.context, "app_url", None) or _get_settings().app_base_url,
```

- [ ] **Step 1.6: Run full suite**

```bash
python -m pytest tests/ -q
```

Expected: 813+ passed, 0 failed

- [ ] **Step 1.7: Commit**

```bash
git add qa_ai/config/settings.py tests/test_settings.py \
        qa_ai/ai/ollama_client.py qa_ai/runners/api_runner.py \
        qa_ai/runners/playwright_runner.py qa_ai/live_execution/live_scenario_runner.py \
        qa_ai/exploration/ui_explorer.py qa_ai/orchestration/workflow_engine.py \
        qa_ai/orchestration/execution_orchestrator.py
git commit -m "feat(config): add Settings module with env-var support for all URLs and timeouts"
```

---

## Task 2 — LLM Integration Hardening

**Files:**
- Modify: `qa_ai/ai/llm_router.py`
- Modify: `qa_ai/ai/ollama_client.py` (already partially done in Task 1)
- Modify: `qa_ai/ai_reasoning/ai_reasoning_orchestrator.py`
- Modify: `qa_ai/ai_orchestration/ai_audit_orchestrator.py`
- Test: `tests/test_llm_router_hardening.py`
- Test: `tests/test_ollama_client_hardening.py`

- [ ] **Step 2.1: Write failing tests**

```python
# tests/test_llm_router_hardening.py
import os
import time
import pytest
from unittest.mock import patch, MagicMock
from qa_ai.ai.llm_router import LLMRouter, ModelHealth, ModelConfig, ModelCapability


class TestCircuitBreakerMetadata:
    def test_circuit_breaker_state_is_closed_initially(self):
        router = LLMRouter()
        health = router.health.get("phi4-mini:latest", ModelHealth())
        assert health.circuit_open is False
        assert health.failure_count == 0
        assert health.last_failure_at is None
        assert health.next_retry_at is None
        assert health.current_state == "closed"

    def test_circuit_opens_after_threshold_failures(self):
        router = LLMRouter()
        model = "phi4-mini:latest"
        config = router._get_config(model)
        for _ in range(config.circuit_breaker_threshold):
            router._record_failure(model)
        health = router.health[model]
        assert health.circuit_open is True
        assert health.current_state == "open"
        assert health.next_retry_at is not None
        assert health.last_failure_at is not None

    def test_circuit_transitions_to_half_open_after_cooldown(self):
        router = LLMRouter()
        model = "phi4-mini:latest"
        config = router._get_config(model)
        for _ in range(config.circuit_breaker_threshold):
            router._record_failure(model)
        # Force cooldown elapsed
        router.health[model].circuit_opened_at = time.time() - config.circuit_breaker_cooldown - 1
        is_open = router._is_circuit_open(model)
        assert is_open is False
        assert router.health[model].current_state == "half_open"

    def test_circuit_closes_after_success(self):
        router = LLMRouter()
        model = "phi4-mini:latest"
        config = router._get_config(model)
        for _ in range(config.circuit_breaker_threshold):
            router._record_failure(model)
        router.health[model].circuit_opened_at = time.time() - config.circuit_breaker_cooldown - 1
        router._is_circuit_open(model)  # triggers half-open
        router._record_success(model, 100.0)
        assert router.health[model].current_state == "closed"


class TestEnvVarTimeouts:
    def test_llm_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("QA_AI_LLM_TIMEOUT_SECONDS", "45")
        import importlib
        import qa_ai.config.settings as mod
        mod.get_settings.cache_clear()
        importlib.reload(mod)
        from qa_ai.config.settings import get_settings
        s = get_settings()
        assert s.llm_timeout_seconds == 45
        mod.get_settings.cache_clear()

    def test_long_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("QA_AI_LLM_LONG_TIMEOUT_SECONDS", "600")
        import importlib
        import qa_ai.config.settings as mod
        mod.get_settings.cache_clear()
        importlib.reload(mod)
        from qa_ai.config.settings import get_settings
        s = get_settings()
        assert s.llm_long_timeout_seconds == 600
        mod.get_settings.cache_clear()


class TestFallbackBehavior:
    def test_all_models_failed_raises_runtime_error(self):
        router = LLMRouter()
        # Open circuit for all models in FAST_CLASSIFICATION
        models = router.model_registry.get(ModelCapability.FAST_CLASSIFICATION, [])
        for cfg in models:
            config = router._get_config(cfg.name)
            if config:
                for _ in range(config.circuit_breaker_threshold):
                    router._record_failure(cfg.name)
        with pytest.raises(RuntimeError, match="All models failed"):
            router.classify("test prompt")

    def test_fallback_to_second_model_on_first_failure(self):
        router = LLMRouter()
        models = router.model_registry.get(ModelCapability.FAST_CLASSIFICATION, [])
        if len(models) < 2:
            pytest.skip("Need at least 2 fallback models")
        first_model = models[0].name
        config = router._get_config(first_model)
        for _ in range(config.circuit_breaker_threshold):
            router._record_failure(first_model)

        call_log = []
        def fake_chat(model, prompt, system=None, temperature=0.2):
            call_log.append(model)
            return "classification_result"

        router.client.chat = fake_chat
        result = router.classify("test")
        assert result == "classification_result"
        assert models[0].name not in call_log
        assert len(call_log) >= 1
```

```python
# tests/test_ollama_client_hardening.py
import os
import pytest
from unittest.mock import patch, MagicMock
from qa_ai.ai.ollama_client import OllamaClient


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("QA_AI_OLLAMA_BASE_URL", "http://custom:11434")
    import importlib
    import qa_ai.config.settings as mod
    mod.get_settings.cache_clear()
    importlib.reload(mod)
    client = OllamaClient()
    assert client.base_url == "http://custom:11434"
    mod.get_settings.cache_clear()


def test_explicit_base_url_overrides_env(monkeypatch):
    monkeypatch.setenv("QA_AI_OLLAMA_BASE_URL", "http://custom:11434")
    client = OllamaClient(base_url="http://explicit:11434")
    assert client.base_url == "http://explicit:11434"


def test_trailing_slash_stripped():
    client = OllamaClient(base_url="http://localhost:11434/")
    assert client.base_url == "http://localhost:11434"


def test_chat_uses_configurable_timeout():
    client = OllamaClient()
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "ok"}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        client.chat("test-model", "hello")
        _, kwargs = mock_post.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] >= 60  # must be >= 60s for any real model call
```

- [ ] **Step 2.2: Verify tests fail**

```bash
python -m pytest tests/test_llm_router_hardening.py tests/test_ollama_client_hardening.py -v 2>&1 | head -40
```

Expected: `AttributeError: 'ModelHealth' object has no attribute 'last_failure_at'`

- [ ] **Step 2.3: Enhance `ModelHealth` in `qa_ai/ai/llm_router.py`**

Find the `ModelHealth` dataclass (around line 51) and replace it:

```python
@dataclass
class ModelHealth:
    is_available: bool = True
    last_checked: float = 0.0
    failure_count: int = 0
    circuit_open: bool = False
    circuit_opened_at: float = 0.0
    last_failure_at: Optional[float] = None
    next_retry_at: Optional[float] = None
    total_calls: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0

    @property
    def current_state(self) -> str:
        if not self.circuit_open:
            return "closed"
        # half_open state is set by _is_circuit_open when cooldown elapsed
        if getattr(self, "_half_open", False):
            return "half_open"
        return "open"
```

- [ ] **Step 2.4: Update `_record_failure` to set `last_failure_at` and `next_retry_at`**

Find `_record_failure` (around line 577) and update:

```python
def _record_failure(self, model_name: str):
    if model_name not in self.health:
        self.health[model_name] = ModelHealth()

    health = self.health[model_name]
    health.total_calls += 1
    health.total_failures += 1
    health.failure_count += 1
    health.last_failure_at = time.time()

    config = self._get_config(model_name)
    if config and health.failure_count >= config.circuit_breaker_threshold:
        health.circuit_open = True
        health.circuit_opened_at = time.time()
        health.next_retry_at = time.time() + config.circuit_breaker_cooldown
        health.is_available = False
        logger.warning(
            "Circuit breaker OPEN for %s (%d consecutive failures). "
            "Next retry at: %.0f (in %ds)",
            model_name, health.failure_count,
            health.next_retry_at, config.circuit_breaker_cooldown,
        )
```

- [ ] **Step 2.5: Update `_is_circuit_open` to track half-open state**

Find `_is_circuit_open` (around line 528):

```python
def _is_circuit_open(self, model_name: str) -> bool:
    health = self.health.get(model_name)
    if not health or not health.circuit_open:
        return False

    config = self._get_config(model_name)
    if not config:
        return True

    cooldown_elapsed = (time.time() - health.circuit_opened_at) > config.circuit_breaker_cooldown

    if cooldown_elapsed:
        health.circuit_open = False
        health.failure_count = 0
        health.is_available = True
        health.next_retry_at = None
        health._half_open = True  # transient flag, cleared on next record_success
        logger.info("Circuit breaker HALF-OPEN for %s (cooldown elapsed)", model_name)
        return False

    return True
```

- [ ] **Step 2.6: Update `_record_success` to clear half-open flag**

Find `_record_success` (around line 560), add at the end:

```python
    health.is_available = True
    if getattr(health, "_half_open", False):
        health._half_open = False
        logger.info("Circuit breaker CLOSED for %s (recovered after half-open)", model_name)
```

- [ ] **Step 2.7: Wire settings timeouts into ModelConfig defaults**

Add near the top of `llm_router.py` after imports:

```python
from qa_ai.config.settings import get_settings as _get_settings

def _default_timeout() -> int:
    return _get_settings().llm_timeout_seconds

def _long_timeout() -> int:
    return _get_settings().llm_long_timeout_seconds
```

Then update `ModelConfig` timeout defaults in the registry. Find models with `timeout=180` or `timeout=300` and replace with:
- Standard models: `timeout=_default_timeout()`
- Deep reasoning models: `timeout=_long_timeout()`

Example for QA_REASONING primary:
```python
ModelConfig(
    "qwen3.5:9b",
    ModelCapability.QA_REASONING,
    max_context_tokens=8192,
    max_output_tokens=4096,
    temperature=0.2,
    timeout=_default_timeout(),
),
```

**Note:** Only change models currently using `timeout=120` (default) or `timeout=180`. Models with explicit `timeout=60` (fast classification) keep 60. Models with `timeout=300` (DEEP_REASONING) use `_long_timeout()`.

- [ ] **Step 2.8: Wire health-check timeout to settings in both orchestrators**

In `qa_ai/ai_reasoning/ai_reasoning_orchestrator.py`:
```python
from qa_ai.config.settings import get_settings as _get_settings

def _detect_model_availability(self) -> bool:
    url = _get_settings().ollama_base_url + "/api/tags"
    timeout = _get_settings().llm_health_check_timeout
    for attempt in range(2):
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            logger.debug("Ollama availability check failed (attempt %d): %s", attempt + 1, e)
    return False
```

Apply the same pattern to `qa_ai/ai_orchestration/ai_audit_orchestrator.py` `_model_available`.

- [ ] **Step 2.9: Run hardening tests**

```bash
python -m pytest tests/test_llm_router_hardening.py tests/test_ollama_client_hardening.py -v
```

Expected: all pass

- [ ] **Step 2.10: Run full suite**

```bash
python -m pytest tests/ -q
```

Expected: 813+ passed, 0 failed

- [ ] **Step 2.11: Commit**

```bash
git add qa_ai/ai/llm_router.py qa_ai/ai/ollama_client.py \
        qa_ai/ai_reasoning/ai_reasoning_orchestrator.py \
        qa_ai/ai_orchestration/ai_audit_orchestrator.py \
        tests/test_llm_router_hardening.py tests/test_ollama_client_hardening.py
git commit -m "feat(llm): enhance circuit breaker metadata, configurable timeouts via env vars"
```

---

## Task 3 — Error Handling Hardening

**Files:**
- Create: `qa_ai/utils/error_handling.py`
- Modify: 16 files listed in the graph context section above
- Test: `tests/test_error_handling.py`

- [ ] **Step 3.1: Write failing tests**

```python
# tests/test_error_handling.py
import logging
import pytest
from unittest.mock import patch
from qa_ai.utils.error_handling import log_and_fallback, safe_fallback


class TestLogAndFallback:
    def test_returns_default_on_exception(self):
        def boom():
            raise ValueError("test error")

        result = log_and_fallback(boom, default=None, logger_name="test")
        assert result is None

    def test_returns_value_when_no_exception(self):
        def ok():
            return 42

        result = log_and_fallback(ok, default=None, logger_name="test")
        assert result == 42

    def test_logs_warning_on_exception(self, caplog):
        def boom():
            raise RuntimeError("something broke")

        with caplog.at_level(logging.WARNING, logger="test"):
            log_and_fallback(boom, default=None, logger_name="test", context="my_operation")

        assert "my_operation" in caplog.text or "something broke" in caplog.text

    def test_custom_default_returned(self):
        def boom():
            raise Exception("err")

        result = log_and_fallback(boom, default={"status": "unavailable"}, logger_name="test")
        assert result == {"status": "unavailable"}

    def test_safe_fallback_decorator(self):
        @safe_fallback(default=[], logger_name="test")
        def risky(x):
            if x < 0:
                raise ValueError("negative")
            return [x]

        assert risky(5) == [5]
        assert risky(-1) == []


class TestWorkflowEngineDurationFallback:
    """Verify workflow_engine silent handler was replaced with logged fallback."""
    def test_bad_iso_date_does_not_crash_phase(self):
        """PhaseResult duration calculation should not crash on bad timestamps."""
        from qa_ai.orchestration.workflow_engine import PhaseResult, WorkflowPhase
        r = PhaseResult(phase=WorkflowPhase.DISCOVERY)
        r.started_at = "not-a-date"
        r.completed_at = "also-not-a-date"
        # Should not raise; duration_seconds stays None or 0
        assert r.duration_seconds is None or r.duration_seconds == 0.0
```

- [ ] **Step 3.2: Verify tests fail**

```bash
python -m pytest tests/test_error_handling.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'qa_ai.utils.error_handling'`

- [ ] **Step 3.3: Create `qa_ai/utils/error_handling.py`**

```python
"""
error_handling.py - Centralized helpers for observable safe fallbacks.

Use log_and_fallback() to replace silent `except Exception: pass` blocks
while preserving the safe-fallback behavior and making failures visible.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


def log_and_fallback(
    fn: Callable[[], T],
    default: T,
    logger_name: str,
    context: str = "",
    level: int = logging.WARNING,
) -> T:
    """
    Call fn(); if it raises, log the exception and return default.

    Args:
        fn: Zero-argument callable to attempt.
        default: Value to return if fn raises.
        logger_name: Logger name (use __name__ from calling module).
        context: Human-readable description of the operation for the log message.
        level: Log level (default WARNING).

    Returns:
        fn() result on success, default on failure.
    """
    try:
        return fn()
    except Exception as e:
        log = logging.getLogger(logger_name)
        msg = f"Safe fallback triggered"
        if context:
            msg = f"{context}: safe fallback triggered"
        log.log(level, "%s — %s: %s", msg, type(e).__name__, e)
        return default


def safe_fallback(
    default: Any,
    logger_name: str,
    context: str = "",
    level: int = logging.WARNING,
) -> Callable:
    """
    Decorator version of log_and_fallback.

    @safe_fallback(default=[], logger_name=__name__, context="scan routes")
    def risky_scan(path):
        ...
    """
    def decorator(fn: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                log = logging.getLogger(logger_name)
                label = context or fn.__qualname__
                log.log(level, "%s: safe fallback triggered — %s: %s", label, type(e).__name__, e)
                return default
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return decorator
```

- [ ] **Step 3.4: Fix remaining 24 silent exception handlers**

For each file below, replace the bare `except Exception:` (followed by `pass` or `continue` or `return`) with a logged version. Use the `logger` already present in the file, or add one if missing.

**`qa_ai/orchestration/workflow_engine.py:1059`**
```python
# Before:
            except Exception:
                pass
# After:
            except Exception as e:
                logger.debug("Phase duration calculation failed: %s", e)
```

**`qa_ai/runners/api_runner.py:340,344`**
Read lines 335-350 first, then add `logger.debug` to both handlers. Pattern:
```python
except Exception as e:
    logger.debug("API runner cleanup failed: %s", e)
```

**`qa_ai/runners/playwright_runner.py:279`**
```python
except Exception as e:
    logger.debug("Playwright runner cleanup failed: %s", e)
```

**`qa_ai/live_execution/visual_regression.py:100`**
```python
except Exception as e:
    logger.debug("Screenshot comparison failed: %s", e)
```

**`qa_ai/live_execution/session_manager.py:97,111,177`** — add logger if missing, log each:
```python
except Exception as e:
    logger.debug("Session manager operation failed: %s", e)
```

**`qa_ai/live_execution/api_session_manager.py:153`**
```python
except Exception as e:
    logger.debug("API session cleanup failed: %s", e)
```

**`qa_ai/platform_performance/memory_usage_tracker.py:46,61`**
```python
except Exception as e:
    logger.debug("Memory usage probe failed: %s", e)
```

**`qa_ai/runtime_lab/docker_runtime.py:34`**
```python
except Exception as e:
    logger.debug("Docker runtime probe failed: %s", e)
```

**`qa_ai/mobile_runtime/android_emulator_manager.py:107,121,133`**
```python
except Exception as e:
    logger.debug("Android emulator probe failed: %s", e)
```

**`qa_ai/mobile_runtime/ios_simulator_manager.py:81,93`**
```python
except Exception as e:
    logger.debug("iOS simulator probe failed: %s", e)
```

**`qa_ai/ai_reasoning/semantic_rca_engine.py:131`**
```python
except Exception as e:
    logger.debug("Semantic RCA step failed: %s", e)
```

**`qa_ai/mobile_runtime/device_registry.py:149`**
```python
except Exception as e:
    logger.debug("Device registry probe failed: %s", e)
```

**`qa_ai/ai_reasoning/scenario_generator.py:150`**
```python
except Exception as e:
    logger.debug("Scenario generation step failed: %s", e)
```

**`qa_ai/mobile_runtime/device_log_collector.py:95`**
```python
except Exception as e:
    logger.debug("Device log collection failed: %s", e)
```

**`qa_ai/ai_orchestration/ai_audit_orchestrator.py:99`** (inner try of `_model_available`):
```python
except Exception as e:
    logger.debug("LLM router health check failed: %s", e)
```

For files missing a `logger`, add at top after imports:
```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 3.5: Run error handling tests**

```bash
python -m pytest tests/test_error_handling.py -v
```

Expected: all pass

- [ ] **Step 3.6: Run full suite**

```bash
python -m pytest tests/ -q
```

Expected: 813+ passed, 0 failed

- [ ] **Step 3.7: Commit**

```bash
git add qa_ai/utils/error_handling.py tests/test_error_handling.py \
        qa_ai/orchestration/workflow_engine.py \
        qa_ai/runners/api_runner.py qa_ai/runners/playwright_runner.py \
        qa_ai/live_execution/visual_regression.py qa_ai/live_execution/session_manager.py \
        qa_ai/live_execution/api_session_manager.py \
        qa_ai/platform_performance/memory_usage_tracker.py \
        qa_ai/runtime_lab/docker_runtime.py \
        qa_ai/mobile_runtime/android_emulator_manager.py \
        qa_ai/mobile_runtime/ios_simulator_manager.py \
        qa_ai/ai_reasoning/semantic_rca_engine.py \
        qa_ai/mobile_runtime/device_registry.py \
        qa_ai/ai_reasoning/scenario_generator.py \
        qa_ai/mobile_runtime/device_log_collector.py \
        qa_ai/ai_orchestration/ai_audit_orchestrator.py
git commit -m "fix(errors): replace all silent exception handlers with logged fallbacks"
```

---

## Task 4 — Security Hardening: Safe Subprocess Utility

**Files:**
- Create: `qa_ai/utils/safe_subprocess.py`
- Modify: `qa_ai/improvement/retest_orchestrator.py` (already uses shlex, wire to safe_subprocess)
- Modify: `qa_ai/runtime_lab/process_manager.py` (uses Popen — keep, but add env sanitization)
- Test: `tests/test_safe_subprocess.py`

> **Context:** `shell=True` was already removed in the previous session. This task adds a secure helper that future code must use, blocks known-dangerous commands, sanitizes env, and audit-logs every execution.

- [ ] **Step 4.1: Write failing tests**

```python
# tests/test_safe_subprocess.py
import os
import pytest
from qa_ai.utils.safe_subprocess import run_safe, CommandBlockedError, SafeSubprocessConfig


class TestCommandBlocking:
    def test_shell_metacharacters_are_not_interpreted(self):
        """list-mode invocation; no shell expansion."""
        result = run_safe(["echo", "hello; echo INJECTED"])
        assert "INJECTED" not in result.stdout
        assert "hello; echo INJECTED" in result.stdout

    def test_destructive_command_is_blocked(self):
        with pytest.raises(CommandBlockedError, match="destructive"):
            run_safe(["rm", "-rf", "/"])

    def test_rm_rf_variant_is_blocked(self):
        with pytest.raises(CommandBlockedError, match="destructive"):
            run_safe(["rm", "-rf", "/tmp/something"])

    def test_sudo_is_blocked_by_default(self):
        with pytest.raises(CommandBlockedError, match="blocked"):
            run_safe(["sudo", "anything"])

    def test_dd_is_blocked(self):
        with pytest.raises(CommandBlockedError, match="destructive"):
            run_safe(["dd", "if=/dev/zero", "of=/dev/sda"])

    def test_allowed_command_succeeds(self):
        result = run_safe(["echo", "safe"])
        assert result.returncode == 0
        assert "safe" in result.stdout

    def test_pytest_command_is_allowed(self):
        """pytest is a known safe test runner."""
        result = run_safe(["python", "-c", "print('ok')"])
        assert result.returncode == 0


class TestTimeout:
    def test_timeout_is_enforced(self):
        import subprocess
        from qa_ai.utils.safe_subprocess import run_safe, SubprocessTimeoutError
        with pytest.raises(SubprocessTimeoutError):
            run_safe(["sleep", "10"], timeout=1)


class TestEnvSanitization:
    def test_dangerous_env_vars_are_stripped(self):
        """LD_PRELOAD and LD_LIBRARY_PATH must not be forwarded."""
        env_override = {"LD_PRELOAD": "/evil.so", "MY_VAR": "hello"}
        result = run_safe(
            ["python", "-c", "import os; print(os.environ.get('LD_PRELOAD', 'STRIPPED'))"],
            extra_env=env_override,
        )
        assert "STRIPPED" in result.stdout
        assert "/evil.so" not in result.stdout

    def test_safe_env_var_is_forwarded(self):
        result = run_safe(
            ["python", "-c", "import os; print(os.environ.get('MY_SAFE_VAR', 'missing'))"],
            extra_env={"MY_SAFE_VAR": "present"},
        )
        assert "present" in result.stdout


class TestCwdValidation:
    def test_nonexistent_cwd_raises(self):
        from qa_ai.utils.safe_subprocess import InvalidCwdError
        with pytest.raises(InvalidCwdError):
            run_safe(["echo", "hi"], cwd="/nonexistent/path/xyz")

    def test_valid_cwd_works(self, tmp_path):
        result = run_safe(["echo", "ok"], cwd=str(tmp_path))
        assert result.returncode == 0


class TestAuditLogging:
    def test_command_is_audit_logged(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="qa_ai.utils.safe_subprocess"):
            run_safe(["echo", "audit_test"])
        assert "echo" in caplog.text
```

- [ ] **Step 4.2: Verify tests fail**

```bash
python -m pytest tests/test_safe_subprocess.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'qa_ai.utils.safe_subprocess'`

- [ ] **Step 4.3: Create `qa_ai/utils/safe_subprocess.py`**

```python
"""
safe_subprocess.py - Security-hardened subprocess execution helper.

Replaces direct subprocess.run() with shell=True.
All process execution in qa_ai SHOULD use run_safe() for:
 - command allowlist/denylist enforcement
 - no shell interpolation
 - env sanitization
 - cwd validation
 - timeout enforcement
 - audit logging
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# ─── Exceptions ────────────────────────────────────────

class CommandBlockedError(ValueError):
    """Raised when a command is blocked by the safety policy."""

class SubprocessTimeoutError(TimeoutError):
    """Raised when a subprocess exceeds its timeout."""

class InvalidCwdError(ValueError):
    """Raised when the specified cwd does not exist."""


# ─── Block / Strip lists ───────────────────────────────

# Commands that should never be executed by the QA platform
_BLOCKED_EXECUTABLES = frozenset({
    "sudo", "su", "doas", "pkexec",
})

# Argument patterns that indicate a destructive rm operation
_DESTRUCTIVE_RM_ARGS = frozenset({"-rf", "-fr", "-r", "--recursive"})

# Environment variables that must never be forwarded to subprocesses
_STRIP_ENV_KEYS = frozenset({
    "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
    "DYLD_LIBRARY_PATH", "PYTHONSTARTUP", "PYTHONINSPECT",
})


# ─── Result ────────────────────────────────────────────

@dataclass
class SubprocessResult:
    returncode: int
    stdout: str
    stderr: str
    command: List[str] = field(default_factory=list)


# ─── Safety checks ─────────────────────────────────────

def _check_blocked(cmd: Sequence[str]) -> None:
    """Raise CommandBlockedError if cmd violates the safety policy."""
    if not cmd:
        raise CommandBlockedError("Empty command")

    executable = Path(cmd[0]).name  # strip path prefix

    if executable in _BLOCKED_EXECUTABLES:
        raise CommandBlockedError(
            f"Command '{executable}' is blocked by the safe subprocess policy"
        )

    # Block destructive rm variants: rm -rf / or rm -rf /*
    if executable == "rm":
        args = set(cmd[1:])
        # Check for recursive flags
        has_recursive = bool(args & _DESTRUCTIVE_RM_ARGS)
        # Combined flag like -rf
        has_combined = any(
            a.startswith("-") and "r" in a.lstrip("-")
            for a in args
        )
        if has_recursive or has_combined:
            raise CommandBlockedError(
                "Destructive command blocked: rm with recursive/force flags"
            )

    # Block disk-level destructive commands
    if executable in ("dd", "mkfs", "fdisk", "parted", "wipefs"):
        raise CommandBlockedError(
            f"Destructive command blocked: {executable}"
        )


def _sanitize_env(extra_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Build a clean environment: inherit os.environ, strip dangerous keys,
    then overlay extra_env (also stripped).
    """
    clean = {k: v for k, v in os.environ.items() if k not in _STRIP_ENV_KEYS}
    if extra_env:
        for k, v in extra_env.items():
            if k not in _STRIP_ENV_KEYS:
                clean[k] = v
            else:
                logger.warning("Stripping dangerous env var from subprocess: %s", k)
    return clean


def _validate_cwd(cwd: Optional[str]) -> None:
    if cwd is not None and not Path(cwd).is_dir():
        raise InvalidCwdError(f"cwd does not exist or is not a directory: {cwd!r}")


# ─── Public API ────────────────────────────────────────

def run_safe(
    cmd: Sequence[str],
    timeout: int = 30,
    cwd: Optional[str] = None,
    extra_env: Optional[Dict[str, str]] = None,
    capture_output: bool = True,
    check: bool = False,
) -> SubprocessResult:
    """
    Execute cmd safely: no shell=True, blocked-command check, env sanitization,
    cwd validation, timeout enforcement, and audit logging.

    Args:
        cmd: Command as a list (e.g. ["pytest", "tests/", "-v"]).
        timeout: Max seconds to wait. Raises SubprocessTimeoutError on expiry.
        cwd: Working directory. Must exist if provided.
        extra_env: Additional env vars to merge (dangerous keys stripped).
        capture_output: Capture stdout/stderr (default True).
        check: If True, raise subprocess.CalledProcessError on non-zero exit.

    Returns:
        SubprocessResult with returncode, stdout, stderr.

    Raises:
        CommandBlockedError: Command violates the safety policy.
        InvalidCwdError: cwd does not exist.
        SubprocessTimeoutError: Process exceeded timeout.
    """
    cmd_list = list(cmd)

    _check_blocked(cmd_list)
    _validate_cwd(cwd)
    env = _sanitize_env(extra_env)

    logger.info(
        "safe_subprocess: %s (cwd=%s, timeout=%ds)",
        " ".join(shlex.quote(c) for c in cmd_list),
        cwd or ".",
        timeout,
    )

    try:
        result = subprocess.run(
            cmd_list,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            check=check,
        )
        return SubprocessResult(
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            command=cmd_list,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "safe_subprocess TIMEOUT after %ds: %s",
            timeout, " ".join(cmd_list),
        )
        raise SubprocessTimeoutError(
            f"Command timed out after {timeout}s: {cmd_list}"
        )
    except subprocess.CalledProcessError:
        raise
    except Exception as e:
        logger.error("safe_subprocess error: %s — %s", " ".join(cmd_list), e)
        raise
```

- [ ] **Step 4.4: Run safe subprocess tests**

```bash
python -m pytest tests/test_safe_subprocess.py -v
```

Expected: all pass

- [ ] **Step 4.5: Wire `retest_orchestrator.py` to use `run_safe`**

In `qa_ai/improvement/retest_orchestrator.py`, replace:
```python
import shlex
import subprocess
```
with:
```python
from qa_ai.utils.safe_subprocess import run_safe, CommandBlockedError, SubprocessTimeoutError
```

Replace the `_run_test` method's subprocess call:
```python
        # Before:
        completed = subprocess.run(shlex.split(command), text=True, capture_output=True, check=False)
        return {
            "test_id": test.get("id"),
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }

        # After:
        try:
            completed = run_safe(shlex.split(command), timeout=120)
            return {
                "test_id": test.get("id"),
                "status": "passed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        except (CommandBlockedError, SubprocessTimeoutError) as e:
            return {
                "test_id": test.get("id"),
                "status": "blocked",
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }
```

Also add `import shlex` back at the top since it's still needed.

- [ ] **Step 4.6: Run full suite**

```bash
python -m pytest tests/ -q
```

Expected: 813+ passed, 0 failed

- [ ] **Step 4.7: Commit**

```bash
git add qa_ai/utils/safe_subprocess.py tests/test_safe_subprocess.py \
        qa_ai/improvement/retest_orchestrator.py
git commit -m "feat(security): add safe_subprocess utility with allowlist, env sanitization, audit logging"
```

---

## Task 5 — WorkflowEngine God Class Decomposition

**Files:**
- Create: `qa_ai/orchestration/phase_handlers/__init__.py`
- Create: `qa_ai/orchestration/phase_handlers/audit_phase_mixin.py`
- Create: `qa_ai/orchestration/phase_handlers/live_phase_mixin.py`
- Create: `qa_ai/orchestration/phase_handlers/improvement_phase_mixin.py`
- Create: `qa_ai/orchestration/phase_handlers/cicd_phase_mixin.py`
- Create: `qa_ai/orchestration/phase_handlers/extended_phase_mixin.py`
- Create: `qa_ai/orchestration/phase_handlers/ai_phase_mixin.py`
- Modify: `qa_ai/orchestration/workflow_engine.py`
- Test: `tests/test_god_class_refactor.py`

**Strategy:** Extract phase handler methods into mixin classes. `WorkflowEngine` inherits from all mixins. Public API (`run()`, `__init__`, all `_run_*` names) is fully preserved. The `_execute_phase` dispatch method stays in `workflow_engine.py`. No imports from outside change.

**Target:** `workflow_engine.py` goes from 2717 lines to ~650 lines. Each mixin is ~150-350 lines.

- [ ] **Step 5.1: Write failing tests (run BEFORE the refactor)**

```python
# tests/test_god_class_refactor.py
"""
Smoke tests that verify WorkflowEngine's public API is intact after the
mixin-based decomposition. Run BEFORE refactoring to establish a baseline,
then re-run AFTER to confirm nothing broke.
"""
import pytest
from unittest.mock import MagicMock, patch
from qa_ai.orchestration.workflow_engine import WorkflowEngine, WorkflowPhase, WorkflowResult


class TestWorkflowEnginePublicAPI:
    def _make_engine(self):
        store = MagicMock()
        store.load_artifact.return_value = {}
        store.save_artifact.return_value = None
        registry = MagicMock()
        registry.assess.return_value = MagicMock(can_run_web=False, can_run_api=False)
        orchestrator = MagicMock()
        orchestrator.setup.return_value = MagicMock(success=True, skipped=False)
        return WorkflowEngine(artifact_store=store, registry=registry, orchestrator=orchestrator)

    def test_init_succeeds(self):
        engine = self._make_engine()
        assert engine is not None
        assert hasattr(engine, "store")
        assert hasattr(engine, "registry")
        assert hasattr(engine, "orchestrator")

    def test_run_method_exists_and_callable(self):
        engine = self._make_engine()
        assert callable(engine.run)

    def test_all_phase_methods_exist(self):
        """Every _run_* method must still exist on WorkflowEngine after refactor."""
        engine = self._make_engine()
        phase_methods = [
            "_run_discovery", "_run_intelligence", "_run_planning",
            "_run_environment", "_run_execution", "_run_exploration",
            "_run_security_audit", "_run_api_audit", "_run_database_audit",
            "_run_sync_audit", "_run_code_quality_audit", "_run_dependency_audit",
            "_run_release_readiness_audit", "_run_performance", "_run_evidence",
            "_run_finding_correlation", "_run_root_cause_analysis", "_run_rca",
            "_run_reporting",
            "_run_live_scenario_execution", "_run_trace_capture",
            "_run_replay_analysis", "_run_visual_regression",
            "_run_runtime_validation", "_run_scenario_execution",
            "_run_behavior_analysis", "_run_execution_replay",
            "_run_evidence_correlation",
            "_run_software_health_assessment", "_run_improvement_planning",
            "_run_change_impact_analysis", "_run_remediation_planning",
            "_run_patch_generation", "_run_change_simulation",
            "_run_rollback_planning", "_run_remediation_retest_scope",
            "_run_remediation_risk_analysis", "_run_remediation_validation",
            "_run_remediation_approval", "_run_remediation_sandbox",
            "_run_ci_provider_detection", "_run_ci_workflow_planning",
            "_run_release_gate", "_run_cicd_reporting",
            "_run_ai_reasoning_context", "_run_semantic_rca",
            "_run_adaptive_audit_planning", "_run_evidence_synthesis",
            "_run_ai_scenario_generation", "_run_ai_fix_reasoning",
            "_run_learning_optimization", "_run_report_generation",
            "_run_dashboard_build",
        ]
        missing = [m for m in phase_methods if not hasattr(engine, m)]
        assert missing == [], f"Missing methods after refactor: {missing}"

    def test_default_phases_returns_list(self):
        from qa_ai.runtime.execution_context import Platform
        engine = self._make_engine()
        phases = engine._default_phases(Platform.UNKNOWN)
        assert isinstance(phases, list)
        assert len(phases) > 0
        assert all(isinstance(p, WorkflowPhase) for p in phases)

    def test_get_workflow_engine_factory(self):
        from qa_ai.orchestration.workflow_engine import get_workflow_engine
        engine = get_workflow_engine()
        assert isinstance(engine, WorkflowEngine)

    def test_no_circular_imports(self):
        """Importing the mixin package must not cause circular import errors."""
        import qa_ai.orchestration.phase_handlers.audit_phase_mixin  # noqa
        import qa_ai.orchestration.phase_handlers.live_phase_mixin  # noqa
        import qa_ai.orchestration.phase_handlers.improvement_phase_mixin  # noqa
        import qa_ai.orchestration.phase_handlers.cicd_phase_mixin  # noqa
        import qa_ai.orchestration.phase_handlers.ai_phase_mixin  # noqa
        import qa_ai.orchestration.phase_handlers.extended_phase_mixin  # noqa
```

- [ ] **Step 5.2: Run tests BEFORE refactor (should already pass on all except `test_no_circular_imports`)**

```bash
python -m pytest tests/test_god_class_refactor.py -v
```

Expected: Most pass, `test_no_circular_imports` fails with `ModuleNotFoundError`.

- [ ] **Step 5.3: Create the package marker**

```python
# qa_ai/orchestration/phase_handlers/__init__.py
"""Phase handler mixins for WorkflowEngine decomposition."""
```

- [ ] **Step 5.4: Extract audit phase methods → `audit_phase_mixin.py`**

Create `qa_ai/orchestration/phase_handlers/audit_phase_mixin.py`.

The mixin class receives `self.store`, `self.context` from `WorkflowEngine`. Copy the following methods verbatim from `workflow_engine.py` into this file:

Methods to extract: `_run_security_audit`, `_run_api_audit`, `_run_database_audit`, `_run_sync_audit`, `_run_code_quality_audit`, `_run_dependency_audit`, `_run_release_readiness_audit`, `_run_performance`, `_run_evidence`, `_run_finding_correlation`, `_run_rca`, `_run_root_cause_analysis`, `_run_reporting`

File template:
```python
"""
audit_phase_mixin.py - Audit and evidence phase handlers for WorkflowEngine.
Extracted from workflow_engine.py to reduce file size.
All methods use self.store and self.context which are provided by WorkflowEngine.
"""
from __future__ import annotations
from typing import Dict, Any


class AuditPhaseMixin:
    """Mixin providing audit, evidence, and RCA phase handler methods."""

    def _run_security_audit(self) -> Dict[str, Any]:
        """Security audit phase."""
        # PASTE EXACT METHOD BODY FROM workflow_engine.py HERE
        ...

    # ... paste all 13 methods
```

- [ ] **Step 5.5: Extract live execution phase methods → `live_phase_mixin.py`**

Methods: `_run_live_scenario_execution`, `_run_trace_capture`, `_run_replay_analysis`, `_run_visual_regression`, `_run_runtime_validation`, `_run_scenario_execution`, `_run_behavior_analysis`, `_run_execution_replay`, `_run_evidence_correlation`

```python
# qa_ai/orchestration/phase_handlers/live_phase_mixin.py
from __future__ import annotations
from typing import Dict, Any

class LivePhaseMixin:
    """Mixin providing live-execution, trace, replay, and visual regression phase handlers."""
    # paste 9 methods
```

- [ ] **Step 5.6: Extract improvement/remediation methods → `improvement_phase_mixin.py`**

Methods (20 total): `_run_software_health_assessment`, `_run_improvement_planning`, `_run_change_impact_analysis`, `_run_remediation_planning`, `_run_patch_generation`, `_run_change_simulation`, `_run_rollback_planning`, `_run_remediation_retest_scope`, `_run_remediation_risk_analysis`, `_run_remediation_validation`, `_run_remediation_approval`, `_run_remediation_sandbox`, `_run_remediation_patch_proposal`, `_run_remediation_change_simulation`, `_run_remediation_rollback_planning`, `_run_remediation_retest_optimization`, `_run_remediation_approval_workflow`, `_run_remediation_audit_logging`, `_run_retest_orchestration`, `_run_regression_guard`

```python
# qa_ai/orchestration/phase_handlers/improvement_phase_mixin.py
from __future__ import annotations
from typing import Dict, Any

class ImprovementPhaseMixin:
    """Mixin providing improvement, remediation, and retest phase handlers."""
    # paste 20 methods
```

- [ ] **Step 5.7: Extract CI/CD methods → `cicd_phase_mixin.py`**

Methods (13 total): `_run_ci_provider_detection`, `_run_ci_workflow_planning`, `_run_incremental_audit_planning`, `_run_baseline_comparison`, `_run_release_gate`, `_run_cicd_reporting`, `_run_cicd_provider_detection`, `_run_cicd_workflow_planning`, `_run_incremental_audit_analysis`, `_run_release_gate_evaluation`, `_run_pipeline_policy_validation`, `_run_pr_audit_orchestration`, `_run_cicd_audit_logging`

```python
# qa_ai/orchestration/phase_handlers/cicd_phase_mixin.py
from __future__ import annotations
from typing import Dict, Any

class CICDPhaseMixin:
    """Mixin providing CI/CD phase handlers."""
    # paste 13 methods
```

- [ ] **Step 5.8: Extract extended platform/enterprise/distributed/mobile methods → `extended_phase_mixin.py`**

Methods (~32 total): all `_run_performance_profiling`, `_run_workflow_timing_analysis`, `_run_artifact_*`, `_run_evidence_storage_optimization`, `_run_incremental_graph_planning`, `_run_parallel_execution_planning`, `_run_memory_usage_tracking`, `_run_scalability_assessment`, all `_run_workspace_*`, `_run_project_registry_management`, `_run_team_registry_management`, `_run_rbac_*`, `_run_governance_*`, `_run_audit_history_management`, `_run_access_audit_logging`, all `_run_benchmark_*`, `_run_quality_tracking`, `_run_learning_update`, `_run_cross_project_learning_analysis`, `_run_self_optimization_reporting`, all `_run_distributed_runtime`, `_run_multi_actor_simulation`, `_run_concurrency_simulation`, `_run_offline_recovery`, `_run_sync_conflict_analysis`, `_run_chaos_testing`, `_run_distributed_evidence_correlation`, all `_run_mobile_*`

```python
# qa_ai/orchestration/phase_handlers/extended_phase_mixin.py
from __future__ import annotations
from typing import Dict, Any

class ExtendedPhaseMixin:
    """Mixin providing platform-performance, enterprise, benchmark, self-opt, distributed, and mobile phase handlers."""
    # paste ~32 methods
```

- [ ] **Step 5.9: Extract AI orchestration + reporting methods → `ai_phase_mixin.py`**

Methods (~19 total): all `_run_ai_*`, `_run_semantic_rca`, `_run_adaptive_audit_planning`, `_run_evidence_synthesis`, `_run_semantic_risk_reasoning`, `_run_learning_optimization`, `_run_report_generation`, `_run_dashboard_build`, `_run_visualization_export`, `_run_quality_tracking_report`, `_run_audit_memory_update`, `_run_strategy_adaptation`, `_run_finding_deduplication`, `_run_confidence_calibration`, `_run_evidence_quality_optimization`, `_run_scenario_optimization`, `_run_risk_prediction`, `_run_remediation_learning`

```python
# qa_ai/orchestration/phase_handlers/ai_phase_mixin.py
from __future__ import annotations
from typing import Dict, Any

class AIPhaseMixin:
    """Mixin providing AI orchestration, self-optimization, and reporting phase handlers."""
    # paste ~19 methods
```

- [ ] **Step 5.10: Update `workflow_engine.py` to use all mixins**

At the top of `workflow_engine.py`, add the mixin imports and update the class definition:

```python
# After existing imports, add:
from qa_ai.orchestration.phase_handlers.audit_phase_mixin import AuditPhaseMixin
from qa_ai.orchestration.phase_handlers.live_phase_mixin import LivePhaseMixin
from qa_ai.orchestration.phase_handlers.improvement_phase_mixin import ImprovementPhaseMixin
from qa_ai.orchestration.phase_handlers.cicd_phase_mixin import CICDPhaseMixin
from qa_ai.orchestration.phase_handlers.extended_phase_mixin import ExtendedPhaseMixin
from qa_ai.orchestration.phase_handlers.ai_phase_mixin import AIPhaseMixin

# Change class definition from:
class WorkflowEngine:

# To:
class WorkflowEngine(
    AuditPhaseMixin,
    LivePhaseMixin,
    ImprovementPhaseMixin,
    CICDPhaseMixin,
    ExtendedPhaseMixin,
    AIPhaseMixin,
):
```

Then **delete** the extracted methods from `workflow_engine.py` (they now come from the mixins).

- [ ] **Step 5.11: Verify `workflow_engine.py` line count has reduced**

```bash
wc -l "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/qa_ai/orchestration/workflow_engine.py"
```

Expected: < 750 lines (down from 2717)

- [ ] **Step 5.12: Run refactor tests**

```bash
python -m pytest tests/test_god_class_refactor.py -v
```

Expected: all pass including `test_no_circular_imports`

- [ ] **Step 5.13: Run full test suite**

```bash
python -m pytest tests/ -q
```

Expected: 813+ passed, 0 failed

- [ ] **Step 5.14: Commit**

```bash
git add qa_ai/orchestration/phase_handlers/ \
        qa_ai/orchestration/workflow_engine.py \
        tests/test_god_class_refactor.py
git commit -m "refactor(structure): decompose 2717-line WorkflowEngine into 6 phase-handler mixins"
```

---

## Task 6 — Documentation Updates

**Files:**
- Modify: `docs/safety/destructive_action_policy.md`
- Modify: `docs/architecture/extension_guidelines.md`
- Modify: `README.md`

- [ ] **Step 6.1: Add safe subprocess policy to `docs/safety/destructive_action_policy.md`**

Append this section:

```markdown
## Safe Subprocess Policy

All process execution within `qa_ai/` MUST use `qa_ai.utils.safe_subprocess.run_safe()`.

Prohibited patterns:
- `subprocess.run(cmd, shell=True, ...)` — shell injection risk
- `os.system(...)` — shell injection risk
- `subprocess.Popen(cmd, shell=True, ...)` — shell injection risk

`run_safe()` enforces:
1. **No shell expansion** — command is always a list, never a string
2. **Blocked executables** — `sudo`, `su`, `rm -rf`, `dd`, `mkfs` are rejected at call time
3. **Env sanitization** — `LD_PRELOAD`, `LD_LIBRARY_PATH`, `DYLD_INSERT_LIBRARIES` are stripped
4. **cwd validation** — non-existent working directory raises `InvalidCwdError` before any process starts
5. **Timeout enforcement** — processes exceeding the timeout are killed, `SubprocessTimeoutError` raised
6. **Audit logging** — every executed command is logged at INFO level via `qa_ai.utils.safe_subprocess` logger

Exceptions to this policy must be documented inline with a `# safe_subprocess: exempt — <reason>` comment and reviewed in PR.
```

- [ ] **Step 6.2: Add error handling policy to `docs/architecture/extension_guidelines.md`**

Append:

```markdown
## Error Handling Policy

**Do not** write silent exception handlers:
```python
# BAD — hides failures, makes debugging impossible
except Exception:
    pass

except Exception:
    return None
```

**Do** use `log_and_fallback` or explicit logging:
```python
# GOOD — safe fallback with observable failure
from qa_ai.utils.error_handling import log_and_fallback

result = log_and_fallback(
    fn=lambda: risky_operation(),
    default=None,
    logger_name=__name__,
    context="route scan",
)

# GOOD — explicit logging for inline try/except
except Exception as e:
    logger.debug("Route scan failed for %s: %s", file_path, e)
    continue
```

Reserve `logger.warning` for failures that indicate a degraded-but-running state.
Reserve `logger.error` for failures in critical paths that require attention.
Use `logger.debug` for expected safe-fallback paths (tool not installed, optional feature unavailable).
```

- [ ] **Step 6.3: Add environment variables section to `README.md`**

After the `## Quickstart` section, add:

```markdown
## Configuration

All runtime settings can be configured via environment variables. Defaults work for local development.

| Variable | Default | Description |
|----------|---------|-------------|
| `QA_AI_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `QA_AI_APP_BASE_URL` | `http://localhost:3000` | Web app base URL for browser tests |
| `QA_AI_API_BASE_URL` | `http://localhost:8000` | API base URL for API tests |
| `QA_AI_ARTIFACT_DIR` | `artifacts` | Output directory for all artifacts |
| `QA_AI_LLM_TIMEOUT_SECONDS` | `120` | Default LLM call timeout |
| `QA_AI_LLM_LONG_TIMEOUT_SECONDS` | `300` | Timeout for deep-reasoning calls |
| `QA_AI_LLM_HEALTH_CHECK_TIMEOUT` | `2.0` | Ollama availability check timeout |
| `QA_AI_ENABLE_LIVE_RUNTIME` | `false` | Enable live browser execution |
| `QA_AI_ENABLE_MOBILE_RUNTIME` | `false` | Enable mobile device testing |
| `QA_AI_ENABLE_DISTRIBUTED_RUNTIME` | `false` | Enable distributed actor simulation |
| `QA_AI_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
```

- [ ] **Step 6.4: Commit docs**

```bash
git add docs/safety/destructive_action_policy.md \
        docs/architecture/extension_guidelines.md \
        README.md
git commit -m "docs: add safe subprocess policy, error handling policy, env var reference"
```

---

## Task 7 — Final Verification

- [ ] **Step 7.1: Python compile check**

```bash
python -m compileall qa_ai/ -q
```

Expected: 0 errors

- [ ] **Step 7.2: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all existing 813+ tests pass, plus new hardening tests pass

- [ ] **Step 7.3: Check for remaining shell=True**

```bash
grep -rn "shell=True" qa_ai/ | grep -v __pycache__
```

Expected: zero results

- [ ] **Step 7.4: Check for remaining silent exception handlers**

```bash
grep -rn "except Exception:" qa_ai/ | grep -v __pycache__ | grep -v "logger\." | grep -v "log\."
```

Expected: zero results (or only `json_io.py` which re-raises and is intentional)

- [ ] **Step 7.5: Rebuild graphify knowledge graph**

```bash
python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: graph rebuilt, new node/edge counts printed

- [ ] **Step 7.6: Verify WorkflowEngine line count**

```bash
wc -l qa_ai/orchestration/workflow_engine.py
```

Expected: < 750 lines

- [ ] **Step 7.7: Final commit summary**

```bash
git log --oneline -8
```

---

## Quality Score Targets (post-sprint)

| Area | Before | Target | How Achieved |
|------|--------|--------|-------------|
| LLM integration | 8/10 | 9/10 | Env-var timeouts, enhanced circuit breaker metadata, settings-wired health check |
| Error handling | 6/10 | 8.5/10 | `log_and_fallback` helper, all 24 silent handlers replaced |
| Security | 6/10 | 9/10 | `safe_subprocess` with allowlist + env sanitization + audit log |
| Configuration | 5/10 | 9/10 | `Settings` dataclass, 12 env vars, all hardcoded URLs removed |
| Code structure | 6/10 | 8.5/10 | 2717-line god class → 6 focused mixin files + ~650-line core |

---

## Known Intentional Exceptions

### `json_io.py:47`
```python
except Exception:
    if Path(tmp_path).exists():
        Path(tmp_path).unlink()
    raise  # <-- re-raises, not silent
```
This is a cleanup-and-rethrow pattern. The `except` does not swallow — it cleans the temp file then re-raises the original exception. Leave as-is.

### `shell.py:54`
```python
except Exception as e:
    logger.error(f"Command error: {e}")
    return -1, "", str(e)
```
Already logged. Leave as-is.
