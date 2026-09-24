"""
evidence_correlator.py - Links evidence artifacts to findings, workflow steps,
APIs, and pages. Builds an evidence graph connecting screenshots, request/response
traces, logs, findings, and execution data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set
import logging
import time

from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class EvidenceNode:
    """A node in the evidence graph."""

    def __init__(self, node_id: str, node_type: str, data: Dict[str, Any]):
        self.node_id = node_id
        self.node_type = node_type  # "evidence", "finding", "api", "page", "workflow_step"
        self.data = data
        self.links: List[str] = []  # IDs of linked nodes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "data": self.data,
            "links": self.links,
        }


class RuntimeEvidenceCorrelator:
    """
    Links evidence artifacts to findings, workflow steps, APIs, and pages.

    Builds an evidence graph:
    - Screenshots linked to pages and test cases
    - API responses linked to endpoints and findings
    - Logs linked to test runs and errors
    - Findings linked to evidence and source audits
    - Workflow steps linked to all of the above
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.validator = ArtifactValidator()

    def run(
        self,
        verified_findings: Optional[Dict[str, Any]] = None,
        execution_results: Optional[Dict[str, Any]] = None,
        app_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the evidence graph."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if verified_findings is None:
            verified_findings = self.store.load_artifact("verified_findings") or {}

        if execution_results is None:
            execution_results = self.store.load_artifact("execution_results") or {}

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        verified_findings = verified_findings if isinstance(verified_findings, dict) else {}
        execution_results = execution_results if isinstance(execution_results, dict) else {}
        app_map = app_map if isinstance(app_map, dict) else {}
        execution_results = self.validator.validate_for_consumption(
            artifact_name="execution_results",
            data=execution_results,
        ).data if execution_results else {}

        nodes: Dict[str, EvidenceNode] = {}
        edges: List[Dict[str, str]] = []

        # Build finding nodes
        findings = verified_findings.get("verified_findings", [])
        if not findings:
            correlated = self.store.load_artifact("correlated_findings") or {}
            findings = correlated.get("findings", [])

        for f in findings:
            fid = f.get("id", "")
            if fid:
                nodes[fid] = EvidenceNode(fid, "finding", {
                    "title": f.get("title", ""),
                    "severity": f.get("severity", ""),
                    "category": f.get("category", f.get("tags", [""])[0] if f.get("tags") else ""),
                    "verification_status": f.get("verification_status", "unverified"),
                })

                # Link finding to its evidence
                for ev in f.get("evidence", f.get("exploit_evidence", [])):
                    eid = ev.get("evidence_id", f"ev-{fid}-{len(edges)}")
                    if eid not in nodes:
                        nodes[eid] = EvidenceNode(eid, "evidence", ev)
                    edges.append({"from": fid, "to": eid, "type": "has_evidence"})

        # Build API endpoint nodes
        endpoints = app_map.get("api_endpoints", [])
        for ep in endpoints:
            ep_id = f"api-{ep.get('method', 'GET')}-{ep.get('path', '')}".replace("/", "_")
            nodes[ep_id] = EvidenceNode(ep_id, "api", {
                "method": ep.get("method", ""),
                "path": ep.get("path", ""),
                "auth_required": ep.get("auth_required"),
            })

            # Link findings to APIs
            for f in findings:
                target = f.get("target", f.get("api_endpoint", ""))
                if target and ep.get("path", "") in target:
                    fid = f.get("id", "")
                    if fid and fid in nodes:
                        edges.append({"from": fid, "to": ep_id, "type": "targets_api"})

        # Build page/screen nodes
        screens = app_map.get("screens", [])
        for screen in screens:
            sid = f"page-{screen.get('path', screen.get('name', ''))}"
            nodes[sid] = EvidenceNode(sid, "page", {
                "name": screen.get("name", ""),
                "path": screen.get("path", ""),
                "auth_required": screen.get("auth_required"),
            })

        # Build execution test nodes
        suites = execution_results.get("suites", [])
        for suite in suites:
            for test in suite.get("tests", []):
                tid = test.get("test_id", "")
                if tid:
                    nodes[tid] = EvidenceNode(tid, "test_execution", {
                        "title": test.get("test_title", ""),
                        "outcome": test.get("outcome", ""),
                        "duration": test.get("duration_seconds", 0),
                    })

                    # Link test to its evidence paths
                    for ep in test.get("evidence_paths", []):
                        eid = f"ev-{tid}"
                        if eid not in nodes:
                            nodes[eid] = EvidenceNode(eid, "evidence", {"path": ep})
                        edges.append({"from": tid, "to": eid, "type": "produced_evidence"})

                    # Link test to matching finding
                    for f in findings:
                        if f.get("id") == tid:
                            edges.append({"from": tid, "to": tid, "type": "validates_finding"})

        # Build workflow step nodes from critical flows
        flows = app_map.get("critical_flows", [])
        for flow in flows:
            flow_name = flow.get("name", "")
            if flow_name:
                fid = f"flow-{flow_name}"
                nodes[fid] = EvidenceNode(fid, "workflow_step", {
                    "name": flow_name,
                    "priority": flow.get("priority", ""),
                    "steps": flow.get("steps", []),
                })

        # Persist evidence graph
        graph = {
            "nodes": [n.to_dict() for n in nodes.values()],
            "edges": edges,
        }

        duration = time.time() - start_time

        result = {
            "metadata": {
                "correlation_type": "evidence_correlation",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "RuntimeEvidenceCorrelator",
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
            "graph": graph,
            "summary": {
                "finding_nodes": sum(1 for n in nodes.values() if n.node_type == "finding"),
                "evidence_nodes": sum(1 for n in nodes.values() if n.node_type == "evidence"),
                "api_nodes": sum(1 for n in nodes.values() if n.node_type == "api"),
                "page_nodes": sum(1 for n in nodes.values() if n.node_type == "page"),
                "test_nodes": sum(1 for n in nodes.values() if n.node_type == "test_execution"),
                "workflow_nodes": sum(1 for n in nodes.values() if n.node_type == "workflow_step"),
            },
        }

        self.store.save_artifact("evidence_graph", result, agent="RuntimeEvidenceCorrelator")
        logger.info(f"Evidence graph built: {len(nodes)} nodes, {len(edges)} edges")
        return result
