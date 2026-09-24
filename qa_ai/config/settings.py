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
    # Model routing
    # Default: local_first — cloud disabled by default for privacy.
    # Set QA_AI_MODEL_ROUTING_MODE=specialist_cloud_first to enable cloud.
    model_routing_mode: str = field(
        default_factory=lambda: os.environ.get("QA_AI_MODEL_ROUTING_MODE", "local_first")
    )
    # Cloud models disabled by default — must be explicitly opted in.
    allow_cloud_models: bool = field(
        default_factory=lambda: _bool_env("QA_AI_ALLOW_CLOUD_MODELS", False)
    )
    require_cloud_permission_for_private_code: bool = field(
        default_factory=lambda: _bool_env("QA_AI_REQUIRE_CLOUD_PERMISSION_FOR_PRIVATE_CODE", True)
    )
    private_code_mode: bool = field(
        default_factory=lambda: _bool_env("QA_AI_PRIVATE_CODE_MODE", False)
    )
    redact_cloud_context: bool = field(
        default_factory=lambda: _bool_env("QA_AI_REDACT_CLOUD_CONTEXT", True)
    )
    enable_visual_cloud_backup: bool = field(
        default_factory=lambda: _bool_env("QA_AI_ENABLE_VISUAL_CLOUD_BACKUP", False)
    )
    local_fallback_provider: str = field(
        default_factory=lambda: os.environ.get("QA_AI_LOCAL_FALLBACK_PROVIDER", "ollama")
    )

    # OpenRouter
    openrouter_api_key: str = field(
        default_factory=lambda: os.environ.get("QA_AI_OPENROUTER_API_KEY", "")
    )
    openrouter_base_url: str = field(
        default_factory=lambda: os.environ.get("QA_AI_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    )
    openrouter_timeout_seconds: int = field(
        default_factory=lambda: _int_env("QA_AI_OPENROUTER_TIMEOUT_SECONDS", 45)
    )
    openrouter_long_timeout_seconds: int = field(
        default_factory=lambda: _int_env("QA_AI_OPENROUTER_LONG_TIMEOUT_SECONDS", 180)
    )

    # Corpus integration
    corpus_base_url: str = field(
        default_factory=lambda: os.environ.get("QA_AI_CORPUS_BASE_URL", "http://127.0.0.1:8123")
    )
    corpus_timeout_seconds: float = field(
        default_factory=lambda: _float_env("QA_AI_CORPUS_TIMEOUT_SECONDS", 2.0)
    )
    allow_corpus_runtime_launch: bool = field(
        default_factory=lambda: _bool_env("QA_AI_ALLOW_CORPUS_RUNTIME_LAUNCH", False)
    )
    corpus_runtime_launch_cmd: str = field(
        default_factory=lambda: os.environ.get("QA_AI_CORPUS_RUNTIME_LAUNCH_CMD", "")
    )

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

    # Task router (16 GB Mac local-first defaults)
    task_router_private_mode: bool = field(
        default_factory=lambda: _bool_env("QA_AI_TASK_ROUTER_PRIVATE_MODE", True)
    )
    task_router_persist_prompts: bool = field(
        default_factory=lambda: _bool_env("QA_AI_TASK_ROUTER_PERSIST_PROMPTS", False)
    )
    task_router_max_parallel_calls: int = field(
        default_factory=lambda: _int_env("QA_AI_TASK_ROUTER_MAX_PARALLEL_CALLS", 1)
    )
    task_router_resource_profile: str = field(
        default_factory=lambda: os.environ.get("QA_AI_TASK_ROUTER_RESOURCE_PROFILE", "mac_m4_16gb")
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.environ.get("QA_AI_LOG_LEVEL", "INFO")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
