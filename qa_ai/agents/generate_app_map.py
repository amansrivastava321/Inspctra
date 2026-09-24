"""
generate_app_map.py - Production-grade application knowledge graph generator.

Creates app_map.json for autonomous QA agents.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any
from dataclasses import asdict, is_dataclass
from enum import Enum

from qa_ai.agents.detect_stack import detect_stack, StackInfo
from qa_ai.runtime.artifact_store import ArtifactStore

try:
    from qa_ai.agents.scan_routes import RouteScanner
except ImportError:
    RouteScanner = None

try:
    from qa_ai.agents.scan_apis import ApiScanner
except ImportError:
    ApiScanner = None


DISCOVERY_VERSION = "1.1.0"


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    return value


def _stack_to_dict(stack: StackInfo) -> dict:
    return {
        "framework": stack.framework.value,
        "language": stack.language.value,
        "app_type": stack.app_type.value,
        "framework_version": stack.framework_version,
        "language_version": stack.language_version,
        "state_management": stack.state_management,
        "router_library": stack.router_library,
        "http_client": stack.http_client,
        "database": stack.database,
        "auth_provider": stack.auth_provider,
        "css_framework": stack.css_framework,
        "bundler": stack.bundler,
        "test_framework": stack.test_framework,
        "package_manager": stack.package_manager,
        "build_tool": stack.build_tool,
        "capabilities": {
            "has_auth": stack.has_auth,
            "has_api": stack.has_api,
            "has_database": stack.has_database,
            "has_payments": stack.has_payments,
            "has_file_upload": stack.has_file_upload,
            "has_real_time": stack.has_real_time,
            "has_i18n": stack.has_i18n,
            "has_dark_mode": stack.has_dark_mode,
            "has_offline_support": stack.has_offline_support,
            "has_e2e_tests": stack.has_e2e_tests,
            "has_unit_tests": stack.has_unit_tests,
        },
        "confidence": stack.confidence_score,
    }


def _fallback_scan_routes(app_path: Path) -> dict:
    from qa_ai.agents.scan_routes import scan_routes

    routes = scan_routes(app_path)

    return {
        "routes": [
            {
                "path": route,
                "route": route,
                "name": route,
                "auth_required": None,
                "source": "fallback_scan_routes",
            }
            for route in routes
        ],
        "total_screens": len(routes),
        "auth_protected_screens": 0,
        "unprotected_screens": 0,
    }


def _fallback_scan_apis(app_path: Path) -> dict:
    from qa_ai.agents.scan_apis import scan_apis

    endpoints = scan_apis(app_path)

    normalized = []

    for endpoint in endpoints:
        if " " not in endpoint:
            continue

        method, path = endpoint.split(" ", 1)

        normalized.append(
            {
                "method": method.upper(),
                "path": path,
                "auth_required": None,
                "source": "fallback_scan_apis",
            }
        )

    return {
        "all_endpoints": normalized,
        "total_backend": len(normalized),
        "total_frontend": 0,
        "auth_protected": 0,
        "unprotected": 0,
        "external_services": [],
    }


def _classify_api_risk(endpoint: dict) -> dict:
    method = str(endpoint.get("method", "")).upper()
    path = str(endpoint.get("path", "")).lower()

    mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}

    financial_keywords = [
        "payment",
        "checkout",
        "stripe",
        "refund",
        "invoice",
        "billing",
        "subscription",
    ]

    admin_keywords = [
        "admin",
        "staff",
        "role",
        "permission",
        "user-management",
    ]

    auth_keywords = [
        "login",
        "signup",
        "register",
        "token",
        "otp",
        "password",
        "auth",
    ]

    mutates_data = method in mutating_methods
    financial_operation = any(k in path for k in financial_keywords)
    admin_operation = any(k in path for k in admin_keywords)
    auth_operation = any(k in path for k in auth_keywords)

    risk_level = "low"

    if financial_operation or admin_operation:
        risk_level = "critical"
    elif mutates_data or auth_operation:
        risk_level = "high"
    elif endpoint.get("auth_required") is False:
        risk_level = "medium"

    endpoint["risk"] = {
        "risk_level": risk_level,
        "mutates_data": mutates_data,
        "financial_operation": financial_operation,
        "admin_operation": admin_operation,
        "auth_operation": auth_operation,
        "rate_limited": endpoint.get("rate_limited"),
    }

    return endpoint


def _build_security_surfaces(api_endpoints: list, screens: list, stack: StackInfo) -> dict:
    public_endpoints = []
    payment_endpoints = []
    admin_endpoints = []
    auth_endpoints = []
    file_upload_endpoints = []

    for endpoint in api_endpoints:
        path = str(endpoint.get("path", "")).lower()

        if endpoint.get("auth_required") is False:
            public_endpoints.append(endpoint)

        if any(k in path for k in ["payment", "checkout", "stripe", "refund", "billing"]):
            payment_endpoints.append(endpoint)

        if any(k in path for k in ["admin", "role", "permission", "staff"]):
            admin_endpoints.append(endpoint)

        if any(k in path for k in ["auth", "login", "signup", "token", "otp", "password"]):
            auth_endpoints.append(endpoint)

        if any(k in path for k in ["upload", "file", "image", "document"]):
            file_upload_endpoints.append(endpoint)

    admin_routes = []
    auth_routes = []

    for screen in screens:
        route = str(screen.get("path") or screen.get("route") or "").lower()
        name = str(screen.get("name", "")).lower()

        if "admin" in route or "admin" in name:
            admin_routes.append(screen)

        if screen.get("auth_required") is True:
            auth_routes.append(screen)

    return {
        "public_endpoints": public_endpoints,
        "payment_endpoints": payment_endpoints,
        "admin_endpoints": admin_endpoints,
        "auth_endpoints": auth_endpoints,
        "file_upload_endpoints": file_upload_endpoints,
        "admin_routes": admin_routes,
        "auth_routes": auth_routes,
        "webviews": [],
        "deep_links": [],
        "sensitive_permissions": [],
        "detected_capabilities": {
            "has_auth": stack.has_auth,
            "has_payments": stack.has_payments,
            "has_file_upload": stack.has_file_upload,
            "has_database": stack.has_database,
            "has_real_time": stack.has_real_time,
        },
    }


def _infer_critical_flows(screens: list, api_endpoints: list) -> list:
    flows = []

    screen_names = [str(s.get("name", "")).lower() for s in screens]
    route_values = [str(s.get("path") or s.get("route") or "").lower() for s in screens]
    combined = screen_names + route_values

    def has_any(words: list[str]) -> bool:
        return any(any(word in value for word in words) for value in combined)

    if has_any(["login", "auth", "signin"]):
        flows.append(
            {
                "name": "authentication_flow",
                "priority": "critical",
                "type": "auth",
                "steps": [],
                "expected_outcome": "User can securely sign in and reach protected areas.",
            }
        )

    if has_any(["checkout", "cart", "payment", "billing"]):
        flows.append(
            {
                "name": "checkout_payment_flow",
                "priority": "critical",
                "type": "payment",
                "steps": [],
                "expected_outcome": "User can complete payment without duplication, leakage, or failure.",
            }
        )

    if has_any(["profile", "account", "settings"]):
        flows.append(
            {
                "name": "profile_account_flow",
                "priority": "high",
                "type": "account_management",
                "steps": [],
                "expected_outcome": "User can view and update account data safely.",
            }
        )

    if has_any(["admin", "dashboard", "staff"]):
        flows.append(
            {
                "name": "admin_management_flow",
                "priority": "critical",
                "type": "admin",
                "steps": [],
                "expected_outcome": "Only authorized users can access privileged functions.",
            }
        )

    return flows


def _build_agent_hints(stack: StackInfo, api_endpoints: list, screens: list) -> dict:
    critical_apis = [
        ep for ep in api_endpoints
        if ep.get("risk", {}).get("risk_level") == "critical"
    ]

    return {
        "test_planner_agent": {
            "prioritize": [
                "critical_flows",
                "auth_protected_routes",
                "public_endpoints",
                "payment_endpoints",
                "high_risk_mutations",
            ],
            "generate_test_types": [
                "smoke",
                "functional",
                "regression",
                "security",
                "performance",
                "accessibility",
                "negative",
                "edge_case",
            ],
        },
        "security_agent": {
            "focus_areas": {
                "critical_apis": critical_apis,
                "auth_required": stack.has_auth,
                "payments": stack.has_payments,
                "file_upload": stack.has_file_upload,
                "database": stack.has_database,
            },
            "recommended_tests": [
                "missing_auth_token",
                "expired_token",
                "role_bypass",
                "idempotency",
                "rate_limit",
                "input_validation",
                "sensitive_data_exposure",
            ],
        },
        "performance_agent": {
            "focus_areas": [
                "startup_time",
                "route_transition_time",
                "api_latency",
                "large_payloads",
                "database_queries",
                "offline_sync",
            ],
        },
        "compliance_agent": {
            "focus_areas": [
                "privacy",
                "permissions",
                "data_retention",
                "payment_security",
                "access_control",
                "audit_logs",
            ],
        },
        "report_agent": {
            "evidence_required": True,
            "link_findings_to": [
                "screen",
                "api_endpoint",
                "critical_flow",
                "code_file",
                "test_case",
            ],
        },
    }


def generate_app_map(
    app_path: Path,
    artifact_store: Optional[ArtifactStore] = None,
) -> dict:
    app_path = Path(app_path).expanduser().resolve()

    if not app_path.exists():
        raise FileNotFoundError(f"App path does not exist: {app_path}")

    if not app_path.is_dir():
        raise NotADirectoryError(f"App path is not a directory: {app_path}")

    if artifact_store is None:
        artifact_store = ArtifactStore("artifacts")

    stack: StackInfo = detect_stack(app_path)
    stack_context = _json_safe(stack)

    if RouteScanner is not None:
        route_scanner = RouteScanner(app_path, stack_context)
        route_result = _json_safe(route_scanner.scan_all() or {})
    else:
        route_result = _fallback_scan_routes(app_path)

    if ApiScanner is not None:
        api_scanner = ApiScanner(app_path, stack_context)
        api_result = _json_safe(api_scanner.scan_all() or {})
    else:
        api_result = _fallback_scan_apis(app_path)

    screens = route_result.get("routes", [])
    api_endpoints = api_result.get("all_endpoints", [])

    api_endpoints = [_classify_api_risk(endpoint) for endpoint in api_endpoints]

    critical_flows = _infer_critical_flows(screens, api_endpoints)
    security_surfaces = _build_security_surfaces(api_endpoints, screens, stack)
    agent_hints = _build_agent_hints(stack, api_endpoints, screens)

    app_map = {
        "metadata": {
            "app_name": app_path.name,
            "app_path": str(app_path),
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "discovery_version": DISCOVERY_VERSION,
            "generated_by": "DiscoveryAgent",
        },

        "stack": _stack_to_dict(stack),

        "entry_points": {
            "app_start": None,
            "auth_gate": None,
            "root_router": None,
            "main_backend_server": None,
            "cli_entry": None,
        },

        "screens": screens,

        "navigation_graph": {
            "nodes": screens,
            "edges": [],
            "entry_screen": None,
            "protected_nodes": [
                screen for screen in screens
                if screen.get("auth_required") is True
            ],
            "public_nodes": [
                screen for screen in screens
                if screen.get("auth_required") is False
            ],
            "dead_end_candidates": [],
            "unreachable_candidates": [],
        },

        "screen_metadata": {
            "auth_required_screens": [
                screen for screen in screens
                if screen.get("auth_required") is True
            ],
            "public_screens": [
                screen for screen in screens
                if screen.get("auth_required") is False
            ],
            "payment_screens": [
                screen for screen in screens
                if any(
                    key in str(screen).lower()
                    for key in ["payment", "checkout", "billing", "cart"]
                )
            ],
            "admin_screens": [
                screen for screen in screens
                if any(
                    key in str(screen).lower()
                    for key in ["admin", "staff", "role", "permission"]
                )
            ],
        },

        "api_endpoints": api_endpoints,

        "api_risk_summary": {
            "critical": [
                ep for ep in api_endpoints
                if ep.get("risk", {}).get("risk_level") == "critical"
            ],
            "high": [
                ep for ep in api_endpoints
                if ep.get("risk", {}).get("risk_level") == "high"
            ],
            "medium": [
                ep for ep in api_endpoints
                if ep.get("risk", {}).get("risk_level") == "medium"
            ],
            "low": [
                ep for ep in api_endpoints
                if ep.get("risk", {}).get("risk_level") == "low"
            ],
        },

        "critical_flows": critical_flows,

        "dependency_graph": {
            "screen_to_api": {},
            "api_to_screen": {},
            "screen_to_state": {},
            "screen_to_services": {},
            "service_to_api": {},
            "provider_to_screen": {},
            "code_file_to_feature": {},
        },

        "state_map": {
            "state_management": stack.state_management,
            "stores": [],
            "providers": [],
            "controllers": [],
            "mutated_entities": [],
            "sensitive_state": [],
        },

        "security_surfaces": security_surfaces,

        "permissions": {
            "camera": [],
            "location": [],
            "microphone": [],
            "contacts": [],
            "storage": [],
            "photos": [],
            "notifications": [],
            "bluetooth": [],
            "biometrics": [],
        },

        "external_services": {
            "payments": [],
            "auth": [],
            "analytics": [],
            "crash_reporting": [],
            "messaging": [],
            "storage": [],
            "maps": [],
            "ai_services": [],
            "other": api_result.get("external_services", []),
        },

        "feature_flags": [],

        "environment_config": {
            "env_files_detected": [],
            "environments": {
                "local": None,
                "dev": None,
                "staging": None,
                "production": None,
            },
            "secrets_detected": [],
            "config_risks": [],
        },

        "testability": {
            "has_unit_tests": stack.has_unit_tests,
            "has_e2e_tests": stack.has_e2e_tests,
            "test_framework": stack.test_framework,
            "has_mock_server": False,
            "has_seed_data": False,
            "has_test_ids": False,
            "supports_offline_testing": stack.has_offline_support,
            "recommended_test_strategy": {
                "smoke": True,
                "functional": True,
                "regression": True,
                "security": True,
                "performance": True,
                "accessibility": True,
                "cross_platform": stack.app_type.value in ["mobile", "web", "desktop"],
            },
        },

        "code_health": {
            "large_files": [],
            "duplicate_routes": [],
            "dead_code_candidates": [],
            "high_complexity_modules": [],
            "circular_dependency_candidates": [],
            "missing_error_handling_candidates": [],
            "missing_loading_state_candidates": [],
        },

        "quality_risks": {
            "auth_risks": [],
            "api_risks": [],
            "payment_risks": [],
            "offline_sync_risks": [],
            "performance_risks": [],
            "privacy_risks": [],
            "accessibility_risks": [],
            "platform_risks": [],
        },

        "routes_summary": {
            "total_screens": route_result.get("total_screens", len(screens)),
            "auth_protected": route_result.get("auth_protected_screens", 0),
            "unprotected": route_result.get("unprotected_screens", 0),
        },

        "api_summary": {
            "total_backend_endpoints": api_result.get("total_backend", 0),
            "total_frontend_calls": api_result.get("total_frontend", 0),
            "auth_protected": api_result.get("auth_protected", 0),
            "unprotected": api_result.get("unprotected", 0),
            "external_services": api_result.get("external_services", []),
        },

        "agent_hints": agent_hints,

        "evidence_index": {
            "screens": {},
            "apis": {},
            "flows": {},
            "files": {},
            "tests": {},
        },

        "raw_dependencies": stack.raw_dependencies,
        "detected_files": stack.detected_files,
    }

    app_map = _json_safe(app_map)

    artifact_store.save_artifact(
        artifact_name="app_map",
        data=app_map,
        version=DISCOVERY_VERSION,
        metadata={
            "source": "DiscoveryAgent",
            "app_path": str(app_path),
            "stack_framework": stack.framework.value,
            "discovery_version": DISCOVERY_VERSION,
        },
    )

    return app_map


if __name__ == "__main__":
    import sys
    from pprint import pprint

    if len(sys.argv) < 2:
        print("Usage: python generate_app_map.py /path/to/app")
        sys.exit(1)

    generated_map = generate_app_map(Path(sys.argv[1]))
    pprint(generated_map)