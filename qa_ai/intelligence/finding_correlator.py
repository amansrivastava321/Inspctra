"""
finding_correlator.py - Correlates findings from all audit sources.
Groups findings by endpoint, database table, file, feature/workflow,
and risk category to identify patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.schemas.finding_schema import Finding, FindingSet, FindingSeverity, FindingCategory

logger = logging.getLogger(__name__)


class CorrelatedGroup:
    """A group of related findings sharing a common dimension."""

    def __init__(self, key: str, dimension: str):
        self.key = key
        self.dimension = dimension
        self.findings: List[Finding] = []

    def add(self, finding: Finding):
        self.findings.append(finding)

    @property
    def count(self) -> int:
        return len(self.findings)

    @property
    def max_severity(self) -> FindingSeverity:
        if not self.findings:
            return FindingSeverity.INFO
        severity_order = [
            FindingSeverity.CRITICAL, FindingSeverity.HIGH,
            FindingSeverity.MEDIUM, FindingSeverity.LOW, FindingSeverity.INFO,
        ]
        for sev in severity_order:
            if any(f.severity == sev for f in self.findings):
                return sev
        return FindingSeverity.INFO

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "dimension": self.dimension,
            "count": self.count,
            "max_severity": self.max_severity.value,
            "finding_ids": [f.id for f in self.findings],
            "finding_titles": [f.title for f in self.findings[:5]],
        }


class FindingCorrelator:
    """
    Ingests findings from all audit sources and correlates them by:
    - Endpoint
    - File
    - Database table
    - Feature/workflow
    - Risk category
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        api_audit: Optional[Dict[str, Any]] = None,
        database_audit: Optional[Dict[str, Any]] = None,
        sync_audit: Optional[Dict[str, Any]] = None,
        security_audit: Optional[Dict[str, Any]] = None,
        code_quality_audit: Optional[Dict[str, Any]] = None,
        execution_results: Optional[Dict[str, Any]] = None,
        app_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run finding correlation across all audit sources."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        # Ingest all findings
        all_findings: List[Finding] = []

        all_findings.extend(self._extract_from_audit(api_audit, "APIAuditAgent"))
        all_findings.extend(self._extract_from_audit(database_audit, "DatabaseAuditAgent"))
        all_findings.extend(self._extract_from_audit(sync_audit, "SyncAuditAgent"))
        all_findings.extend(self._extract_from_audit(security_audit, "SecurityAuditAgent"))
        all_findings.extend(self._extract_from_audit(code_quality_audit, "CodeQualityAuditAgent"))
        all_findings.extend(self._extract_from_execution(execution_results))

        # Correlate by different dimensions
        by_endpoint = self._correlate_by_endpoint(all_findings)
        by_file = self._correlate_by_file(all_findings)
        by_category = self._correlate_by_category(all_findings)
        by_workflow = self._correlate_by_workflow(all_findings, app_map)
        by_severity = self._correlate_by_severity(all_findings)

        # Build cross-cutting concerns
        cross_cutting = self._identify_cross_cutting(by_endpoint, by_file, by_category)

        duration = time.time() - start_time

        result = {
            "metadata": {
                "correlation_type": "finding_correlation",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "FindingCorrelator",
                "total_findings": len(all_findings),
            },
            "findings": [self._finding_to_dict(f) for f in all_findings],
            "correlations": {
                "by_endpoint": [g.to_dict() for g in by_endpoint if g.count > 1],
                "by_file": [g.to_dict() for g in by_file if g.count > 1],
                "by_category": [g.to_dict() for g in by_category if g.count > 0],
                "by_workflow": [g.to_dict() for g in by_workflow if g.count > 0],
                "by_severity": {sev.value: count for sev, count in by_severity.items()},
            },
            "cross_cutting": cross_cutting,
        }

        self.store.save_artifact("correlated_findings", result, agent="FindingCorrelator")
        logger.info(f"Finding correlation complete: {len(all_findings)} findings correlated")
        return result

    def _extract_from_audit(self, audit_result: Optional[Dict[str, Any]], source: str) -> List[Finding]:
        if not audit_result:
            return []

        findings: List[Finding] = []
        checks = audit_result.get("checks", [])

        for check in checks:
            if check.get("status") in ("failed", "warning"):
                severity_map = {
                    "critical": FindingSeverity.CRITICAL,
                    "high": FindingSeverity.HIGH,
                    "medium": FindingSeverity.MEDIUM,
                    "low": FindingSeverity.LOW,
                    "info": FindingSeverity.INFO,
                }
                sev = severity_map.get(check.get("severity", "medium"), FindingSeverity.MEDIUM)

                category_map = {
                    "secrets": FindingCategory.SECURITY,
                    "endpoint_auth": FindingCategory.SECURITY,
                    "authentication": FindingCategory.SECURITY,
                    "transport_security": FindingCategory.SECURITY,
                    "token_security": FindingCategory.SECURITY,
                    "file_size": FindingCategory.CODE_QUALITY,
                    "function_size": FindingCategory.CODE_QUALITY,
                    "class_size": FindingCategory.CODE_QUALITY,
                    "technical_debt": FindingCategory.CODE_QUALITY,
                    "error_handling": FindingCategory.CODE_QUALITY,
                    "duplication": FindingCategory.CODE_QUALITY,
                    "version_pinning": FindingCategory.COMPLIANCE,
                    "idempotency": FindingCategory.BUG,
                }
                cat = category_map.get(check.get("category", ""), FindingCategory.BUG)

                target = check.get("target", "")
                # Determine if target is an API endpoint (e.g., "GET /users", "DELETE /admin/users")
                api_endpoint = None
                file_path = target
                if target and any(target.startswith(m) for m in ("GET ", "POST ", "PUT ", "PATCH ", "DELETE ", "HEAD ", "OPTIONS ")):
                    api_endpoint = target
                    file_path = None

                findings.append(Finding(
                    id=check.get("check_id", ""),
                    title=check.get("title", ""),
                    description=check.get("description", ""),
                    severity=sev,
                    category=cat,
                    file_path=file_path,
                    api_endpoint=api_endpoint,
                    recommendation=check.get("recommendation", ""),
                    found_by_agent=source,
                    tags=[check.get("category", "")],
                    metadata={"source_audit": source, "target": target},
                ))

        return findings

    def _extract_from_execution(self, execution_result: Optional[Dict[str, Any]]) -> List[Finding]:
        if not execution_result:
            return []

        findings: List[Finding] = []
        suites = execution_result.get("suites", [])

        for suite in suites:
            for test in suite.get("tests", []):
                if test.get("outcome") in ("failed", "error"):
                    findings.append(Finding(
                        id=test.get("test_id", ""),
                        title=test.get("test_title", ""),
                        description=f"Test failed: {test.get('error_message', '')}",
                        severity=FindingSeverity.HIGH,
                        category=FindingCategory.BUG,
                        found_by_agent="ExecutionEngine",
                        tags=[test.get("test_type", "")],
                    ))

        return findings

    def _correlate_by_endpoint(self, findings: List[Finding]) -> List[CorrelatedGroup]:
        groups: Dict[str, CorrelatedGroup] = {}
        for f in findings:
            endpoint = f.api_endpoint or f.metadata.get("target", "")
            if endpoint:
                if endpoint not in groups:
                    groups[endpoint] = CorrelatedGroup(endpoint, "endpoint")
                groups[endpoint].add(f)
        return list(groups.values())

    def _correlate_by_file(self, findings: List[Finding]) -> List[CorrelatedGroup]:
        groups: Dict[str, CorrelatedGroup] = {}
        for f in findings:
            fp = f.file_path
            if fp:
                if fp not in groups:
                    groups[fp] = CorrelatedGroup(fp, "file")
                groups[fp].add(f)
        return list(groups.values())

    def _correlate_by_category(self, findings: List[Finding]) -> List[CorrelatedGroup]:
        groups: Dict[str, CorrelatedGroup] = {}
        for f in findings:
            cat = f.tags[0] if f.tags else (f.category if isinstance(f.category, str) else f.category.value)
            if cat not in groups:
                groups[cat] = CorrelatedGroup(cat, "category")
            groups[cat].add(f)
        return list(groups.values())

    def _correlate_by_workflow(self, findings: List[Finding], app_map: Optional[Dict[str, Any]]) -> List[CorrelatedGroup]:
        groups: Dict[str, CorrelatedGroup] = {}
        critical_flows = (app_map or {}).get("critical_flows", [])

        for flow in critical_flows:
            flow_name = flow.get("name", "")
            flow_steps = set(flow.get("steps", []))
            if not flow_name:
                continue

            group = CorrelatedGroup(flow_name, "workflow")
            for f in findings:
                combined = f"{f.title} {f.description} {f.api_endpoint or ''} {f.screen or ''}".lower()
                if any(step.lower() in combined for step in flow_steps):
                    group.add(f)
            if group.count > 0:
                groups[flow_name] = group

        return list(groups.values())

    def _correlate_by_severity(self, findings: List[Finding]) -> Dict[FindingSeverity, int]:
        counts: Dict[FindingSeverity, int] = {}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts

    def _identify_cross_cutting(
        self,
        by_endpoint: List[CorrelatedGroup],
        by_file: List[CorrelatedGroup],
        by_category: List[CorrelatedGroup],
    ) -> Dict[str, Any]:
        hotspots: List[str] = []
        for g in by_file:
            if g.count >= 3 and g.max_severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH):
                hotspots.append(g.key)

        multi_endpoint_files: List[str] = []
        for g in by_endpoint:
            if g.count >= 2:
                multi_endpoint_files.append(g.key)

        return {
            "hotspot_files": hotspots,
            "multi_issue_endpoints": multi_endpoint_files,
            "dominant_category": max(by_category, key=lambda g: g.count).key if by_category else None,
        }

    def _finding_to_dict(self, f: Finding) -> Dict[str, Any]:
        return {
            "id": f.id,
            "title": f.title,
            "description": f.description,
            "severity": f.severity.value,
            "category": f.tags[0] if f.tags else f.category.value,
            "file_path": f.file_path,
            "api_endpoint": f.api_endpoint,
            "recommendation": f.recommendation,
            "found_by_agent": f.found_by_agent,
            "tags": f.tags,
        }
