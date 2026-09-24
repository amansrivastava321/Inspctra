"""
security_audit.py - Security audit agent.
Detects hardcoded secrets, unsafe auth patterns, insecure HTTP usage,
exposed admin/debug routes, weak token handling, and unsafe local storage.
"""

from __future__ import annotations

import re
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

# ─── Patterns ──────────────────────────────────────────

SECRET_PATTERNS = [
    (r'(?:api[_-]?key|apikey)\s*[:=]\s*["\'][^"\']{8,}["\']', "API key"),
    (r'(?:secret|secret[_-]?key)\s*[:=]\s*["\'][^"\']{8,}["\']', "Secret key"),
    (r'(?:password|passwd|pwd)\s*[:=]\s*["\'][^"\']{4,}["\']', "Password"),
    (r'(?:token|auth[_-]?token|access[_-]?token)\s*[:=]\s*["\'][^"\']{8,}["\']', "Token"),
    (r'(?:private[_-]?key)\s*[:=]\s*["\'][^"\']{8,}["\']', "Private key"),
    (r'(?:aws[_-]?secret|aws[_-]?access)', "AWS credential"),
    (r'(?:database[_-]?url|db[_-]?url|connection[_-]?string)\s*[:=]\s*["\']', "Database URL"),
    (r'sk-[a-zA-Z0-9]{20,}', "OpenAI-style API key"),
    (r'ghp_[a-zA-Z0-9]{36}', "GitHub personal access token"),
    (r'xox[bps]-[a-zA-Z0-9-]+', "Slack token"),
]

INSECURE_URL_PATTERN = r'http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|::1)'

ADMIN_ROUTE_PATTERNS = [
    r'/(?:admin|debug|management|internal|swagger|openapi|graphql)',
    r'/(?:__debug__|_debug|debugger)',
    r'/(?:phpmyadmin|adminer|pgadmin)',
]

DEBUG_FLAG_PATTERNS = [
    (r'DEBUG\s*=\s*True', "Debug mode enabled"),
    (r'DEBUG_MODE\s*=\s*(?:true|1|yes)', "Debug mode flag"),
    (r'FLASK_DEBUG\s*=\s*1', "Flask debug mode"),
    (r'NODE_ENV\s*[:=]\s*["\']development["\']', "Node development mode"),
    (r'LOG_LEVEL\s*[:=]\s*["\']DEBUG["\']', "Debug log level"),
]

LOCAL_STORAGE_PATTERNS = [
    (r'localStorage\.(?:setItem|getItem)', "Browser localStorage usage"),
    (r'sessionStorage\.(?:setItem|getItem)', "Browser sessionStorage usage"),
    (r'SecureStore|AsyncStorage', "Mobile local storage"),
]

WEAK_TOKEN_PATTERNS = [
    (r'(?:jwt|token).*expires.*(?:365|30\.24|year)', "Very long token expiry"),
    (r'verify\s*=\s*False', "SSL verification disabled"),
    (r'check_hostname\s*=\s*False', "Hostname verification disabled"),
    (r'CORS.*allow[_-]?(?:all|origin)\s*=\s*(?:True|\*)', "CORS allows all origins"),
]


class SecurityAuditAgent:
    """
    Audits codebase for security concerns via static analysis.

    Generates checks for:
    - Hardcoded secrets (API keys, passwords, tokens)
    - Unsafe authentication patterns
    - Missing auth on dangerous endpoints
    - Unsafe local storage usage
    - Insecure HTTP usage
    - Exposed admin/debug routes
    - Weak token handling
    - RLS/auth bypass risks
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_map: Optional[Dict[str, Any]] = None,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> AuditResult:
        """Run the security audit."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        checks: List[AuditCheck] = []

        # Scan file contents for security issues
        if file_contents:
            for filepath, content in file_contents.items():
                checks.extend(self._check_hardcoded_secrets(filepath, content))
                checks.extend(self._check_insecure_urls(filepath, content))
                checks.extend(self._check_admin_routes(filepath, content))
                checks.extend(self._check_debug_flags(filepath, content))
                checks.extend(self._check_local_storage(filepath, content))
                checks.extend(self._check_weak_token_handling(filepath, content))

        # Check app_map for missing auth on dangerous endpoints
        checks.extend(self._check_endpoint_auth(app_map))

        # Tally
        passed = sum(1 for c in checks if c.status == AuditCheckStatus.PASSED)
        failed = sum(1 for c in checks if c.status == AuditCheckStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == AuditCheckStatus.WARNING)
        blocked = sum(1 for c in checks if c.status == AuditCheckStatus.BLOCKED)
        skipped = sum(1 for c in checks if c.status == AuditCheckStatus.SKIPPED)

        duration = time.time() - start_time

        result = AuditResult(
            metadata=AuditResultMetadata(
                audit_type="security_audit",
                app_name=app_map.get("metadata", {}).get("app_name", ""),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration,
                generated_by="SecurityAuditAgent",
            ),
            total_checks=len(checks),
            passed=passed,
            failed=failed,
            warnings=warnings,
            blocked=blocked,
            skipped=skipped,
            checks=checks,
            summary=self._build_summary(checks),
        )

        self.store.save_artifact("security_audit_results", result.model_dump(), agent="SecurityAuditAgent")
        logger.info(f"Security audit complete: {passed} passed, {failed} failed, {warnings} warnings")
        return result

    def _check_hardcoded_secrets(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        for i, (pattern, label) in enumerate(SECRET_PATTERNS):
            if re.search(pattern, content, re.IGNORECASE):
                checks.append(AuditCheck(
                    check_id=f"SEC-SECRET-{i:03d}",
                    title=f"Possible hardcoded {label.lower()}: {filepath}",
                    description=f"Found pattern matching {label} in {filepath}.",
                    status=AuditCheckStatus.FAILED,
                    severity=AuditSeverity.CRITICAL,
                    category="secrets",
                    target=filepath,
                    expected="No hardcoded secrets",
                    actual=f"Found {label} pattern",
                    recommendation=f"Move {label.lower()} to environment variables or a secrets manager.",
                ))
        return checks

    def _check_insecure_urls(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        matches = re.findall(INSECURE_URL_PATTERN, content)
        if matches:
            checks.append(AuditCheck(
                check_id=f"SEC-HTTP-{hash(filepath) % 10000:04d}",
                title=f"Insecure HTTP URL: {filepath}",
                description=f"Found {len(matches)} insecure HTTP URL(s) in {filepath} (non-localhost).",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="transport_security",
                target=filepath,
                expected="HTTPS for all non-localhost URLs",
                actual=f"{len(matches)} HTTP URLs found",
                recommendation="Use HTTPS for all external URLs.",
            ))
        return checks

    def _check_admin_routes(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        for i, pattern in enumerate(ADMIN_ROUTE_PATTERNS):
            if re.search(pattern, content, re.IGNORECASE):
                checks.append(AuditCheck(
                    check_id=f"SEC-ADM-{i:03d}",
                    title=f"Admin/debug route exposed: {filepath}",
                    description=f"Found admin/debug route pattern in {filepath}.",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.HIGH,
                    category="exposed_routes",
                    target=filepath,
                    expected="Admin routes behind auth",
                    actual="Admin route pattern found in code",
                    recommendation="Ensure admin routes require authentication and are not publicly accessible.",
                ))
        return checks

    def _check_debug_flags(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        for i, (pattern, label) in enumerate(DEBUG_FLAG_PATTERNS):
            if re.search(pattern, content, re.IGNORECASE):
                checks.append(AuditCheck(
                    check_id=f"SEC-DBG-{i:03d}",
                    title=f"Debug flag: {filepath}",
                    description=f"{label} found in {filepath}.",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.MEDIUM,
                    category="debug_flags",
                    target=filepath,
                    expected="Debug flags disabled in production",
                    actual=f"{label} detected",
                    recommendation=f"Disable {label.lower()} for production builds.",
                ))
        return checks

    def _check_local_storage(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        for i, (pattern, label) in enumerate(LOCAL_STORAGE_PATTERNS):
            if re.search(pattern, content):
                checks.append(AuditCheck(
                    check_id=f"SEC-STORE-{i:03d}",
                    title=f"Local storage usage: {filepath}",
                    description=f"{label} found in {filepath}.",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.MEDIUM,
                    category="data_storage",
                    target=filepath,
                    expected="Sensitive data not stored locally",
                    actual=f"{label} detected",
                    recommendation="Verify no sensitive data is stored in local storage.",
                ))
        return checks

    def _check_weak_token_handling(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        for i, (pattern, label) in enumerate(WEAK_TOKEN_PATTERNS):
            if re.search(pattern, content, re.IGNORECASE):
                checks.append(AuditCheck(
                    check_id=f"SEC-TOKEN-{i:03d}",
                    title=f"Weak token handling: {filepath}",
                    description=f"{label} found in {filepath}.",
                    status=AuditCheckStatus.FAILED,
                    severity=AuditSeverity.HIGH,
                    category="token_security",
                    target=filepath,
                    expected="Strong token/security configuration",
                    actual=f"{label} detected",
                    recommendation=f"Fix: {label}. Use secure defaults.",
                ))
        return checks

    def _check_endpoint_auth(self, app_map: Dict[str, Any]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        endpoints = app_map.get("api_endpoints", [])

        dangerous_methods = {"POST", "PUT", "PATCH", "DELETE"}
        for i, ep in enumerate(endpoints):
            method = (ep.get("method") or "GET").upper()
            path = ep.get("path", "")
            auth_required = ep.get("auth_required")

            if method in dangerous_methods and auth_required is False:
                checks.append(AuditCheck(
                    check_id=f"SEC-EP-{i:03d}",
                    title=f"Unauthenticated dangerous endpoint: {method} {path}",
                    description=f"Mutation endpoint {method} {path} does not require authentication.",
                    status=AuditCheckStatus.FAILED,
                    severity=AuditSeverity.CRITICAL,
                    category="endpoint_auth",
                    target=f"{method} {path}",
                    expected="Authentication required for mutation endpoints",
                    actual="auth_required=False",
                    recommendation="Add authentication to this endpoint.",
                ))
        return checks

    def _build_summary(self, checks: List[AuditCheck]) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        for c in checks:
            by_category[c.category] = by_category.get(c.category, 0) + 1
        return {
            "total_checks": len(checks),
            "by_category": by_category,
            "has_critical_secrets": any(
                c.status == AuditCheckStatus.FAILED and c.category == "secrets"
                for c in checks
            ),
            "has_auth_gaps": any(
                c.status == AuditCheckStatus.FAILED and c.category == "endpoint_auth"
                for c in checks
            ),
        }
