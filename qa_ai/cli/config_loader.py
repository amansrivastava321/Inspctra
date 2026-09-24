"""
config_loader.py - Safe YAML config loading for CLI profiles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import logging

import yaml

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load YAML config with safe fallback and malformed-file protection."""

    def __init__(self, default_config_path: Path):
        self.default_config_path = default_config_path

    def load_yaml(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            logger.warning("Config path does not exist: %s", path)
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Malformed config at %s: %s", path, exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    def load(self, path: Path | None = None) -> Dict[str, Any]:
        if path is not None:
            loaded = self.load_yaml(path)
            if loaded:
                return loaded
        return self.load_yaml(self.default_config_path)
