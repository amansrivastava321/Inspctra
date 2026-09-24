"""
validation_pack.py - ValidationPack: container of ValidationTarget entries.

Load from YAML. No hardcoded app logic.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from qa_ai.interactive_runtime.validation.validation_target import ValidationTarget

logger = logging.getLogger(__name__)


class ValidationPack(BaseModel):
    """A named collection of ValidationTarget entries for Phase 2 validation."""

    pack_name: str
    description: str = ""
    targets: List[ValidationTarget] = Field(default_factory=list)

    def get_target(self, target_id: str) -> Optional[ValidationTarget]:
        for t in self.targets:
            if t.target_id == target_id:
                return t
        return None

    def filter_by_platform(self, platform: str) -> List[ValidationTarget]:
        """Return targets whose expected_platform matches or is None."""
        return [
            t for t in self.targets
            if t.expected_platform is None or t.expected_platform == platform
        ]


def load_pack(path: str) -> ValidationPack:
    """Load a ValidationPack from a YAML file."""
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        raise ImportError("PyYAML required: pip install pyyaml")

    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Validation pack not found: {resolved}")

    with open(resolved, "r", encoding="utf-8") as fh:
        raw: Dict[str, Any] = yaml.safe_load(fh) or {}

    try:
        pack = ValidationPack(**raw)
    except Exception as exc:
        raise ValueError(f"Invalid validation pack at {resolved}: {exc}") from exc

    logger.info("Loaded validation pack '%s' with %d targets", pack.pack_name, len(pack.targets))
    return pack
