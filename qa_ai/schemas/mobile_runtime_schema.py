"""
mobile_runtime_schema.py - Strict contracts for mobile runtime artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class DeviceRegistryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "device_registry"

    tooling: Dict[str, Any] = Field(default_factory=dict)
    inventory: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AndroidEmulatorReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "android_emulator_report"

    dry_run: bool = True
    emulators: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class IosSimulatorReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ios_simulator_report"

    dry_run: bool = True
    simulators: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class FlutterExecutionPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "flutter_execution_plan"

    app_path: str = ""
    is_flutter_project: bool = False
    dry_run: bool = True
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    plans: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AppiumPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "appium_plan"

    available: bool = False
    dry_run: bool = True
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    plans: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class MaestroPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "maestro_plan"

    available: bool = False
    dry_run: bool = True
    flows: List[Dict[str, Any]] = Field(default_factory=list)
    plans: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class DeviceSessionReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "device_session_report"

    distributed: bool = False
    shared_state: Dict[str, Any] = Field(default_factory=dict)
    sessions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class MobileNetworkReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "mobile_network_report"

    simulation_mode: bool = True
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_actions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class MobileRuntimeMonitorReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "mobile_runtime_monitor_report"

    devices: List[Dict[str, Any]] = Field(default_factory=list)
    health_signals: List[Dict[str, Any]] = Field(default_factory=list)
    crashes_detected: int = 0
    anr_signals: int = 0
    memory_warnings: int = 0
    reconnect_instability: int = 0
    summary: Dict[str, Any] = Field(default_factory=dict)


class MobileLogsIndexArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "mobile_logs_index"

    dry_run: bool = True
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class MobileEvidenceGraphArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "mobile_evidence_graph"

    graph: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class MobileRuntimeReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "mobile_runtime_report"

    app_path: str = ""
    dry_run: bool = True
    distributed: bool = False
    phases: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
