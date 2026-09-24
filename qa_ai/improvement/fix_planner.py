"""
fix_planner.py - Converts findings and root causes into safe fix plans.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
import time

from qa_ai.runtime.artifact_store import ArtifactStore


class FixPlanner:
    """Builds bounded fix plans without applying changes."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        findings: Optional[Dict[str, Any]] = None,
        root_causes: Optional[Dict[str, Any]] = None,
        risk_report: Optional[Dict[str, Any]] = None,
        test_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        findings = findings or self.store.load_artifact("correlated_findings") or self.store.load_artifact("findings") or {}
        root_causes = root_causes or self.store.load_artifact("root_cause_analysis") or {}
        risk_report = risk_report or self.store.load_artifact("overall_risk_report") or {}
        test_plan = test_plan or self.store.load_artifact("test_plan") or {}

        finding_list = self._findings(findings, risk_report)
        roots = root_causes.get("root_causes", []) if isinstance(root_causes, dict) else []
        fixes = self._plans_from_roots(roots, finding_list, test_plan)
        if not fixes:
            fixes = self._plans_from_findings(finding_list, test_plan)

        result = {
            "metadata": {
                "plan_type": "safe_fix_plan",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "FixPlanner",
            },
            "fixes": fixes,
            "summary": {
                "total_fixes": len(fixes),
                "low_risk": sum(1 for fix in fixes if fix["risk_level"] == "low"),
                "medium_risk": sum(1 for fix in fixes if fix["risk_level"] == "medium"),
                "high_risk": sum(1 for fix in fixes if fix["risk_level"] == "high"),
            },
        }
        self.store.save_artifact("fix_plan", result, agent="FixPlanner")
        return result

    def _plans_from_roots(
        self,
        roots: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        test_plan: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        plans = []
        by_id = {f.get("id"): f for f in findings}
        for index, root in enumerate(roots, start=1):
            linked = [by_id[fid] for fid in root.get("finding_ids", []) if fid in by_id]
            affected_files = sorted(set(root.get("affected_files", []) + [f.get("file_path", "") for f in linked if f.get("file_path")]))
            affected_apis = sorted(set(root.get("affected_endpoints", []) + [f.get("api_endpoint", "") for f in linked if f.get("api_endpoint")]))
            affected_functions = sorted({f.get("function", "") for f in linked if f.get("function")})
            risk_level = self._risk_level(linked, root)
            plans.append({
                "fix_id": f"FIX-{index:03d}",
                "source": "root_cause",
                "source_id": root.get("cause_id", f"root-{index}"),
                "title": self._title(root, linked),
                "description": root.get("description", "Address correlated findings safely."),
                "risk_level": risk_level,
                "confidence": round(float(root.get("confidence", 0.6)), 2),
                "affected_files": affected_files,
                "affected_functions": affected_functions,
                "affected_tests": [],
                "affected_workflows": sorted(root.get("affected_workflows", [])),
                "affected_apis": affected_apis,
                "finding_ids": root.get("finding_ids", []),
                "recommended_tests": self._recommended_tests(test_plan, linked, affected_apis),
                "safe_steps": self._safe_steps(risk_level),
                "requires_permission": True,
            })
        return plans

    def _plans_from_findings(self, findings: List[Dict[str, Any]], test_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        plans = []
        for index, finding in enumerate(findings, start=1):
            affected_api = [finding["api_endpoint"]] if finding.get("api_endpoint") else []
            plans.append({
                "fix_id": f"FIX-{index:03d}",
                "source": "finding",
                "source_id": finding.get("id", f"finding-{index}"),
                "title": f"Fix: {finding.get('title', 'Untitled finding')}",
                "description": finding.get("description", finding.get("title", "Address finding.")),
                "risk_level": self._risk_level([finding], {}),
                "confidence": float(finding.get("confidence", 0.55)),
                "affected_files": [finding["file_path"]] if finding.get("file_path") else [],
                "affected_functions": [finding["function"]] if finding.get("function") else [],
                "affected_tests": [],
                "affected_workflows": [finding["workflow"]] if finding.get("workflow") else [],
                "affected_apis": affected_api,
                "finding_ids": [finding.get("id", "")],
                "recommended_tests": self._recommended_tests(test_plan, [finding], affected_api),
                "safe_steps": self._safe_steps(self._risk_level([finding], {})),
                "requires_permission": True,
            })
        return plans

    def _findings(self, findings: Dict[str, Any], risk_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates = []
        if isinstance(findings, dict):
            candidates.extend(findings.get("findings", []))
        if not candidates and isinstance(risk_report, dict):
            candidates.extend(risk_report.get("findings", []))
        return [item for item in candidates if isinstance(item, dict)]

    def _risk_level(self, findings: List[Dict[str, Any]], root: Dict[str, Any]) -> str:
        severities = {str(f.get("severity", "medium")).lower() for f in findings}
        if "critical" in severities or "high" in severities:
            return "high"
        if "medium" in severities or len(root.get("affected_files", [])) > 1 or root.get("root_type") in {"category_cluster", "cascading_failure"}:
            return "medium"
        return "low"

    def _recommended_tests(
        self,
        test_plan: Dict[str, Any],
        findings: List[Dict[str, Any]],
        affected_apis: Iterable[str],
    ) -> List[str]:
        text_tokens = " ".join(
            list(affected_apis)
            + [str(f.get("title", "")) for f in findings]
            + [str(f.get("category", "")) for f in findings]
        ).lower()
        recommended = []
        for test in self._flatten_tests(test_plan):
            haystack = f"{test.get('id', '')} {test.get('title', '')} {test.get('type', '')} {' '.join(map(str, test.get('steps', [])))}".lower()
            if test.get("id") and any(token and token in haystack for token in text_tokens.split()):
                recommended.append(test["id"])
        return sorted(dict.fromkeys(recommended))

    def _flatten_tests(self, test_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        suites = test_plan.get("test_suites", {}) if isinstance(test_plan, dict) else {}
        tests = []
        for suite_tests in suites.values():
            if isinstance(suite_tests, list):
                tests.extend(item for item in suite_tests if isinstance(item, dict))
        return tests

    def _safe_steps(self, risk_level: str) -> List[str]:
        steps = [
            "Create a minimal patch limited to affected files.",
            "Run targeted retests selected from the fix plan.",
            "Run regression guard before accepting the change.",
        ]
        if risk_level == "high":
            steps.insert(1, "Require human review before applying remediation.")
        return steps

    def _title(self, root: Dict[str, Any], linked: List[Dict[str, Any]]) -> str:
        if linked:
            return f"Resolve root cause for {linked[0].get('title', 'linked findings')}"
        return f"Resolve {root.get('root_type', 'root cause')}"
