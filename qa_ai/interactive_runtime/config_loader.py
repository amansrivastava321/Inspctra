"""
config_loader.py - Load and validate interactive_runtime.yaml configs.

Follows the existing project pattern (yaml files in qa_ai/config/).
Supports loading from an explicit path or by searching standard locations.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from qa_ai.interactive_runtime.schemas import InteractiveRuntimeConfig

logger = logging.getLogger(__name__)

_SEARCH_PATHS = [
    "interactive_runtime.yaml",
    "interactive_runtime.yml",
    ".qa_ai/interactive_runtime.yaml",
    "config/interactive_runtime.yaml",
]


def load_config(path: Optional[str] = None) -> InteractiveRuntimeConfig:
    """
    Load InteractiveRuntimeConfig from a YAML file.

    Args:
        path: Explicit path to a YAML file. If None, searches standard locations.

    Returns:
        Parsed and validated config.

    Raises:
        FileNotFoundError: if no config file is found.
        ValueError: if the YAML is invalid or fails validation.
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        raise ImportError("PyYAML is required for config loading. Install it with: pip install pyyaml")

    resolved = _resolve_path(path)
    logger.info("Loading interactive runtime config from: %s", resolved)

    with open(resolved, "r", encoding="utf-8") as fh:
        raw: Dict[str, Any] = yaml.safe_load(fh) or {}

    try:
        config = InteractiveRuntimeConfig(**raw)
    except Exception as exc:
        raise ValueError(f"Invalid interactive_runtime config at {resolved}: {exc}") from exc

    logger.debug("Config loaded: app_name=%s app_type=%s", config.app_name, config.app_type)
    return config


def _resolve_path(path: Optional[str]) -> Path:
    if path:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        return p

    for candidate in _SEARCH_PATHS:
        p = Path(candidate)
        if p.exists():
            return p.resolve()

    raise FileNotFoundError(
        "No interactive_runtime.yaml found. "
        "Create one or pass --config <path>. "
        f"Searched: {_SEARCH_PATHS}"
    )


def validate_config(config: InteractiveRuntimeConfig) -> Dict[str, Any]:
    """
    Run basic sanity checks on the config without launching anything.

    Returns a dict with 'valid', 'errors', 'warnings' keys.
    """
    errors: list = []
    warnings: list = []

    if not config.app_name:
        errors.append("app_name is required")
    if not config.launch_command:
        errors.append("launch_command is required")
    if config.max_actions <= 0:
        errors.append("max_actions must be > 0")
    if config.max_duration_seconds <= 0:
        errors.append("max_duration_seconds must be > 0")

    if config.database.enabled and config.database.type == "sqlite":
        if not config.database.path:
            warnings.append("database.path not set; SQLite verification may fail")

    if config.database.enabled and config.database.type == "supabase":
        if not config.database.url_env:
            warnings.append("database.url_env not set; Supabase verification will be skipped")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "app_name": config.app_name,
        "app_type": config.app_type,
        "launch_command": config.launch_command,
    }
