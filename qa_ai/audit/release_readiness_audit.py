"""
release_readiness_audit.py - Release readiness audit agent.
Detects missing environment configs, debug flags in production,
missing signing/build configs, CI/release workflows, monitoring,
and backup/recovery indicators.
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

# Config file patterns
ENV_FILE_PATTERNS = [
    ".env", ".env.example", ".env.local", ".env.production",
    ".env.staging", ".env.development",
]

CI_FILE_PATTERNS = [
    ".github/workflows/", ".gitlab-ci.yml", "Jenkinsfile",
    ".circleci/", "azure-pipelines.yml", "bitbucket-pipelines.yml",
]

SIGNING_PATTERNS = [
    "keystore", "signing", "codesign", "certificate",
    ".p12", ".pem", ".key", "provisionprofile",
]

MONITORING_PATTERNS = [
    "sentry", "datadog", "newrelic", "grafana", "prometheus",
    "elk", "cloudwatch", "rollbar", "bugsnag", "airbrake",
    "logging", "log_level", "log_format",
]

BACKUP_PATTERNS = [
    "backup", "restore", "migration", "rollback",
    "recovery", "disaster", "failover",
]


class ReleaseReadinessAuditAgent:
    """
    Audits project for release readiness concerns.

    Generates checks for:
    - Missing environment configs
    - Debug flags in production configs
    - Missing signing/build configs
    - Missing CI/release workflows
    - Missing monitoring/logging setup
    - Missing backup/recovery indicators
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_map: Optional[Dict[str, Any]] = None,
        file_contents: Optional[Dict[str, str]] = None,
        file_list: Optional[List[str]] = None,
    ) -> AuditResult:
        """Run the release readiness audit."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        checks: List[AuditCheck] = []

        # Check for config files
        checks.extend(self._check_environment_configs(file_list, file_contents))
        checks.extend(self._check_ci_configs(file_list))
        checks.extend(self._check_signing_configs(file_list))
        checks.extend(self._check_monitoring(file_list, file_contents))
        checks.extend(self._check_backup_recovery(file_list, file_contents))
        checks.extend(self._check_debug_in_production(file_contents))

        # Tally
        passed = sum(1 for c in checks if c.status == AuditCheckStatus.PASSED)
        failed = sum(1 for c in checks if c.status == AuditCheckStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == AuditCheckStatus.WARNING)
        blocked = sum(1 for c in checks if c.status == AuditCheckStatus.BLOCKED)
        skipped = sum(1 for c in checks if c.status == AuditCheckStatus.SKIPPED)

        duration = time.time() - start_time

        result = AuditResult(
            metadata=AuditResultMetadata(
                audit_type="release_readiness_audit",
                app_name=app_map.get("metadata", {}).get("app_name", ""),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration,
                generated_by="ReleaseReadinessAuditAgent",
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

        self.store.save_artifact("release_readiness_results", result.model_dump(), agent="ReleaseReadinessAuditAgent")
        logger.info(f"Release readiness audit complete: {passed} passed, {failed} failed, {warnings} warnings")
        return result

    def _check_environment_configs(self, file_list: Optional[List[str]], file_contents: Optional[Dict[str, str]]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        if not file_list:
            return checks

        found_env = [f for f in file_list if any(p in f for p in ENV_FILE_PATTERNS)]

        if not found_env:
            checks.append(AuditCheck(
                check_id="REL-ENV-001",
                title="No environment config files found",
                description="No .env or environment config files found.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="environment_config",
                target="project root",
                expected=".env.example or environment config",
                actual="No env files found",
                recommendation="Create environment configuration files.",
            ))
        else:
            has_example = any(".env.example" in f for f in found_env)
            if has_example:
                checks.append(AuditCheck(
                    check_id="REL-ENV-002",
                    title="Environment example file found",
                    description=f"Found .env.example: {', '.join(found_env[:3])}",
                    status=AuditCheckStatus.PASSED,
                    severity=AuditSeverity.LOW,
                    category="environment_config",
                    target=', '.join(found_env[:3]),
                ))
            else:
                checks.append(AuditCheck(
                    check_id="REL-ENV-003",
                    title="No .env.example found",
                    description="Found env files but no .env.example for documentation.",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.MEDIUM,
                    category="environment_config",
                    target=', '.join(found_env[:3]),
                    recommendation="Create .env.example documenting required variables.",
                ))

        return checks

    def _check_ci_configs(self, file_list: Optional[List[str]]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        if not file_list:
            return checks

        found_ci = [f for f in file_list if any(p in f for p in CI_FILE_PATTERNS)]

        if found_ci:
            checks.append(AuditCheck(
                check_id="REL-CI-001",
                title="CI/CD configuration found",
                description=f"Found CI config: {', '.join(found_ci[:3])}",
                status=AuditCheckStatus.PASSED,
                severity=AuditSeverity.LOW,
                category="ci_cd",
                target=', '.join(found_ci[:3]),
            ))
        else:
            checks.append(AuditCheck(
                check_id="REL-CI-002",
                title="No CI/CD configuration found",
                description="No CI/CD pipeline configuration detected.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="ci_cd",
                target="project root",
                expected="CI/CD pipeline configuration",
                actual="No CI config found",
                recommendation="Set up CI/CD pipeline for automated testing and deployment.",
            ))

        return checks

    def _check_signing_configs(self, file_list: Optional[List[str]]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        if not file_list:
            return checks

        found_signing = [f for f in file_list if any(p.lower() in f.lower() for p in SIGNING_PATTERNS)]

        if found_signing:
            checks.append(AuditCheck(
                check_id="REL-SIGN-001",
                title="Signing configuration found",
                description=f"Found signing artifacts: {', '.join(found_signing[:3])}",
                status=AuditCheckStatus.PASSED,
                severity=AuditSeverity.LOW,
                category="signing",
                target=', '.join(found_signing[:3]),
            ))
        else:
            checks.append(AuditCheck(
                check_id="REL-SIGN-002",
                title="No signing configuration found",
                description="No code signing or build signing configuration detected.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.LOW,
                category="signing",
                target="project root",
                recommendation="Set up code signing if distributing binaries.",
            ))

        return checks

    def _check_monitoring(self, file_list: Optional[List[str]], file_contents: Optional[Dict[str, str]]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        if not file_list:
            return checks

        found_monitoring = []
        if file_contents:
            for filepath, content in file_contents.items():
                for pattern in MONITORING_PATTERNS:
                    if pattern.lower() in content.lower():
                        found_monitoring.append(filepath)
                        break

        if found_monitoring:
            checks.append(AuditCheck(
                check_id="REL-MON-001",
                title="Monitoring/logging setup found",
                description=f"Found monitoring/logging references in: {', '.join(found_monitoring[:3])}",
                status=AuditCheckStatus.PASSED,
                severity=AuditSeverity.LOW,
                category="monitoring",
                target=', '.join(found_monitoring[:3]),
            ))
        else:
            checks.append(AuditCheck(
                check_id="REL-MON-002",
                title="No monitoring/logging setup detected",
                description="No monitoring or logging framework detected.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="monitoring",
                target="project root",
                expected="Monitoring/logging framework",
                actual="No monitoring detected",
                recommendation="Add error tracking (Sentry) and structured logging.",
            ))

        return checks

    def _check_backup_recovery(self, file_list: Optional[List[str]], file_contents: Optional[Dict[str, str]]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []

        has_backup = False
        if file_contents:
            for filepath, content in file_contents.items():
                for pattern in BACKUP_PATTERNS:
                    if pattern.lower() in content.lower():
                        has_backup = True
                        break
                if has_backup:
                    break

        if has_backup:
            checks.append(AuditCheck(
                check_id="REL-BAK-001",
                title="Backup/recovery references found",
                description="Found backup or recovery related code.",
                status=AuditCheckStatus.PASSED,
                severity=AuditSeverity.LOW,
                category="backup_recovery",
                target="codebase",
            ))
        else:
            checks.append(AuditCheck(
                check_id="REL-BAK-002",
                title="No backup/recovery indicators",
                description="No backup, recovery, or rollback mechanisms detected.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="backup_recovery",
                target="project root",
                expected="Backup/recovery strategy",
                actual="No backup indicators found",
                recommendation="Implement database backups and rollback procedures.",
            ))

        return checks

    def _check_debug_in_production(self, file_contents: Optional[Dict[str, str]]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        if not file_contents:
            return checks

        for filepath, content in file_contents.items():
            if "production" in filepath.lower() or "prod" in filepath.lower():
                if re.search(r'DEBUG\s*=\s*True', content, re.IGNORECASE):
                    checks.append(AuditCheck(
                        check_id=f"REL-DBG-{hash(filepath) % 10000:04d}",
                        title=f"Debug flag in production config: {filepath}",
                        description=f"DEBUG=True found in production config {filepath}.",
                        status=AuditCheckStatus.FAILED,
                        severity=AuditSeverity.CRITICAL,
                        category="debug_config",
                        target=filepath,
                        expected="DEBUG=False in production",
                        actual="DEBUG=True",
                        recommendation="Set DEBUG=False for production.",
                    ))

        return checks

    def _build_summary(self, checks: List[AuditCheck]) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        for c in checks:
            by_category[c.category] = by_category.get(c.category, 0) + 1
        return {
            "total_checks": len(checks),
            "by_category": by_category,
            "ready_for_release": not any(
                c.status == AuditCheckStatus.FAILED and c.severity == AuditSeverity.CRITICAL
                for c in checks
            ),
        }
