"""
validation_target.py - Generic model describing one app to validate.

App-specific targets belong in examples/configs/tests only.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ValidationTarget(BaseModel):
    """Describes one application target for Phase 2 validation."""

    target_id: str
    app_name: str
    app_type: str  # string matches AppType enum values; no enum import to keep generic
    config_path: str  # path to interactive_runtime.yaml for this target

    working_dir: str = "."
    launch_command: str = ""
    expected_platform: Optional[str] = None  # "darwin" | "windows" | "linux" | None (any)

    requires_permissions: bool = True
    expected_capabilities: List[str] = Field(default_factory=list)
    # e.g. ["can_observe_screen", "can_click", "can_screenshot"]

    validation_mode: str = "dry_run"
    # dry_run | live | live_guided | live_guided_ai

    max_actions: int = 20
    allow_real_launch: str = "ask"   # ask | always | never
    allow_external_calls: str = "ask"  # ask | always | never
    allow_database_checks: bool = False
    allow_screenshots: str = "ask"   # ask | always | never

    notes: str = ""
