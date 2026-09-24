"""
discovery_models.py — Pydantic models for app source discovery.

All scanning is explicit, user-initiated, and privacy-safe:
- Only file existence checked (except package.json name/scripts field)
- No secrets read
- No shell execution
- Confidence label on every detected field
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    local_folder = "local_folder"
    web_url = "web_url"
    api_base_url = "api_base_url"
    github_url = "github_url"
    manual = "manual"


class DiscoveryStatus(str, Enum):
    pending = "pending"
    scanning = "scanning"
    complete = "complete"
    failed = "failed"
    unsupported = "unsupported"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


# ── Input ─────────────────────────────────────────────────────────────────────

class AppSourceInput(BaseModel):
    project_id: str
    source_type: SourceType
    # Exactly one of these should be set
    local_path: Optional[str] = None   # absolute local folder path
    url: Optional[str] = None          # web / api / github URL
    # User must explicitly grant permission before any local folder scan.
    # Backend rejects local_folder scan if this is False.
    permission_to_scan: bool = False


# ── Fingerprint (internal scan result) ───────────────────────────────────────

class AppFingerprint(BaseModel):
    """Raw signal detected during scanning — files found, patterns matched."""
    files_scanned: int = 0
    depth_reached: int = 0
    detected_files: List[str] = Field(default_factory=list)   # relative paths
    package_name: Optional[str] = None       # from package.json if present
    package_scripts: dict = Field(default_factory=dict)  # scripts from package.json
    has_node_modules: bool = False
    has_git: bool = False
    truncated: bool = False   # True if hit file/depth limit


# ── Detected values ───────────────────────────────────────────────────────────

class DetectedValue(BaseModel):
    value: str
    confidence: Confidence
    source: str   # e.g. "package.json", "requirements.txt", "file pattern"


class DetectedLaunchCommand(BaseModel):
    command: str
    confidence: Confidence
    source: str


class AuditStrategySuggestion(BaseModel):
    strategy: str          # e.g. "web-browser", "api-contract", "mobile-ui"
    confidence: Confidence
    reason: str


# ── Discovery Result ──────────────────────────────────────────────────────────

class DiscoveryResult(BaseModel):
    id: str
    project_id: str
    source_type: SourceType
    local_path: Optional[str] = None
    url: Optional[str] = None
    status: DiscoveryStatus = DiscoveryStatus.pending

    # Detected suggestions (all editable by user before app creation)
    suggested_name: Optional[DetectedValue] = None
    suggested_app_type: Optional[DetectedValue] = None     # web / api / mobile / desktop
    suggested_platform: Optional[DetectedValue] = None
    suggested_launch_command: Optional[DetectedLaunchCommand] = None
    suggested_base_url: Optional[DetectedValue] = None
    detected_stack: List[DetectedValue] = Field(default_factory=list)
    audit_strategy: Optional[AuditStrategySuggestion] = None

    fingerprint: Optional[AppFingerprint] = None
    error_message: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


# ── Create-from-discovery request ─────────────────────────────────────────────

class AppCreateFromDiscoveryRequest(BaseModel):
    """User-confirmed values after reviewing detection result."""
    discovery_id: str
    name: str
    app_type: str
    platform: Optional[str] = None
    base_url: Optional[str] = None
    launch_command: Optional[str] = None
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    working_directory: Optional[str] = None
