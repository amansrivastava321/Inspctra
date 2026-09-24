"""
root_cause_engine.py - Identifies probable shared root causes,
architectural hotspots, and cascading failures from correlated findings.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set
import logging
import time
from collections import defaultdict

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class RootCause:
    """A probable root cause linking multiple findings."""

    def __init__(self, cause_id: str, description: str, root_type: str):
        self.cause_id = cause_id
        self.description = description
        self.root_type = root_type
        self.finding_ids: List[str] = []
        self.affected_files: Set[str] = set()
        self.affected_endpoints: Set[str] = set()
        self.affected_workflows: Set[str] = set()
        self.confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "description": self.description,
            "root_type": self.root_type,
            "finding_ids": self.finding_ids,
            "affected_files": sorted(self.affected_files),
            "affected_endpoints": sorted(self.affected_endpoints),
            "affected_workflows": sorted(self.affected_workflows),
            "confidence": round(self.confidence, 2),
            "impact_count": len(self.finding_ids),
        }


class RootCauseEngine:
    """
    Identifies probable shared root causes by analyzing:
    - Findings sharing the same file
    - Findings sharing the same endpoint
    - Findings sharing the same category
    - Architectural hotspots (files with many findings)
    - Likely cascading failures
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        correlated_findings: Optional[Dict[str, Any]] = None,
        app_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run root cause analysis."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if correlated_findings is None:
            correlated_findings = self.store.load_artifact("correlated_findings") or {}

        findings = correlated_findings.get("findings", [])
        correlations = correlated_findings.get("correlations", {})

        root_causes: List[RootCause] = []
        cause_counter = 0

        # 1. Findings sharing files → file-level root cause
        file_groups = self._group_by_field(findings, "file_path")
        for fp, group_findings in file_groups.items():
            if len(group_findings) >= 2:
                cause_counter += 1
                rc = RootCause(
                    cause_id=f"RC-FILE-{cause_counter:03d}",
                    description=f"Multiple issues in {fp} suggest a systemic code quality problem.",
                    root_type="file_hotspot",
                )
                rc.finding_ids = [f["id"] for f in group_findings]
                rc.affected_files.add(fp)
                rc.confidence = min(0.9, 0.3 + len(group_findings) * 0.15)
                root_causes.append(rc)

        # 2. Findings sharing endpoints → endpoint-level root cause
        endpoint_groups = self._group_by_field(findings, "api_endpoint")
        for ep, group_findings in endpoint_groups.items():
            if ep and len(group_findings) >= 2:
                cause_counter += 1
                rc = RootCause(
                    cause_id=f"RC-EP-{cause_counter:03d}",
                    description=f"Multiple issues around endpoint {ep} suggest an architectural concern.",
                    root_type="endpoint_risk",
                )
                rc.finding_ids = [f["id"] for f in group_findings]
                rc.affected_endpoints.add(ep)
                rc.confidence = min(0.85, 0.3 + len(group_findings) * 0.15)
                root_causes.append(rc)

        # 3. Category clusters → category-level root cause
        category_groups = self._group_by_field(findings, "category")
        for cat, group_findings in category_groups.items():
            if len(group_findings) >= 3:
                cause_counter += 1
                rc = RootCause(
                    cause_id=f"RC-CAT-{cause_counter:03d}",
                    description=f"Cluster of {len(group_findings)} '{cat}' findings suggests a systemic issue.",
                    root_type="category_cluster",
                )
                rc.finding_ids = [f["id"] for f in group_findings]
                for f in group_findings:
                    if f.get("file_path"):
                        rc.affected_files.add(f["file_path"])
                rc.confidence = min(0.8, 0.2 + len(group_findings) * 0.1)
                root_causes.append(rc)

        # 4. Cascading failure detection
        cascades = self._detect_cascades(findings, correlations)
        root_causes.extend(cascades)

        # 5. Architectural hotspots
        hotspots = self._find_hotspots(correlations)

        duration = time.time() - start_time

        result = {
            "metadata": {
                "analysis_type": "root_cause_analysis",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "RootCauseEngine",
                "total_findings_analyzed": len(findings),
            },
            "root_causes": [rc.to_dict() for rc in root_causes],
            "hotspots": hotspots,
            "summary": {
                "total_root_causes": len(root_causes),
                "file_hotspots": sum(1 for rc in root_causes if rc.root_type == "file_hotspot"),
                "endpoint_risks": sum(1 for rc in root_causes if rc.root_type == "endpoint_risk"),
                "category_clusters": sum(1 for rc in root_causes if rc.root_type == "category_cluster"),
                "cascading_failures": sum(1 for rc in root_causes if rc.root_type == "cascading_failure"),
            },
        }

        self.store.save_artifact("root_cause_analysis", result, agent="RootCauseEngine")
        logger.info(f"Root cause analysis complete: {len(root_causes)} root causes identified")
        return result

    def _group_by_field(self, findings: List[Dict[str, Any]], field: str) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for f in findings:
            value = f.get(field)
            if value:
                groups[value].append(f)
        return dict(groups)

    def _detect_cascades(
        self,
        findings: List[Dict[str, Any]],
        correlations: Dict[str, Any],
    ) -> List[RootCause]:
        """Detect likely cascading failures from cross-cutting correlations."""
        cascades: List[RootCause] = []
        cross_cutting = correlations.get("cross_cutting", {})
        hotspots = cross_cutting.get("hotspot_files", [])

        for i, hotspot in enumerate(hotspots):
            related = [f for f in findings if f.get("file_path") == hotspot]
            if len(related) >= 2:
                rc = RootCause(
                    cause_id=f"RC-CASCADE-{i:03d}",
                    description=f"Hotspot file {hotspot} has {len(related)} issues that may cascade.",
                    root_type="cascading_failure",
                )
                rc.finding_ids = [f["id"] for f in related]
                rc.affected_files.add(hotspot)
                rc.confidence = min(0.7, 0.2 + len(related) * 0.1)
                cascades.append(rc)

        return cascades

    def _find_hotspots(self, correlations: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify architectural hotspots from correlation data."""
        hotspots: List[Dict[str, Any]] = []

        cross_cutting = correlations.get("cross_cutting", {})
        for fp in cross_cutting.get("hotspot_files", []):
            hotspots.append({
                "file": fp,
                "type": "file_hotspot",
                "description": f"File {fp} has multiple high-severity findings.",
            })

        for ep in cross_cutting.get("multi_issue_endpoints", []):
            hotspots.append({
                "endpoint": ep,
                "type": "endpoint_hotspot",
                "description": f"Endpoint {ep} has multiple correlated findings.",
            })

        return hotspots
