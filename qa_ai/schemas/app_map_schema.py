"""
app_map_schema.py - Pydantic models for the application knowledge graph.
Defines the contract for app_map.json produced by the Discovery Agent.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class StackCapabilities(BaseModel):
    has_auth: bool = False
    has_api: bool = False
    has_database: bool = False
    has_payments: bool = False
    has_file_upload: bool = False
    has_real_time: bool = False
    has_i18n: bool = False
    has_dark_mode: bool = False
    has_offline_support: bool = False
    has_e2e_tests: bool = False
    has_unit_tests: bool = False


class StackInfo(BaseModel):
    framework: str = "unknown"
    language: str = "unknown"
    app_type: str = "unknown"
    framework_version: Optional[str] = None
    language_version: Optional[str] = None
    state_management: Optional[str] = None
    router_library: Optional[str] = None
    http_client: Optional[str] = None
    database: Optional[str] = None
    auth_provider: Optional[str] = None
    css_framework: Optional[str] = None
    bundler: Optional[str] = None
    test_framework: Optional[str] = None
    package_manager: Optional[str] = None
    build_tool: Optional[str] = None
    capabilities: StackCapabilities = Field(default_factory=StackCapabilities)
    confidence: float = 0.0


class APIRisk(BaseModel):
    risk_level: str = "low"
    mutates_data: bool = False
    financial_operation: bool = False
    admin_operation: bool = False
    auth_operation: bool = False
    rate_limited: Optional[bool] = None


class APIEndpoint(BaseModel):
    method: Optional[str] = None
    path: str = ""
    full_url: Optional[str] = None
    base_url: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    type: str = "rest"
    auth_required: Optional[bool] = None
    auth_type: Optional[str] = None
    params: List[str] = Field(default_factory=list)
    query: List[str] = Field(default_factory=list)
    request_body: Optional[Any] = None
    response_type: Optional[str] = None
    headers: List[str] = Field(default_factory=list)
    error_handling: bool = False
    rate_limited: bool = False
    deprecated: bool = False
    called_by: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    risk: Optional[APIRisk] = None


class Screen(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    route: Optional[str] = None
    auth_required: Optional[bool] = None
    source: Optional[str] = None
    screen_type: Optional[str] = None
    framework: Optional[str] = None
    confidence: float = 0.0


class CriticalFlow(BaseModel):
    name: str = ""
    priority: str = "medium"
    type: str = ""
    steps: List[str] = Field(default_factory=list)
    expected_outcome: str = ""


class SecuritySurfaces(BaseModel):
    public_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    payment_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    admin_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    auth_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    file_upload_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    admin_routes: List[Dict[str, Any]] = Field(default_factory=list)
    auth_routes: List[Dict[str, Any]] = Field(default_factory=list)
    webviews: List[Any] = Field(default_factory=list)
    deep_links: List[Any] = Field(default_factory=list)
    sensitive_permissions: List[Any] = Field(default_factory=list)
    detected_capabilities: Dict[str, bool] = Field(default_factory=dict)


class Testability(BaseModel):
    has_unit_tests: bool = False
    has_e2e_tests: bool = False
    test_framework: Optional[str] = None
    has_mock_server: bool = False
    has_seed_data: bool = False
    has_test_ids: bool = False
    supports_offline_testing: bool = False
    recommended_test_strategy: Dict[str, bool] = Field(default_factory=dict)


class AppMapMetadata(BaseModel):
    app_name: str = ""
    app_path: str = ""
    discovered_at: str = ""
    discovery_version: str = ""
    generated_by: str = "DiscoveryAgent"


class AppMap(BaseModel):
    """Complete application knowledge graph produced by the Discovery Agent."""

    metadata: AppMapMetadata = Field(default_factory=AppMapMetadata)
    stack: StackInfo = Field(default_factory=StackInfo)
    entry_points: Dict[str, Optional[str]] = Field(default_factory=dict)
    screens: List[Screen] = Field(default_factory=list)
    navigation_graph: Dict[str, Any] = Field(default_factory=dict)
    screen_metadata: Dict[str, Any] = Field(default_factory=dict)
    api_endpoints: List[APIEndpoint] = Field(default_factory=list)
    api_risk_summary: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    critical_flows: List[CriticalFlow] = Field(default_factory=list)
    dependency_graph: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    state_map: Dict[str, Any] = Field(default_factory=dict)
    security_surfaces: SecuritySurfaces = Field(default_factory=SecuritySurfaces)
    permissions: Dict[str, List[Any]] = Field(default_factory=dict)
    external_services: Dict[str, List[Any]] = Field(default_factory=dict)
    feature_flags: List[Any] = Field(default_factory=list)
    environment_config: Dict[str, Any] = Field(default_factory=dict)
    testability: Testability = Field(default_factory=Testability)
    code_health: Dict[str, List[Any]] = Field(default_factory=dict)
    quality_risks: Dict[str, List[Any]] = Field(default_factory=dict)
    routes_summary: Dict[str, int] = Field(default_factory=dict)
    api_summary: Dict[str, Any] = Field(default_factory=dict)
    agent_hints: Dict[str, Any] = Field(default_factory=dict)
    evidence_index: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    raw_dependencies: List[str] = Field(default_factory=list)
    detected_files: List[str] = Field(default_factory=list)
