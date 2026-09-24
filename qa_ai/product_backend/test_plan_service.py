"""
test_plan_service.py - Generic test plan generator for Inspectra.

Generates template-based test cases from app_type.
No app-specific hardcoding (no FlowBook, no Videomation, no product names).
No AI calls — deterministic, instant, offline-capable.

All generated cases are labelled generated_from='generic_app_type_template'.
Users must review and refine after connecting an app.

Security:
- No secrets stored.
- No external calls.
- Destructive tests not enabled by default (safety_level='destructive', enabled=False).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ── Template definitions ──────────────────────────────────────────────────────
#
# Each entry: dict matching TestCase model fields.
# 'enabled' defaults True except destructive/external_cost cases → False by default.

def _web_cases(plan_id: str, pack_id: str) -> List[Dict[str, Any]]:
    now = _now_iso()
    return [
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="smoke",
             title="App loads without error", test_type="positive", priority="P0",
             risk_level="high", steps=["navigate", "assert_title_contains", "screenshot"],
             expected_result="Page loads, no 5xx error, title visible",
             expected_evidence=["screenshot"], pass_criteria="HTTP 200, DOM rendered",
             fail_criteria="Blank page, error overlay, or timeout",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["smoke"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="navigation",
             title="Primary navigation links resolve", test_type="positive", priority="P1",
             risk_level="medium", steps=["Click each top-level nav item", "Verify route changes"],
             expected_result="Each link navigates to correct page without 404",
             expected_evidence=["screenshot"],
             pass_criteria="URL changes, target page renders",
             fail_criteria="404 error or blank panel",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["navigation"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="forms",
             title="Form rejects missing required fields", test_type="negative", priority="P1",
             risk_level="medium", steps=["Leave required field empty", "Submit form"],
             expected_result="Validation error shown inline, form not submitted",
             expected_evidence=["screenshot"],
             pass_criteria="Error message visible, no network request sent",
             fail_criteria="Form submits with empty required field",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["forms", "validation"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="forms",
             title="Form rejects invalid input format", test_type="negative", priority="P1",
             risk_level="medium",
             steps=["Enter invalid email/phone/date in appropriate field", "Submit form"],
             expected_result="Format validation error shown",
             expected_evidence=["screenshot"],
             pass_criteria="Inline validation message appears",
             fail_criteria="Form accepts invalid format without error",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["forms", "validation"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="edge_cases",
             title="Double-submit prevention", test_type="edge_case", priority="P1",
             risk_level="high", steps=["Fill valid form", "Click submit twice quickly"],
             expected_result="Only one submission processed, no duplicate created",
             expected_evidence=["screenshot", "log"],
             pass_criteria="Submit button disabled after first click OR backend deduplicates",
             fail_criteria="Duplicate records created",
             automation_status="needs_selector", safety_level="caution", enabled=True,
             tags=["edge_case", "idempotency"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="error_handling",
             title="Backend error shows user-friendly message", test_type="negative", priority="P1",
             risk_level="medium",
             steps=["Trigger a 500 error (mock or intercept)", "Observe UI response"],
             expected_result="Error message shown, no raw stack trace exposed",
             expected_evidence=["screenshot"],
             pass_criteria="User-facing error message, no internal path/code leaked",
             fail_criteria="Raw exception or stack trace visible to user",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["error_handling", "security"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="security",
             title="Unauthenticated access returns 401/redirect", test_type="security",
             priority="P0", risk_level="critical",
             steps=["Access protected route without auth token", "Observe response"],
             expected_result="Redirect to login or 401 response",
             expected_evidence=["screenshot"],
             pass_criteria="Protected content not visible without auth",
             fail_criteria="Protected page accessible without authentication",
             automation_status="needs_credentials", safety_level="safe", enabled=True,
             tags=["security", "auth"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="security",
             title="XSS input sanitized in output", test_type="security", priority="P1",
             risk_level="critical",
             steps=["Enter <script>alert(1)</script> in a text field", "Save and view"],
             expected_result="Script tag rendered as text, not executed",
             expected_evidence=["screenshot"],
             pass_criteria="No alert dialog, content escaped in DOM",
             fail_criteria="Script executes or alert appears",
             automation_status="needs_selector", safety_level="caution", enabled=True,
             tags=["security", "xss"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="edge_cases",
             title="Very long input handled gracefully", test_type="edge_case", priority="P2",
             risk_level="low",
             steps=["Enter 10000-character string in a text field", "Submit form"],
             expected_result="Graceful truncation or validation error, no crash",
             expected_evidence=["screenshot"],
             pass_criteria="App remains responsive, max-length enforced",
             fail_criteria="Page crash, DB error, or silent truncation without feedback",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["edge_case", "input"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="destructive",
             title="Delete action requires confirmation", test_type="negative", priority="P1",
             risk_level="high",
             steps=["Trigger delete action", "Dismiss confirmation if shown"],
             expected_result="Delete cancelled if user dismisses confirmation",
             expected_evidence=["screenshot"],
             pass_criteria="Confirmation dialog shown, item not deleted on dismiss",
             fail_criteria="Item deleted without confirmation",
             automation_status="needs_selector",
             safety_level="destructive",
             requires_permission=True, enabled=False,  # OFF by default — user must enable
             tags=["destructive", "data_integrity"], created_at=now, updated_at=now),
    ]


def _api_cases(plan_id: str, pack_id: str) -> List[Dict[str, Any]]:
    now = _now_iso()
    return [
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="health",
             title="Health endpoint returns 200", test_type="positive", priority="P0",
             risk_level="high", steps=["GET /health or /api/health"],
             expected_result="HTTP 200, JSON status ok",
             expected_evidence=["log"], pass_criteria="status_code == 200",
             fail_criteria="Non-200 response or timeout",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["smoke", "health"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="auth",
             title="Protected endpoint returns 401 without auth", test_type="security",
             priority="P0", risk_level="critical",
             steps=["GET protected endpoint with no Authorization header"],
             expected_result="HTTP 401 or 403",
             expected_evidence=["log"],
             pass_criteria="401/403 returned, no data leaked",
             fail_criteria="200 returned or internal error exposed",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["security", "auth"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="validation",
             title="Missing required field returns 422", test_type="negative", priority="P1",
             risk_level="medium",
             steps=["POST to create endpoint with required field omitted"],
             expected_result="HTTP 422 with field-level error details",
             expected_evidence=["log"],
             pass_criteria="422 returned, error body identifies missing field",
             fail_criteria="500 error or ambiguous response",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["validation", "api_contract"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="validation",
             title="Invalid JSON body returns 400/422", test_type="negative", priority="P1",
             risk_level="medium",
             steps=["POST with malformed JSON body"],
             expected_result="HTTP 400 or 422, not 500",
             expected_evidence=["log"],
             pass_criteria="Appropriate client error, not server error",
             fail_criteria="500 error or app crash",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["validation"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="edge_cases",
             title="Idempotent PUT does not create duplicate", test_type="edge_case",
             priority="P1", risk_level="high",
             steps=["PUT same payload twice to same resource"],
             expected_result="Second PUT returns same result, no duplicate created",
             expected_evidence=["log"],
             pass_criteria="Resource state identical after both calls",
             fail_criteria="Duplicate resource created",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["edge_case", "idempotency"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="destructive",
             title="DELETE removes resource and returns 204", test_type="positive",
             priority="P1", risk_level="high",
             steps=["Create resource", "DELETE it", "GET same resource"],
             expected_result="DELETE returns 204, subsequent GET returns 404",
             expected_evidence=["log"],
             pass_criteria="204 on delete, 404 on subsequent get",
             fail_criteria="Resource still accessible after delete",
             automation_status="ready",
             safety_level="destructive",
             requires_permission=True, enabled=False,  # OFF by default
             tags=["destructive", "api_contract"], created_at=now, updated_at=now),
    ]


def _desktop_cases(plan_id: str, pack_id: str) -> List[Dict[str, Any]]:
    now = _now_iso()
    return [
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="smoke",
             title="App launches and main window is detected", test_type="positive",
             priority="P0", risk_level="high",
             steps=["Launch app", "Wait for window to appear"],
             expected_result="Window detected with expected title",
             expected_evidence=["screenshot"],
             pass_criteria="Window handle found within 10s",
             fail_criteria="No window detected or crash on launch",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["smoke"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="accessibility",
             title="Accessibility permissions granted for automation", test_type="permission",
             priority="P0", risk_level="high",
             steps=["Check OS accessibility permission for automation tool"],
             expected_result="Permission granted",
             expected_evidence=["log"],
             pass_criteria="Accessibility API accessible, no permission denial",
             fail_criteria="Permission denied, automation blocked",
             automation_status="needs_permission", safety_level="safe",
             requires_permission=True, enabled=True,
             tags=["accessibility", "permission"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="interaction",
             title="Primary action button is clickable", test_type="positive", priority="P1",
             risk_level="medium", steps=["Locate primary CTA button", "Click it"],
             expected_result="Button responds, expected action triggered",
             expected_evidence=["screenshot"],
             pass_criteria="Button state changes after click",
             fail_criteria="No response or error dialog",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["interaction"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="edge_cases",
             title="Menu keyboard navigation works", test_type="accessibility", priority="P2",
             risk_level="low", steps=["Open app menu with keyboard", "Navigate with arrow keys"],
             expected_result="Each menu item reachable via keyboard",
             expected_evidence=["screenshot"],
             pass_criteria="All menu items focusable and activatable by keyboard",
             fail_criteria="Items not reachable without mouse",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["accessibility", "keyboard"], created_at=now, updated_at=now),
    ]


def _mobile_cases(plan_id: str, pack_id: str) -> List[Dict[str, Any]]:
    now = _now_iso()
    return [
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="smoke",
             title="App launches on device/emulator", test_type="positive", priority="P0",
             risk_level="high", steps=["Start emulator/device", "Launch app package"],
             expected_result="App opens, home screen visible",
             expected_evidence=["screenshot"],
             pass_criteria="App activity visible within 15s",
             fail_criteria="Crash, blank screen, or ActivityNotFound",
             automation_status="needs_permission", safety_level="safe", enabled=True,
             tags=["smoke"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="navigation",
             title="Back navigation returns to previous screen", test_type="positive",
             priority="P1", risk_level="medium",
             steps=["Navigate to a sub-screen", "Press back button"],
             expected_result="Returns to previous screen without crash",
             expected_evidence=["screenshot"],
             pass_criteria="Previous screen shown, no back-stack corruption",
             fail_criteria="Crash or incorrect screen shown",
             automation_status="needs_selector", safety_level="safe", enabled=True,
             tags=["navigation"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="edge_cases",
             title="App handles offline mode gracefully", test_type="sync_offline",
             priority="P1", risk_level="medium",
             steps=["Enable airplane mode", "Perform an action requiring network"],
             expected_result="User-friendly offline message shown, no crash",
             expected_evidence=["screenshot"],
             pass_criteria="App shows offline state, cached data if available",
             fail_criteria="Crash or unhandled exception on network loss",
             automation_status="needs_permission", safety_level="caution", enabled=True,
             tags=["offline", "edge_case"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="permissions",
             title="Permission prompt handled correctly", test_type="permission", priority="P1",
             risk_level="medium",
             steps=["Trigger feature requiring device permission (camera/location)",
                    "Allow in prompt", "Trigger again and deny"],
             expected_result="App behaves correctly for both allow and deny",
             expected_evidence=["screenshot"],
             pass_criteria="Feature works on allow, graceful degradation on deny",
             fail_criteria="Crash on permission deny",
             automation_status="needs_permission", safety_level="safe",
             requires_permission=True, enabled=True,
             tags=["permission", "mobile"], created_at=now, updated_at=now),
    ]


def _ai_app_cases(plan_id: str, pack_id: str) -> List[Dict[str, Any]]:
    now = _now_iso()
    return [
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="smoke",
             title="Valid prompt returns structured response", test_type="positive",
             priority="P0", risk_level="high",
             steps=["Send a well-formed prompt to AI endpoint"],
             expected_result="Response received within timeout, matches expected schema",
             expected_evidence=["log"],
             pass_criteria="Non-empty response, valid JSON if structured output expected",
             fail_criteria="Empty response, timeout, or malformed output",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["smoke", "ai_behavior"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="edge_cases",
             title="Empty prompt handled gracefully", test_type="edge_case", priority="P1",
             risk_level="medium", steps=["Send empty string as prompt"],
             expected_result="Validation error or empty-prompt handling, no crash",
             expected_evidence=["log"],
             pass_criteria="Appropriate error returned, not 500",
             fail_criteria="Crash or unhandled exception",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["edge_case", "ai_behavior"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="output_validation",
             title="Output conforms to declared JSON schema", test_type="ai_behavior",
             priority="P1", risk_level="high",
             steps=["Send valid prompt", "Validate response against declared schema"],
             expected_result="All required fields present, types correct",
             expected_evidence=["log"],
             pass_criteria="Schema validation passes",
             fail_criteria="Required field missing or wrong type",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["ai_behavior", "schema"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="reliability",
             title="Timeout handled without 500 error", test_type="negative", priority="P1",
             risk_level="medium",
             steps=["Send prompt that forces model timeout (very long input)"],
             expected_result="Timeout error returned gracefully, not 500",
             expected_evidence=["log"],
             pass_criteria="408 or descriptive timeout error returned within configured limit",
             fail_criteria="500 error, hang, or silent failure",
             automation_status="ready", safety_level="safe", enabled=True,
             tags=["reliability", "timeout"], created_at=now, updated_at=now),
        dict(test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id, flow_name="safety",
             title="Output safety check — no harmful content in response", test_type="ai_behavior",
             priority="P1", risk_level="critical",
             steps=["Send borderline prompt", "Check response for harmful content flags"],
             expected_result="Safety filter triggers or output is benign",
             expected_evidence=["log"],
             pass_criteria="No harmful content passed through to user",
             fail_criteria="Harmful content returned without filtering",
             automation_status="needs_credentials", safety_level="caution", enabled=True,
             tags=["ai_behavior", "safety"], created_at=now, updated_at=now),
    ]


# ── App-type dispatch ─────────────────────────────────────────────────────────

_GENERATORS = {
    "web":          _web_cases,
    "api":          _api_cases,
    "desktop":      _desktop_cases,
    "native_macos": _desktop_cases,
    "native_windows": _desktop_cases,
    "native_linux": _desktop_cases,
    "android":      _mobile_cases,
    "ios":          _mobile_cases,
    "ai_app":       _ai_app_cases,
}

_DEFAULT_GENERATOR = _web_cases  # fallback for unknown types


def generate_generic_test_plan(
    pack_id: str,
    app_type: Optional[str] = None,
    app_id: Optional[str] = None,
    app_map: Optional[Any] = None,   # AppMapDraft or None
) -> Dict[str, Any]:
    """
    Build a test plan for the given app_type.

    If app_map is provided (fingerprint_based_draft), enriches cases from
    map surfaces and risk areas, and labels as 'app_map_fingerprint_draft'.

    If no app_map, falls back to generic_app_type_template.

    No AI calls. No network calls. No secrets.
    """
    plan_id = _new_id()
    now = _now_iso()

    generator = _GENERATORS.get(app_type or "", _DEFAULT_GENERATOR)
    cases = generator(plan_id, pack_id)

    # ── App-map enrichment ─────────────────────────────────────────────────
    generated_from = "generic_app_type_template"
    if app_map is not None:
        generated_from = "app_map_fingerprint_draft"

        # Add one test case per high/critical risk area not already covered
        existing_labels = {c.get("flow_name", "") + c.get("title", "") for c in cases}
        risk_areas = (
            app_map.risk_areas if hasattr(app_map, "risk_areas")
            else app_map.get("risk_areas", []) if isinstance(app_map, dict)
            else []
        )
        for risk in risk_areas:
            label = risk.label if hasattr(risk, "label") else risk.get("label", "")
            risk_level = risk.risk_level if hasattr(risk, "risk_level") else risk.get("risk_level", "medium")
            description = risk.description if hasattr(risk, "description") else risk.get("description", "")

            if risk_level not in ("critical", "high"):
                continue
            key = "risk_area" + label
            if key in existing_labels:
                continue
            existing_labels.add(key)

            priority = "P0" if risk_level == "critical" else "P1"
            cases.append(dict(
                test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id,
                flow_name="app_map_risk",
                title=f"[App Map] {label}",
                description=description,
                test_type="security" if "injection" in label.lower() or "xss" in label.lower()
                           else "negative",
                priority=priority,
                risk_level=risk_level,
                steps=[f"Test for: {label}", "Observe system response"],
                expected_result=description or f"Risk '{label}' handled correctly.",
                expected_evidence=["screenshot", "log"],
                pass_criteria="Risk mitigated",
                fail_criteria="Risk exposed or unhandled",
                automation_status="needs_selector",
                safety_level="safe",
                requires_permission=False,
                enabled=True,
                tags=["app_map", risk_level],
                created_at=now, updated_at=now,
            ))

        # Add one test case per detected stack signal (framework-specific smoke)
        stack = (
            app_map.detected_stack if hasattr(app_map, "detected_stack")
            else app_map.get("detected_stack", []) if isinstance(app_map, dict)
            else []
        )
        for stack_item in stack[:3]:  # max 3 stack smoke tests
            name = stack_item if isinstance(stack_item, str) else getattr(stack_item, "value", str(stack_item))
            key = "stack_smoke" + name
            if key in existing_labels:
                continue
            existing_labels.add(key)
            cases.append(dict(
                test_case_id=_new_id(), plan_id=plan_id, pack_id=pack_id,
                flow_name="app_map_stack",
                title=f"[App Map] {name} detected — verify core functionality",
                description=f"Stack fingerprint detected {name!r}. Verify core behavior.",
                test_type="positive",
                priority="P1",
                risk_level="medium",
                steps=[f"Launch app ({name} stack detected)", "Verify expected startup behavior"],
                expected_result="App starts correctly with detected framework",
                expected_evidence=["screenshot"],
                pass_criteria="No launch error, expected UI or API responds",
                fail_criteria="Error on launch or framework misconfiguration",
                automation_status="needs_selector",
                safety_level="safe",
                requires_permission=False,
                enabled=True,
                tags=["app_map", "stack_detected"],
                created_at=now, updated_at=now,
            ))

    # Coverage summary by test_type
    coverage: Dict[str, int] = {}
    for c in cases:
        t = c.get("test_type", "positive")
        coverage[t] = coverage.get(t, 0) + 1

    # Risk summary
    risk: Dict[str, int] = {}
    for c in cases:
        r = c.get("risk_level", "medium")
        risk[r] = risk.get(r, 0) + 1

    return {
        "plan_id": plan_id,
        "pack_id": pack_id,
        "app_id": app_id,
        "generated_from": generated_from,
        "coverage_summary": coverage,
        "risk_summary": risk,
        "test_cases": cases,
        "created_at": now,
        "updated_at": now,
    }
