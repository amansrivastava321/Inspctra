"""
product_interface_schema.py - Artifact schemas for the product interface layer.

Covers the three artifacts produced by the UX layer:
  cli_run_summary.json       - Result of a single CLI command invocation
  webapp_session.json        - Web dashboard session info
  product_interface_summary.json  - Cross-session product usage summary
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CLIRunSummaryArtifact(BaseModel):
    """Artifact produced at the end of every CLI command invocation."""
    artifact_type: str = "cli_run_summary"
    version: str = "1.0"

    run_id: str = ""
    command: str = ""
    subcommand: Optional[str] = None
    target_path: Optional[str] = None
    profile: Optional[str] = None
    status: str = "ok"           # ok | failed | error
    exit_code: int = 0
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    phases_executed: List[str] = Field(default_factory=list)
    artifacts_generated: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    dry_run: bool = False
    cli_version: str = "1.0.0"


class WebAppSessionArtifact(BaseModel):
    """Artifact written when the web dashboard starts."""
    artifact_type: str = "webapp_session"
    version: str = "1.0"

    session_id: str = ""
    host: str = "127.0.0.1"
    port: int = 8765
    artifacts_dir: str = "artifacts"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    read_only: bool = True
    routes_registered: List[str] = Field(default_factory=list)


class ProductInterfaceSummaryArtifact(BaseModel):
    """Cross-session summary of product interface interactions."""
    artifact_type: str = "product_interface_summary"
    version: str = "1.0"

    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_cli_runs: int = 0
    total_dashboard_sessions: int = 0
    commands_used: List[str] = Field(default_factory=list)
    profiles_used: List[str] = Field(default_factory=list)
    last_audit_target: Optional[str] = None
    last_audit_status: Optional[str] = None
    platform_version: str = "1.0.0"
