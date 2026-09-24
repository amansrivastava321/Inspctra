"""
detection_metrics.py - Detection quality metrics for benchmark runs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set


class DetectionMetrics:
    """Computes issue coverage, false positives, duplicates, and evidence metrics."""

    def run(self, benchmark_summary: Dict[str, Any] | None) -> Dict[str, Any]:
        payload = benchmark_summary if isinstance(benchmark_summary, dict) else {}
        apps = payload.get("apps", [])
        if not isinstance(apps, list):
            apps = []

        per_app: List[Dict[str, Any]] = []
        totals = {
            "expected_issues": 0,
            "matched_issues": 0,
            "findings": 0,
            "false_positives": 0,
            "duplicate_findings": 0,
            "runtime_verified": 0,
            "runtime_total": 0,
            "evidence_with_links": 0,
            "evidence_total_findings": 0,
        }

        for app in apps:
            if not isinstance(app, dict):
                continue
            app_metrics = self._metrics_for_app(app)
            per_app.append(app_metrics)
            totals["expected_issues"] += app_metrics["expected_issues"]
            totals["matched_issues"] += app_metrics["matched_issues"]
            totals["findings"] += app_metrics["findings_count"]
            totals["false_positives"] += app_metrics["false_positives"]
            totals["duplicate_findings"] += app_metrics["duplicate_findings"]
            totals["runtime_verified"] += app_metrics["runtime_verified"]
            totals["runtime_total"] += app_metrics["runtime_total"]
            totals["evidence_with_links"] += app_metrics["evidence_with_links"]
            totals["evidence_total_findings"] += app_metrics["evidence_total_findings"]

        issue_coverage = self._ratio(totals["matched_issues"], totals["expected_issues"])
        runtime_verification_rate = self._ratio(totals["runtime_verified"], totals["runtime_total"])
        evidence_completeness = self._ratio(totals["evidence_with_links"], totals["evidence_total_findings"])
        false_positive_rate = self._ratio(totals["false_positives"], totals["findings"])
        duplicate_rate = self._ratio(totals["duplicate_findings"], totals["findings"])

        return {
            "metrics": {
                "issue_coverage": issue_coverage,
                "false_positives": totals["false_positives"],
                "false_positive_rate": false_positive_rate,
                "duplicate_findings": totals["duplicate_findings"],
                "duplicate_finding_rate": duplicate_rate,
                "runtime_verification_rate": runtime_verification_rate,
                "evidence_completeness": evidence_completeness,
                "apps_evaluated": len(per_app),
            },
            "per_app": per_app,
        }

    def _metrics_for_app(self, app: Dict[str, Any]) -> Dict[str, Any]:
        findings = app.get("findings", [])
        if not isinstance(findings, list):
            findings = []
        findings = [item for item in findings if isinstance(item, dict)]

        expected = app.get("expected_issues", [])
        if not isinstance(expected, list):
            expected = []
        expected = [item for item in expected if isinstance(item, dict)]

        matched_issue_ids = self._matched_issues(expected, findings)
        matched_finding_indices = self._matched_finding_indices(expected, findings)
        duplicate_findings = self._duplicate_count(findings)
        false_positives = max(0, len(findings) - len(matched_finding_indices))

        runtime_summary = app.get("runtime_validation_summary", {})
        if not isinstance(runtime_summary, dict):
            runtime_summary = {}
        runtime_verified = self._safe_int(runtime_summary.get("verified")) + self._safe_int(
            runtime_summary.get("partially_verified")
        )
        runtime_total = sum(self._safe_int(v) for v in runtime_summary.values())
        if runtime_total == 0:
            runtime_total = len(findings)

        evidence_with_links = min(len(findings), self._safe_int((app.get("evidence_summary") or {}).get("evidence_nodes")))
        evidence_total = len(findings)

        return {
            "app_name": app.get("app_name", "unknown"),
            "expected_issues": len(expected),
            "matched_issues": len(matched_issue_ids),
            "issue_coverage": self._ratio(len(matched_issue_ids), len(expected)),
            "findings_count": len(findings),
            "false_positives": false_positives,
            "duplicate_findings": duplicate_findings,
            "runtime_verified": runtime_verified,
            "runtime_total": runtime_total,
            "runtime_verification_rate": self._ratio(runtime_verified, runtime_total),
            "evidence_with_links": evidence_with_links,
            "evidence_total_findings": evidence_total,
            "evidence_completeness": self._ratio(evidence_with_links, evidence_total),
        }

    def _matched_issues(self, expected: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> Set[str]:
        matched: Set[str] = set()
        for issue in expected:
            issue_id = str(issue.get("issue_id", "")).strip()
            keywords = issue.get("keywords", [])
            if not issue_id or not isinstance(keywords, list):
                continue
            needle = [str(item).lower() for item in keywords if str(item).strip()]
            if not needle:
                continue
            for finding in findings:
                hay = self._finding_text(finding)
                if any(keyword in hay for keyword in needle):
                    matched.add(issue_id)
                    break
        return matched

    def _matched_finding_indices(self, expected: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> Set[int]:
        keywords: List[str] = []
        for issue in expected:
            raw = issue.get("keywords", [])
            if isinstance(raw, list):
                keywords.extend(str(item).lower() for item in raw if str(item).strip())
        matched: Set[int] = set()
        if not keywords:
            return matched
        for idx, finding in enumerate(findings):
            hay = self._finding_text(finding)
            if any(keyword in hay for keyword in keywords):
                matched.add(idx)
        return matched

    def _finding_text(self, finding: Dict[str, Any]) -> str:
        parts = [
            finding.get("id", ""),
            finding.get("title", ""),
            finding.get("description", ""),
            finding.get("severity", ""),
            finding.get("category", ""),
            finding.get("target", ""),
            finding.get("api_endpoint", ""),
            " ".join([str(tag) for tag in finding.get("tags", [])]) if isinstance(finding.get("tags"), list) else "",
        ]
        return " ".join(str(part).lower() for part in parts if part is not None)

    def _duplicate_count(self, findings: List[Dict[str, Any]]) -> int:
        seen: Set[str] = set()
        duplicates = 0
        for finding in findings:
            key = "|".join(
                [
                    str(finding.get("title", "")).strip().lower(),
                    str(finding.get("category", "")).strip().lower(),
                    str(finding.get("target", finding.get("file_path", ""))).strip().lower(),
                ]
            )
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
        return duplicates

    def _ratio(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(float(numerator) / float(denominator), 4)

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
