"""
api_audit.py - API security and correctness audit agent.
Discovers API endpoints from app_map, generates audit checks for
missing auth, invalid tokens, wrong roles, payload validation,
idempotency risks, and unsafe methods.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.schemas.audit_result_schema import (
    AuditResult,
    AuditCheck,
    AuditCheckStatus,
    AuditSeverity,
    AuditResultMetadata,
)

logger = logging.getLogger(__name__)

# Unsafe HTTP methods that mutate state
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Large payload threshold (bytes)
LARGE_PAYLOAD_THRESHOLD = 1_048_576  # 1 MB


class APIAuditAgent:
    """
    Audits API endpoints discovered from the app_map.

    Generates checks for:
    - Missing authentication on sensitive endpoints
    - Invalid/expired token handling
    - Role-based access control gaps
    - Missing required fields
    - Invalid payload validation
    - Large payload risks
    - Idempotency concerns
    - Expected status code validation
    - Unsafe HTTP methods without safeguards
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_map: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None,
        credentials: Optional[Dict[str, str]] = None,
    ) -> AuditResult:
        """
        Run the API audit.

        Args:
            app_map: Application map from Discovery phase. If None, attempts to load from store.
            base_url: Base URL for the API. If None, checks requiring execution are blocked.
            credentials: Dict of credential name -> value.

        Returns:
            AuditResult with all checks.
        """
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        checks: List[AuditCheck] = []
        endpoints = app_map.get("api_endpoints", [])
        security_surfaces = app_map.get("security_surfaces", {})

        # Generate checks for each endpoint
        for i, endpoint in enumerate(endpoints):
            ep_checks = self._audit_endpoint(endpoint, i, base_url, credentials)
            checks.extend(ep_checks)

        # Generate cross-cutting checks
        checks.extend(self._audit_unauthenticated_exposure(endpoints, security_surfaces))
        checks.extend(self._audit_idempotency_risks(endpoints))
        checks.extend(self._audit_unsafe_methods(endpoints))

        # Tally results
        passed = sum(1 for c in checks if c.status == AuditCheckStatus.PASSED)
        failed = sum(1 for c in checks if c.status == AuditCheckStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == AuditCheckStatus.WARNING)
        blocked = sum(1 for c in checks if c.status == AuditCheckStatus.BLOCKED)
        skipped = sum(1 for c in checks if c.status == AuditCheckStatus.SKIPPED)

        duration = time.time() - start_time

        result = AuditResult(
            metadata=AuditResultMetadata(
                audit_type="api_audit",
                app_name=app_map.get("metadata", {}).get("app_name", ""),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration,
                generated_by="APIAuditAgent",
            ),
            total_checks=len(checks),
            passed=passed,
            failed=failed,
            warnings=warnings,
            blocked=blocked,
            skipped=skipped,
            checks=checks,
            summary=self._build_summary(checks, endpoints),
        )

        # Persist artifacts
        self.store.save_artifact("api_audit_results", result.model_dump(), agent="APIAuditAgent")
        self._save_audit_plan(checks, app_map)

        logger.info(
            f"API audit complete: {passed} passed, {failed} failed, "
            f"{warnings} warnings, {blocked} blocked out of {len(checks)} checks"
        )

        return result

    def _audit_endpoint(
        self,
        endpoint: Dict[str, Any],
        index: int,
        base_url: Optional[str],
        credentials: Optional[Dict[str, str]],
    ) -> List[AuditCheck]:
        """Generate audit checks for a single endpoint."""
        checks: List[AuditCheck] = []
        method = endpoint.get("method", "UNKNOWN") or "UNKNOWN"
        path = endpoint.get("path", "")
        auth_required = endpoint.get("auth_required")
        risk = endpoint.get("risk", {})
        risk_level = risk.get("risk_level", "low") if risk else "low"
        ep_label = f"{method} {path}"

        # 1. Missing auth on sensitive endpoints
        if auth_required is False and risk_level in ("high", "critical"):
            checks.append(AuditCheck(
                check_id=f"API-AUTH-{index:03d}",
                title=f"Missing auth on high-risk endpoint: {ep_label}",
                description=f"Endpoint {ep_label} is marked as {risk_level} risk but does not require authentication.",
                status=AuditCheckStatus.FAILED,
                severity=AuditSeverity.HIGH,
                category="authentication",
                target=ep_label,
                expected="Authentication required",
                actual="No authentication required",
                recommendation="Add authentication middleware to this endpoint.",
            ))
        elif auth_required is False:
            checks.append(AuditCheck(
                check_id=f"API-AUTH-{index:03d}",
                title=f"Public endpoint: {ep_label}",
                description=f"Endpoint {ep_label} does not require authentication.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.LOW,
                category="authentication",
                target=ep_label,
                expected="Auth requirement verified",
                actual="No auth required (public endpoint)",
                recommendation="Verify this endpoint intentionally exposes no sensitive data.",
            ))

        # 2. Missing auth field (unknown auth status)
        if auth_required is None:
            checks.append(AuditCheck(
                check_id=f"API-UNK-{index:03d}",
                title=f"Unknown auth requirement: {ep_label}",
                description=f"Endpoint {ep_label} has no auth_required field in app_map.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="authentication",
                target=ep_label,
                recommendation="Determine and document whether this endpoint requires authentication.",
            ))

        # 3. Token validation check (requires execution)
        if base_url:
            checks.append(self._check_token_validation(ep_label, base_url, index))
        else:
            checks.append(AuditCheck(
                check_id=f"API-TKN-{index:03d}",
                title=f"Token validation: {ep_label}",
                description="Cannot verify token handling without a base URL.",
                status=AuditCheckStatus.BLOCKED,
                severity=AuditSeverity.MEDIUM,
                category="authentication",
                target=ep_label,
                blocked_reason="No base_url provided. Supply a running API URL to execute this check.",
            ))

        # 4. Role-based access control
        if auth_required and risk and risk.get("admin_operation"):
            if base_url:
                checks.append(self._check_role_bypass(ep_label, base_url, index))
            else:
                checks.append(AuditCheck(
                    check_id=f"API-ROLE-{index:03d}",
                    title=f"Role bypass check: {ep_label}",
                    description="Admin endpoint requires role verification.",
                    status=AuditCheckStatus.BLOCKED,
                    severity=AuditSeverity.HIGH,
                    category="authorization",
                    target=ep_label,
                    blocked_reason="No base_url provided. Supply a running API URL to execute this check.",
                ))

        # 5. Required fields / payload validation
        if method in ("POST", "PUT", "PATCH"):
            checks.append(self._check_payload_validation(ep_label, endpoint, index))

        # 6. Large payload risk
        if method in ("POST", "PUT", "PATCH"):
            checks.append(self._check_large_payload(ep_label, index))

        return checks

    def _check_token_validation(
        self, ep_label: str, base_url: str, index: int
    ) -> AuditCheck:
        """Check if endpoint properly rejects invalid tokens."""
        # Static analysis: we cannot execute HTTP calls here.
        # Mark as a check that could be executed by the runner.
        return AuditCheck(
            check_id=f"API-TKN-{index:03d}",
            title=f"Token validation: {ep_label}",
            description=f"Verify that {ep_label} rejects invalid/expired tokens with 401.",
            status=AuditCheckStatus.SKIPPED,
            severity=AuditSeverity.HIGH,
            category="authentication",
            target=ep_label,
            expected="401 Unauthorized on invalid token",
            recommendation="Run with APIRunner to validate token rejection behavior.",
        )

    def _check_role_bypass(
        self, ep_label: str, base_url: str, index: int
    ) -> AuditCheck:
        """Check if admin endpoint rejects non-admin users."""
        return AuditCheck(
            check_id=f"API-ROLE-{index:03d}",
            title=f"Role bypass check: {ep_label}",
            description=f"Verify that {ep_label} rejects requests from non-admin users with 403.",
            status=AuditCheckStatus.SKIPPED,
            severity=AuditSeverity.HIGH,
            category="authorization",
            target=ep_label,
            expected="403 Forbidden for non-admin users",
            recommendation="Run with APIRunner using non-admin credentials.",
        )

    def _check_payload_validation(
        self, ep_label: str, endpoint: Dict[str, Any], index: int
    ) -> AuditCheck:
        """Check if endpoint validates request payloads."""
        has_request_body = endpoint.get("request_body") is not None
        if has_request_body:
            return AuditCheck(
                check_id=f"API-PAY-{index:03d}",
                title=f"Payload validation: {ep_label}",
                description=f"Endpoint {ep_label} accepts a request body. Verify it validates required fields.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="validation",
                target=ep_label,
                expected="422 Unprocessable Entity on missing required fields",
                recommendation="Test with empty body and missing required fields.",
            )
        return AuditCheck(
            check_id=f"API-PAY-{index:03d}",
            title=f"Payload schema: {ep_label}",
            description=f"No request body schema found for {ep_label}.",
            status=AuditCheckStatus.WARNING,
            severity=AuditSeverity.LOW,
            category="validation",
            target=ep_label,
            recommendation="Document expected request body schema.",
        )

    def _check_large_payload(self, ep_label: str, index: int) -> AuditCheck:
        """Check if endpoint handles large payloads safely."""
        return AuditCheck(
            check_id=f"API-SIZE-{index:03d}",
            title=f"Large payload handling: {ep_label}",
            description=f"Verify that {ep_label} rejects payloads larger than {LARGE_PAYLOAD_THRESHOLD} bytes.",
            status=AuditCheckStatus.SKIPPED,
            severity=AuditSeverity.MEDIUM,
            category="validation",
            target=ep_label,
            expected="413 Payload Too Large or 400 Bad Request",
            recommendation="Send a payload exceeding the size limit and verify rejection.",
        )

    def _audit_unauthenticated_exposure(
        self,
        endpoints: List[Dict[str, Any]],
        security_surfaces: Dict[str, Any],
    ) -> List[AuditCheck]:
        """Check for endpoints that expose data without authentication."""
        checks: List[AuditCheck] = []
        public_endpoints = security_surfaces.get("public_endpoints", [])

        if public_endpoints:
            ep_labels = []
            for ep in public_endpoints:
                method = ep.get("method", "UNKNOWN") or "UNKNOWN"
                path = ep.get("path", "")
                ep_labels.append(f"{method} {path}")

            checks.append(AuditCheck(
                check_id="API-EXPOSE-001",
                title=f"Public endpoint exposure: {len(public_endpoints)} endpoints",
                description=f"Found {len(public_endpoints)} public endpoints: {', '.join(ep_labels[:5])}{'...' if len(ep_labels) > 5 else ''}",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="data_exposure",
                target=", ".join(ep_labels[:10]),
                recommendation="Verify none of these endpoints expose PII or sensitive data.",
            ))

        return checks

    def _audit_idempotency_risks(
        self, endpoints: List[Dict[str, Any]]
    ) -> List[AuditCheck]:
        """Check for mutation endpoints that may lack idempotency."""
        checks: List[AuditCheck] = []
        mutation_endpoints = [
            ep for ep in endpoints
            if (ep.get("method") or "").upper() in ("POST", "PUT")
        ]

        for i, ep in enumerate(mutation_endpoints):
            method = ep.get("method", "UNKNOWN") or "UNKNOWN"
            path = ep.get("path", "")
            ep_label = f"{method} {path}"

            checks.append(AuditCheck(
                check_id=f"API-IDEM-{i:03d}",
                title=f"Idempotency risk: {ep_label}",
                description=f"Mutation endpoint {ep_label} may not handle duplicate requests safely.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="idempotency",
                target=ep_label,
                recommendation="Verify idempotency keys or deduplication logic is in place.",
            ))

        return checks

    def _audit_unsafe_methods(
        self, endpoints: List[Dict[str, Any]]
    ) -> List[AuditCheck]:
        """Flag endpoints using unsafe HTTP methods."""
        checks: List[AuditCheck] = []
        unsafe_eps = [
            ep for ep in endpoints
            if (ep.get("method") or "").upper() in UNSAFE_METHODS
        ]

        for i, ep in enumerate(unsafe_eps):
            method = ep.get("method", "UNKNOWN") or "UNKNOWN"
            path = ep.get("path", "")
            ep_label = f"{method} {path}"
            risk = ep.get("risk", {})
            risk_level = risk.get("risk_level", "low") if risk else "low"

            severity = AuditSeverity.LOW
            if risk_level in ("critical", "high"):
                severity = AuditSeverity.MEDIUM

            checks.append(AuditCheck(
                check_id=f"API-UNSAFE-{i:03d}",
                title=f"Unsafe method: {ep_label}",
                description=f"Endpoint {ep_label} uses {method}, which mutates data.",
                status=AuditCheckStatus.WARNING,
                severity=severity,
                category="method_safety",
                target=ep_label,
                recommendation="Verify proper input validation, error handling, and audit logging.",
            ))

        return checks

    def _save_audit_plan(
        self, checks: List[AuditCheck], app_map: Dict[str, Any]
    ) -> None:
        """Save the audit plan (what checks will be run)."""
        plan = {
            "metadata": {
                "audit_type": "api_audit",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generated_by": "APIAuditAgent",
                "total_checks": len(checks),
            },
            "checks": [
                {
                    "check_id": c.check_id,
                    "title": c.title,
                    "category": c.category,
                    "severity": c.severity.value,
                    "target": c.target,
                }
                for c in checks
            ],
        }
        self.store.save_artifact("api_audit_plan", plan, agent="APIAuditAgent")

    def _build_summary(
        self,
        checks: List[AuditCheck],
        endpoints: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build a summary of audit results."""
        by_category: Dict[str, Dict[str, int]] = {}
        for c in checks:
            if c.category not in by_category:
                by_category[c.category] = {"passed": 0, "failed": 0, "warning": 0, "blocked": 0, "skipped": 0}
            by_category[c.category][c.status.value] = by_category[c.category].get(c.status.value, 0) + 1

        return {
            "endpoints_audited": len(endpoints),
            "by_category": by_category,
            "has_auth_gaps": any(
                c.status == AuditCheckStatus.FAILED and c.category == "authentication"
                for c in checks
            ),
            "has_validation_gaps": any(
                c.status == AuditCheckStatus.FAILED and c.category == "validation"
                for c in checks
            ),
        }
