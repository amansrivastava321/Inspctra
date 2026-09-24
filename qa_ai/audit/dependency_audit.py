"""
dependency_audit.py - Dependency audit agent.
Parses requirements.txt, package.json, pubspec.yaml to identify
outdated/high-risk dependencies, security-sensitive packages, and
duplicate ecosystems.
"""

from __future__ import annotations

import re
import json
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

# Security-sensitive packages (Python)
PYTHON_SECURITY_PACKAGES = {
    "cryptography", "pycryptodome", "paramiko", "pyjwt", "jose",
    "authlib", "oauthlib", "passlib", "bcrypt", "hashlib",
    "requests", "httpx", "aiohttp", "urllib3",
    "django", "flask", "fastapi", "starlette",
    "sqlalchemy", "psycopg2", "pymongo", "redis",
    "celery", "pyyaml", "lxml", "jinja2", "markupsafe",
}

# Security-sensitive packages (Node)
NODE_SECURITY_PACKAGES = {
    "jsonwebtoken", "passport", "bcrypt", "express", "helmet",
    "cors", "csurf", "express-rate-limit",
    "sequelize", "mongoose", "prisma", "typeorm",
    "axios", "node-fetch", "got", "request",
    "dotenv", "config", "nconf",
    "lodash", "moment", "underscore",
}

# Unpinned version patterns
UNPINNED_PATTERN = re.compile(r'^([a-zA-Z][\w.-]*)\s*$')
PINNED_PATTERN = re.compile(r'^([a-zA-Z][\w.-]*)\s*==\s*(.+)$')
RANGE_PATTERN = re.compile(r'^([a-zA-Z][\w.-]*)\s*[><=!~]')


class DependencyAuditAgent:
    """
    Audits project dependencies for security and quality concerns.

    Generates checks for:
    - Unpinned dependency versions
    - Security-sensitive packages
    - Duplicate dependency ecosystems
    - High-risk dependencies heuristically
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_map: Optional[Dict[str, Any]] = None,
        dependency_files: Optional[Dict[str, str]] = None,
    ) -> AuditResult:
        """Run the dependency audit."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        checks: List[AuditCheck] = []

        if dependency_files:
            ecosystems_found: List[str] = []

            for filepath, content in dependency_files.items():
                if "requirements" in filepath and filepath.endswith(".txt"):
                    ecosystems_found.append("python")
                    checks.extend(self._audit_requirements_txt(filepath, content))
                elif filepath.endswith("package.json"):
                    ecosystems_found.append("node")
                    checks.extend(self._audit_package_json(filepath, content))
                elif filepath.endswith("pubspec.yaml"):
                    ecosystems_found.append("dart")
                    checks.extend(self._audit_pubspec(filepath, content))

            checks.extend(self._check_duplicate_ecosystems(ecosystems_found))

        # Tally
        passed = sum(1 for c in checks if c.status == AuditCheckStatus.PASSED)
        failed = sum(1 for c in checks if c.status == AuditCheckStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == AuditCheckStatus.WARNING)
        blocked = sum(1 for c in checks if c.status == AuditCheckStatus.BLOCKED)
        skipped = sum(1 for c in checks if c.status == AuditCheckStatus.SKIPPED)

        duration = time.time() - start_time

        result = AuditResult(
            metadata=AuditResultMetadata(
                audit_type="dependency_audit",
                app_name=app_map.get("metadata", {}).get("app_name", ""),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration,
                generated_by="DependencyAuditAgent",
            ),
            total_checks=len(checks),
            passed=passed,
            failed=failed,
            warnings=warnings,
            blocked=blocked,
            skipped=skipped,
            checks=checks,
            summary=self._build_summary(checks, dependency_files),
        )

        self.store.save_artifact("dependency_audit_results", result.model_dump(), agent="DependencyAuditAgent")
        logger.info(f"Dependency audit complete: {passed} passed, {failed} failed, {warnings} warnings")
        return result

    def _audit_requirements_txt(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]

        unpinned: List[str] = []
        security_pkgs: List[str] = []

        for line in lines:
            m_pin = PINNED_PATTERN.match(line)
            m_unpin = UNPINNED_PATTERN.match(line)
            m_range = RANGE_PATTERN.match(line)

            pkg_name = None
            if m_pin:
                pkg_name = m_pin.group(1).lower()
            elif m_unpin:
                pkg_name = m_unpin.group(1).lower()
                unpinned.append(m_unpin.group(1))
            elif m_range:
                pkg_name = m_range.group(1).lower()

            if pkg_name and pkg_name in PYTHON_SECURITY_PACKAGES:
                security_pkgs.append(pkg_name)

        if unpinned:
            checks.append(AuditCheck(
                check_id="DEP-UNPIN-001",
                title=f"Unpinned dependencies: {filepath}",
                description=f"Found {len(unpinned)} unpinned dependencies: {', '.join(unpinned[:5])}{'...' if len(unpinned) > 5 else ''}",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="version_pinning",
                target=filepath,
                expected="All dependencies pinned with ==",
                actual=f"{len(unpinned)} unpinned",
                recommendation="Pin all dependency versions for reproducible builds.",
            ))

        if security_pkgs:
            checks.append(AuditCheck(
                check_id="DEP-SEC-001",
                title=f"Security-sensitive packages: {filepath}",
                description=f"Found {len(security_pkgs)} security-sensitive packages: {', '.join(security_pkgs[:5])}",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="security_packages",
                target=filepath,
                expected="Security packages audited",
                actual=f"{len(security_pkgs)} security-sensitive packages",
                recommendation="Audit security-sensitive packages for known vulnerabilities.",
            ))

        return checks

    def _audit_package_json(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            checks.append(AuditCheck(
                check_id="DEP-JSON-001",
                title=f"Invalid JSON: {filepath}",
                description=f"Could not parse {filepath} as JSON.",
                status=AuditCheckStatus.FAILED,
                severity=AuditSeverity.HIGH,
                category="parse_error",
                target=filepath,
            ))
            return checks

        all_deps: Dict[str, str] = {}
        all_deps.update(data.get("dependencies", {}))
        all_deps.update(data.get("devDependencies", {}))

        unpinned: List[str] = []
        security_pkgs: List[str] = []

        for name, version in all_deps.items():
            if version in ("*", "latest", "x", "X"):
                unpinned.append(name)
            if name.lower() in NODE_SECURITY_PACKAGES:
                security_pkgs.append(name)

        if unpinned:
            checks.append(AuditCheck(
                check_id="DEP-UNPIN-002",
                title=f"Unpinned Node dependencies: {filepath}",
                description=f"Found {len(unpinned)} unpinned dependencies: {', '.join(unpinned[:5])}",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="version_pinning",
                target=filepath,
                expected="All dependencies have specific versions",
                actual=f"{len(unpinned)} unpinned",
                recommendation="Pin dependency versions.",
            ))

        if security_pkgs:
            checks.append(AuditCheck(
                check_id="DEP-SEC-002",
                title=f"Security-sensitive Node packages: {filepath}",
                description=f"Found {len(security_pkgs)} security-sensitive packages: {', '.join(security_pkgs[:5])}",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="security_packages",
                target=filepath,
                expected="Security packages audited",
                actual=f"{len(security_pkgs)} security-sensitive packages",
                recommendation="Audit security-sensitive packages for known vulnerabilities.",
            ))

        return checks

    def _audit_pubspec(self, filepath: str, content: str) -> List[AuditCheck]:
        """Basic pubspec.yaml audit (YAML parsing not required for heuristic check)."""
        checks: List[AuditCheck] = []
        lines = content.split('\n')

        has_any = False
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and ':' in stripped:
                has_any = True
                break

        if has_any:
            checks.append(AuditCheck(
                check_id="DEP-PUB-001",
                title=f"Flutter/Dart dependencies found: {filepath}",
                description=f"pubspec.yaml found with dependencies.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.LOW,
                category="ecosystem",
                target=filepath,
                recommendation="Run 'dart pub outdated' to check for outdated packages.",
            ))
        return checks

    def _check_duplicate_ecosystems(self, ecosystems: List[str]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        unique = set(ecosystems)
        if len(unique) > 1:
            checks.append(AuditCheck(
                check_id="DEP-ECO-001",
                title=f"Multiple dependency ecosystems: {', '.join(unique)}",
                description=f"Found {len(unique)} dependency ecosystems: {', '.join(unique)}.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.LOW,
                category="ecosystem",
                target=', '.join(unique),
                expected="Single primary ecosystem",
                actual=f"{len(unique)} ecosystems",
                recommendation="Verify this is intentional (e.g., monorepo).",
            ))
        return checks

    def _build_summary(self, checks: List[AuditCheck], dependency_files: Optional[Dict[str, str]]) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        for c in checks:
            by_category[c.category] = by_category.get(c.category, 0) + 1
        return {
            "total_checks": len(checks),
            "files_audited": len(dependency_files) if dependency_files else 0,
            "by_category": by_category,
            "has_unpinned": any(c.category == "version_pinning" for c in checks),
        }
