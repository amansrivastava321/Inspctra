"""
software_understanding_engine.py - Infer software intent and risk posture from deterministic context.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class SoftwareUnderstandingEngine:
    """Builds an evidence-backed understanding of the software under audit."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, app_path: str = "") -> Dict[str, Any]:
        app_map = self._load("app_map")
        stack = app_map.get("stack", {}) if isinstance(app_map.get("stack"), dict) else {}
        framework = str(stack.get("framework", "unknown")).lower()
        app_type = str(stack.get("app_type", "")).lower()
        language = str(stack.get("language", "unknown")).lower()

        routes = self._routes(app_map)
        apis = self._apis(app_map)
        screens = app_map.get("screens", []) if isinstance(app_map.get("screens"), list) else []
        critical_flows = app_map.get("critical_flows", []) if isinstance(app_map.get("critical_flows"), list) else []

        software_type = self._infer_software_type(framework=framework, app_type=app_type, routes=routes, apis=apis)
        sensitive_areas = self._sensitive_areas(app_map, apis, screens)
        entities = self._entities_from_apis(apis)
        risk_areas = self._business_risk_areas(sensitive_areas, critical_flows, software_type)
        graphify = self._graphify_context()

        result = {
            "software_type": software_type,
            "framework": framework,
            "language": language,
            "critical_workflows": self._critical_workflow_names(critical_flows, routes),
            "sensitive_areas": sensitive_areas,
            "likely_data_entities": entities,
            "business_risk_areas": risk_areas,
            "graphify_context": graphify,
            "source_artifacts": [
                "app_map.json",
                "graphify-out/GRAPH_REPORT.md",
                "graphify-out/graph.json",
            ],
            "summary": {
                "route_count": len(routes),
                "api_count": len(apis),
                "screen_count": len(screens),
                "critical_workflow_count": len(critical_flows),
                "confidence": round(self._confidence(software_type, routes, apis, screens), 2),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("software_understanding", result, agent="SoftwareUnderstandingEngine")
        return result

    def _infer_software_type(self, framework: str, app_type: str, routes: List[str], apis: List[Dict[str, Any]]) -> str:
        if "flutter" in framework or app_type == "mobile":
            return "mobile_application"
        if "fastapi" in framework or "django" in framework or app_type == "backend":
            return "api_backend_service"
        if "react" in framework or "next" in framework or app_type == "frontend":
            return "web_application"
        if routes and apis:
            return "full_stack_application"
        if apis:
            return "api_service"
        if routes:
            return "ui_application"
        return "unknown_application"

    def _routes(self, app_map: Dict[str, Any]) -> List[str]:
        routes: Set[str] = set()
        for screen in app_map.get("screens", []) if isinstance(app_map.get("screens"), list) else []:
            if isinstance(screen, dict):
                path = str(screen.get("path", "")).strip()
                if path:
                    routes.add(path)
        return sorted(routes)

    def _apis(self, app_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        endpoints = app_map.get("api_endpoints", [])
        if not isinstance(endpoints, list):
            return []
        return [endpoint for endpoint in endpoints if isinstance(endpoint, dict)]

    def _critical_workflow_names(self, flows: List[Dict[str, Any]], routes: List[str]) -> List[str]:
        names: List[str] = []
        for flow in flows:
            if isinstance(flow, dict):
                value = str(flow.get("name", "")).strip()
                if value:
                    names.append(value)
        if not names and routes:
            names.extend([f"route_flow:{route}" for route in routes[:5]])
        if not names:
            names = ["baseline_smoke_flow"]
        return sorted(dict.fromkeys(names))

    def _sensitive_areas(self, app_map: Dict[str, Any], apis: List[Dict[str, Any]], screens: List[Dict[str, Any]]) -> List[str]:
        sensitive: Set[str] = set()
        surfaces = app_map.get("security_surfaces", {})
        if isinstance(surfaces, dict):
            for key in ("auth_endpoints", "payment_endpoints", "admin_endpoints"):
                values = surfaces.get(key, [])
                if isinstance(values, list) and values:
                    sensitive.add(key.replace("_endpoints", ""))
        for endpoint in apis:
            if str(endpoint.get("auth_required", "")).lower() == "true":
                sensitive.add("authenticated_api")
            risk = endpoint.get("risk", {})
            if isinstance(risk, dict) and str(risk.get("risk_level", "")).lower() in {"high", "critical"}:
                sensitive.add("high_risk_api")
        for screen in screens:
            if not isinstance(screen, dict):
                continue
            if bool(screen.get("auth_required", False)):
                sensitive.add("authenticated_ui")
        if not sensitive:
            sensitive.add("general_application_surface")
        return sorted(sensitive)

    def _entities_from_apis(self, apis: List[Dict[str, Any]]) -> List[str]:
        entities: Set[str] = set()
        for endpoint in apis:
            path = str(endpoint.get("path", "")).strip().strip("/")
            if not path:
                continue
            first = path.split("/")[0]
            if first and not first.startswith("{"):
                entities.add(first.replace("-", "_"))
        if not entities:
            entities.add("application_state")
        return sorted(entities)

    def _business_risk_areas(self, sensitive: List[str], flows: List[Dict[str, Any]], software_type: str) -> List[str]:
        areas: Set[str] = set()
        areas.update(sensitive)
        for flow in flows:
            if not isinstance(flow, dict):
                continue
            priority = str(flow.get("priority", "")).lower()
            flow_type = str(flow.get("type", "")).lower()
            if priority in {"critical", "p0"} or flow_type:
                areas.add(flow_type or "critical_flow")
        if software_type in {"api_backend_service", "api_service"}:
            areas.update({"authorization", "input_validation", "availability"})
        if software_type in {"mobile_application"}:
            areas.update({"offline_sync", "device_state"})
        if software_type in {"web_application", "full_stack_application"}:
            areas.update({"session_integrity", "navigation_integrity"})
        return sorted(areas)

    def _confidence(self, software_type: str, routes: List[str], apis: List[Dict[str, Any]], screens: List[Dict[str, Any]]) -> float:
        base = 0.45 if software_type == "unknown_application" else 0.62
        base += min(len(routes), 10) * 0.01
        base += min(len(apis), 10) * 0.015
        base += min(len(screens), 10) * 0.01
        return max(0.0, min(0.95, base))

    def _graphify_context(self) -> Dict[str, Any]:
        graph_path = Path("graphify-out/graph.json")
        report_path = Path("graphify-out/GRAPH_REPORT.md")
        nodes = 0
        edges = 0
        report_preview = ""
        if graph_path.exists():
            try:
                graph = json.loads(graph_path.read_text(encoding="utf-8"))
                nodes_list = graph.get("nodes", [])
                edges_list = graph.get("edges") if isinstance(graph.get("edges"), list) else graph.get("links", [])
                nodes = len(nodes_list) if isinstance(nodes_list, list) else 0
                edges = len(edges_list) if isinstance(edges_list, list) else 0
            except (OSError, json.JSONDecodeError):
                pass
        if report_path.exists():
            report_preview = "\n".join(report_path.read_text(encoding="utf-8").splitlines()[:18])
        return {"graph_nodes": nodes, "graph_edges": edges, "report_preview": report_preview}

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
