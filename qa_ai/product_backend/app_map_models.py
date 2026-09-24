"""
app_map_models.py — Pydantic models for AppMapDraft.

An AppMapDraft is built from fingerprint data only.
- No source code read.
- No commands executed.
- Every field is honest about confidence and data source.
- map_type = "fingerprint_based_draft" always — never claim deep code mapping.

Capability gaps are explicit (not hidden).
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class EntryPoint(BaseModel):
    """A suspected app entry point — not confirmed without runtime."""
    label: str                  # e.g. "npm run dev", "python manage.py runserver"
    command: Optional[str] = None
    url: Optional[str] = None   # if web/api URL is known
    confidence: str = "low"     # high/medium/low
    source: str = ""            # "launch_command", "package.json", "user_provided"


class RuntimeConnector(BaseModel):
    """Which Inspectra connector can test this app."""
    connector_type: str         # "web_browser", "api_http", "desktop_native", "mobile_appium"
    tool: str                   # "playwright", "requests", "pywinauto", "appium"
    confidence: str = "medium"
    note: str = ""


class TestableSurface(BaseModel):
    """A surface that can be tested — inferred from stack, not confirmed."""
    name: str                   # e.g. "frontend_ui", "api_endpoints", "desktop_window"
    surface_type: str           # "ui", "api", "native", "mobile"
    confidence: str = "medium"
    note: str = ""              # honest caveats


class RiskArea(BaseModel):
    """A risk area inferred from stack / app type."""
    label: str
    risk_level: str = "medium"  # critical/high/medium/low
    description: str = ""
    detection_basis: str = ""   # "stack_signal", "app_type_heuristic", "user_provided"


class CapabilityGap(BaseModel):
    """Honest gap — what Inspectra cannot determine from fingerprint alone."""
    id: str
    title: str
    description: str
    resolution: str = ""        # how user can unblock this
    severity: str = "medium"    # high/medium/low


class AppMapDraft(BaseModel):
    """
    Fingerprint-based app map.

    IMPORTANT: map_type is always 'fingerprint_based_draft'.
    Do not rename or claim deep code analysis.
    All fields are inferred from file existence + user-provided info only.
    """
    app_map_id: str
    app_id: str
    discovery_id: Optional[str] = None
    app_name: str
    app_type: str
    map_type: str = "fingerprint_based_draft"   # NEVER change to "deep_analysis"
    confidence: str = "low"                      # honest overall confidence
    detected_stack: List[str] = Field(default_factory=list)
    source_type: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    entry_points: List[EntryPoint] = Field(default_factory=list)
    launch_commands: List[str] = Field(default_factory=list)
    runtime_connectors: List[RuntimeConnector] = Field(default_factory=list)
    testable_surfaces: List[TestableSurface] = Field(default_factory=list)
    risk_areas: List[RiskArea] = Field(default_factory=list)
    capability_gaps: List[CapabilityGap] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
