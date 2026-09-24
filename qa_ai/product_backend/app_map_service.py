"""
app_map_service.py — Generate AppMapDraft from fingerprint discovery data.

RULES (non-negotiable):
- No source code reads.
- No command execution.
- No shell=True, no subprocess, no os.system, no eval.
- No fake routes or fake coverage claims.
- All entries clearly labelled as fingerprint-based inferences.
- map_type = "fingerprint_based_draft" always.
- Capability gaps are explicit, not hidden.
- No hardcoded FlowBook / Videomation / Inspectra-only logic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from qa_ai.product_backend.app_map_models import (
    AppMapDraft,
    CapabilityGap,
    EntryPoint,
    RiskArea,
    RuntimeConnector,
    TestableSurface,
)
from qa_ai.product_backend.discovery_models import DiscoveryResult, DiscoveryStatus


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Connector rules ────────────────────────────────────────────────────────────

_CONNECTOR_MAP: Dict[str, List[RuntimeConnector]] = {
    "web": [
        RuntimeConnector(
            connector_type="web_browser",
            tool="playwright",
            confidence="high",
            note="Web apps tested via browser automation. Playwright required.",
        ),
    ],
    "api": [
        RuntimeConnector(
            connector_type="api_http",
            tool="requests / httpx",
            confidence="high",
            note="API tested via HTTP client. No browser needed.",
        ),
    ],
    "desktop": [
        RuntimeConnector(
            connector_type="desktop_native",
            tool="pywinauto (Windows) / pyobjc (macOS)",
            confidence="medium",
            note="Desktop automation requires OS-level accessibility permissions.",
        ),
    ],
    "mobile": [
        RuntimeConnector(
            connector_type="mobile_appium",
            tool="Appium",
            confidence="medium",
            note="Mobile testing requires Appium server + device/emulator.",
        ),
    ],
    "ai_app": [
        RuntimeConnector(
            connector_type="api_http",
            tool="requests / httpx",
            confidence="high",
            note="AI apps tested via their HTTP API endpoint.",
        ),
    ],
}

# ── Testable surfaces ─────────────────────────────────────────────────────────

def _surfaces_for_type(app_type: str, stack: List[str]) -> List[TestableSurface]:
    surfaces: List[TestableSurface] = []
    if app_type == "web":
        surfaces.append(TestableSurface(
            name="frontend_ui",
            surface_type="ui",
            confidence="medium",
            note="Specific routes and component selectors unknown without runtime inspection.",
        ))
        # If API-related stack detected, suggest backend surface too
        if any(s in ("Python", "Django", "Go", "Ruby", "PHP", "Java/Maven", "Java/Gradle", "Rust")
               for s in stack):
            surfaces.append(TestableSurface(
                name="backend_api",
                surface_type="api",
                confidence="low",
                note="Backend stack detected. API endpoints unknown — check your API docs.",
            ))
    elif app_type == "api":
        surfaces.append(TestableSurface(
            name="api_endpoints",
            surface_type="api",
            confidence="medium",
            note="Specific endpoints unknown without OpenAPI spec or runtime introspection.",
        ))
    elif app_type == "desktop":
        surfaces.append(TestableSurface(
            name="desktop_window",
            surface_type="native",
            confidence="medium",
            note="Window title and element tree unknown without launching the app.",
        ))
        # If Tauri detected, add web surface
        if any("Tauri" in s for s in stack):
            surfaces.append(TestableSurface(
                name="webview_ui",
                surface_type="ui",
                confidence="high",
                note="Tauri detected: WebView frontend testable via Playwright.",
            ))
    elif app_type == "mobile":
        surfaces.append(TestableSurface(
            name="mobile_ui",
            surface_type="mobile",
            confidence="medium",
            note="Screen layout unknown without launching on device/emulator.",
        ))
        if any("Flutter" in s for s in stack):
            surfaces.append(TestableSurface(
                name="flutter_widget_tree",
                surface_type="mobile",
                confidence="high",
                note="Flutter detected. Widget tree testable via flutter_driver or Patrol.",
            ))
    elif app_type == "ai_app":
        surfaces.append(TestableSurface(
            name="inference_api",
            surface_type="api",
            confidence="medium",
            note="AI inference endpoint shape unknown without API docs.",
        ))
    return surfaces


# ── Risk areas ────────────────────────────────────────────────────────────────

def _risk_areas_for_type(app_type: str, stack: List[str]) -> List[RiskArea]:
    risks: List[RiskArea] = []

    if app_type == "web":
        risks += [
            RiskArea(label="XSS / output encoding", risk_level="critical",
                     description="User input rendered in DOM must be escaped.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Authentication gates", risk_level="high",
                     description="Protected routes must reject unauthenticated access.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Form validation", risk_level="medium",
                     description="Required field validation, format checks.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="API error exposure", risk_level="medium",
                     description="Backend errors must not leak stack traces to browser.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Double-submit / idempotency", risk_level="medium",
                     description="Forms must prevent duplicate submissions.",
                     detection_basis="app_type_heuristic"),
        ]
    elif app_type == "api":
        risks += [
            RiskArea(label="Authentication (401/403)", risk_level="critical",
                     description="Protected endpoints must reject unauthenticated requests.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Input validation (422)", risk_level="high",
                     description="Invalid inputs must return 422 not 500.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="SQL / NoSQL injection", risk_level="critical",
                     description="Input must not reach DB queries without sanitization.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Rate limiting", risk_level="medium",
                     description="Endpoints without rate limits risk abuse.",
                     detection_basis="app_type_heuristic"),
        ]
    elif app_type == "desktop":
        risks += [
            RiskArea(label="OS permission gates", risk_level="high",
                     description="App must request permissions correctly and handle denial.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Crash on launch", risk_level="high",
                     description="Verify app launches cleanly on target OS version.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Keyboard accessibility", risk_level="medium",
                     description="All interactive elements reachable without mouse.",
                     detection_basis="app_type_heuristic"),
        ]
        if any("Tauri" in s for s in stack):
            risks.append(RiskArea(
                label="Tauri shell command boundary", risk_level="critical",
                description="Shell commands from frontend must be allowlisted and validated.",
                detection_basis="stack_signal",
            ))
    elif app_type == "mobile":
        risks += [
            RiskArea(label="Permission denial handling", risk_level="high",
                     description="App must degrade gracefully when permission denied.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Offline / network loss", risk_level="medium",
                     description="App must not crash when network unavailable.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Back-stack corruption", risk_level="medium",
                     description="Back navigation must not corrupt screen stack.",
                     detection_basis="app_type_heuristic"),
        ]
        if any("Flutter" in s for s in stack):
            risks.append(RiskArea(
                label="Flutter platform channel errors", risk_level="medium",
                description="Platform channel calls must handle errors from native side.",
                detection_basis="stack_signal",
            ))
        if any("Android" in s for s in stack):
            risks.append(RiskArea(
                label="Android lifecycle", risk_level="medium",
                description="onPause/onResume/onDestroy must preserve state correctly.",
                detection_basis="stack_signal",
            ))
    elif app_type == "ai_app":
        risks += [
            RiskArea(label="Prompt injection", risk_level="critical",
                     description="User input must not override system prompt boundaries.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Output safety", risk_level="critical",
                     description="Harmful content must not pass through to users.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Schema conformance", risk_level="high",
                     description="Structured output must match declared schema.",
                     detection_basis="app_type_heuristic"),
            RiskArea(label="Timeout handling", risk_level="medium",
                     description="Model timeout must return error, not hang.",
                     detection_basis="app_type_heuristic"),
        ]
    return risks


# ── Capability gaps ───────────────────────────────────────────────────────────

def _capability_gaps(app_type: str, discovery: Optional[DiscoveryResult]) -> List[CapabilityGap]:
    gaps: List[CapabilityGap] = []
    source_type = discovery.source_type.value if discovery else None

    gaps.append(CapabilityGap(
        id="cap_gap_routes",
        title="Specific routes / screens unknown",
        description=(
            "Inspectra cannot enumerate actual routes or screens without launching the app. "
            "This map is based on file existence only."
        ),
        resolution="Run the app and use Runtime Doctor to scan live surfaces.",
        severity="medium",
    ))

    if app_type in ("web", "api") and not (discovery and discovery.suggested_base_url):
        gaps.append(CapabilityGap(
            id="cap_gap_base_url",
            title="No live URL known",
            description="Base URL not detected. Cannot perform health checks without it.",
            resolution="Add base_url in App Detail → Edit, then run Runtime Doctor.",
            severity="medium",
        ))

    if source_type == "github_url":
        gaps.append(CapabilityGap(
            id="cap_gap_github",
            title="GitHub source not scanned",
            description="Inspectra does not clone repositories. No file-level fingerprints available.",
            resolution="Clone the repo locally and re-add the app with 'Local folder' source.",
            severity="high",
        ))

    if source_type is None or source_type == "manual":
        gaps.append(CapabilityGap(
            id="cap_gap_no_discovery",
            title="No source scanned — map is generic",
            description=(
                "No source path or URL was scanned. This map is based on app_type alone. "
                "Stack detection, launch commands, and framework-specific risks are unavailable."
            ),
            resolution="Re-add the app with a local folder path or URL to enable fingerprinting.",
            severity="high",
        ))

    if app_type == "desktop":
        gaps.append(CapabilityGap(
            id="cap_gap_window_title",
            title="Window title unknown",
            description="Cannot locate app window without launching it.",
            resolution="Add window_title in App Detail. Run app and observe title bar.",
            severity="medium",
        ))

    if app_type == "mobile":
        gaps.append(CapabilityGap(
            id="cap_gap_device",
            title="Device / emulator not connected",
            description="Mobile testing requires a connected device or running emulator.",
            resolution="Connect device or start emulator, then run Runtime Doctor.",
            severity="high",
        ))

    return gaps


# ── Overall confidence ────────────────────────────────────────────────────────

def _overall_confidence(discovery: Optional[DiscoveryResult], stack: List[str]) -> str:
    if not discovery or discovery.status != DiscoveryStatus.complete:
        return "low"
    if len(stack) >= 3:
        return "medium"
    if len(stack) >= 1:
        return "low"
    return "low"


# ── Main generator ────────────────────────────────────────────────────────────

def generate_app_map(
    app_id: str,
    app_name: str,
    app_type: str,
    discovery: Optional[DiscoveryResult] = None,
    discovery_id: Optional[str] = None,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    source_type: Optional[str] = None,
    launch_command: Optional[str] = None,
) -> AppMapDraft:
    """
    Generate an AppMapDraft from available fingerprint data.

    ALWAYS returns map_type='fingerprint_based_draft'.
    Never claims deep code analysis.
    Capability gaps are always included.
    """
    now = _now_iso()
    app_map_id = _new_id()

    # Resolve stack from discovery
    stack: List[str] = []
    if discovery and discovery.detected_stack:
        stack = [s.value for s in discovery.detected_stack]

    # Resolve source info
    _source_type = source_type
    _source_path = source_path
    _source_url = source_url
    if discovery:
        _source_type = _source_type or (discovery.source_type.value if discovery.source_type else None)
        _source_path = _source_path or discovery.local_path
        _source_url = _source_url or discovery.url
        if not discovery_id:
            discovery_id = discovery.id

    # Build entry points
    entry_points: List[EntryPoint] = []
    if launch_command:
        entry_points.append(EntryPoint(
            label=f"Launch: {launch_command}",
            command=launch_command,
            confidence="high",
            source="user_confirmed",
        ))
    elif discovery and discovery.suggested_launch_command:
        entry_points.append(EntryPoint(
            label=f"Suggested: {discovery.suggested_launch_command.command}",
            command=discovery.suggested_launch_command.command,
            confidence=discovery.suggested_launch_command.confidence.value
            if hasattr(discovery.suggested_launch_command.confidence, 'value')
            else discovery.suggested_launch_command.confidence,
            source=discovery.suggested_launch_command.source,
        ))
    if discovery and discovery.suggested_base_url:
        entry_points.append(EntryPoint(
            label=f"URL: {discovery.suggested_base_url.value}",
            url=discovery.suggested_base_url.value,
            confidence="high",
            source="user_provided",
        ))
    elif source_url:
        entry_points.append(EntryPoint(
            label=f"URL: {source_url}",
            url=source_url,
            confidence="medium",
            source="source_scan",
        ))

    launch_commands: List[str] = []
    if launch_command:
        launch_commands.append(launch_command)
    elif discovery and discovery.suggested_launch_command:
        launch_commands.append(discovery.suggested_launch_command.command)

    # Build the map
    map_draft = AppMapDraft(
        app_map_id=app_map_id,
        app_id=app_id,
        discovery_id=discovery_id,
        app_name=app_name,
        app_type=app_type,
        map_type="fingerprint_based_draft",
        confidence=_overall_confidence(discovery, stack),
        detected_stack=stack,
        source_type=_source_type,
        source_path=_source_path,
        source_url=_source_url,
        entry_points=entry_points,
        launch_commands=launch_commands,
        runtime_connectors=_CONNECTOR_MAP.get(app_type, []),
        testable_surfaces=_surfaces_for_type(app_type, stack),
        risk_areas=_risk_areas_for_type(app_type, stack),
        capability_gaps=_capability_gaps(app_type, discovery),
        created_at=now,
        updated_at=now,
    )
    return map_draft


def generate_app_map_from_app_record(
    app: Dict[str, Any],
    discovery: Optional[DiscoveryResult] = None,
) -> AppMapDraft:
    """Convenience wrapper — takes a storage row dict for the app."""
    return generate_app_map(
        app_id=app["id"],
        app_name=app["name"],
        app_type=app.get("app_type", "web"),
        discovery=discovery,
        discovery_id=app.get("discovery_id"),
        source_path=app.get("source_path"),
        source_url=app.get("source_url"),
        source_type=app.get("source_type"),
        launch_command=app.get("launch_command"),
    )
