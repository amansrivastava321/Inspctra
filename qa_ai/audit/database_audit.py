"""
database_audit.py - Database schema and integrity audit agent.
Detects database technologies, scans migrations/schema files,
and generates checks for missing migrations, dangerous nullable fields,
missing foreign keys, missing indexes, and more.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import logging
import re
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


# Technology detection patterns
TECH_PATTERNS: Dict[str, List[str]] = {
    "sqlite": [
        r"sqlite3?",
        r"\.db\b",
        r"drift",
        r"sqflite",
    ],
    "postgres": [
        r"postgres(ql)?",
        r"supabase",
        r"pg_",
        r"neon\.tech",
    ],
    "firebase": [
        r"firebase",
        r"firestore",
        r"cloud_firestore",
    ],
    "prisma": [
        r"prisma",
        r"\.prisma\b",
    ],
    "sqlalchemy": [
        r"sqlalchemy",
        r"declarative_base",
        r"Column\(",
    ],
    "django_orm": [
        r"django",
        r"models\.Model",
        r"from django\.db",
    ],
    "typeorm": [
        r"typeorm",
        r"@Entity",
        r"@Column",
    ],
    "mongoose": [
        r"mongoose",
        r"Schema\(",
        r"model\(",
    ],
    "drift": [
        r"drift",
        r"DriftDatabase",
        r"@DriftDatabase",
    ],
}

# File patterns for schema/migration files
SCHEMA_FILE_PATTERNS = [
    r"schema\.prisma",
    r"models\.py",
    r"entities/.*\.ts$",
    r"migration.*\.sql$",
    r"migration.*\.py$",
    r"migration.*\.ts$",
    r"versions/.*\.py$",
    r"alembic/.*\.py$",
    r"knexfile\.",
    r"database\.sql",
]

# Dangerous nullable field patterns
DANGEROUS_NULLABLE_PATTERNS = [
    (r"user_?id.*nullable", "user_id should not be nullable"),
    (r"email.*nullable", "email should not be nullable"),
    (r"account_?id.*nullable", "account_id should not be nullable"),
    (r"order_?id.*nullable", "order_id should not be nullable"),
    (r"foreign.*key.*nullable", "Foreign key column should not be nullable without justification"),
]

# Fields that likely need indexes
LOOKUP_FIELD_PATTERNS = [
    r"\bemail\b",
    r"\busername\b",
    r"\buser_id\b",
    r"\baccount_id\b",
    r"\bslug\b",
    r"\btoken\b",
    r"\breference\b",
    r"\bexternal_id\b",
    r"\bstatus\b",
]


class DatabaseAuditAgent:
    """
    Audits database schema, migrations, and integrity.

    Detects:
    - Database technology (SQLite/Drift, Supabase/Postgres, Firebase, Prisma, etc.)
    - Missing migrations
    - Dangerous nullable fields
    - Missing foreign keys
    - Missing indexes on lookup fields
    - Integer size risks
    - created_at/updated_at consistency
    - Soft-delete/tombstone support
    - Orphan record risks
    - Migration ordering risks
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_map: Optional[Dict[str, Any]] = None,
        detected_files: Optional[List[str]] = None,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> AuditResult:
        """
        Run the database audit.

        Args:
            app_map: Application map from Discovery phase.
            detected_files: List of file paths found in the project.
            file_contents: Dict of file_path -> content for schema/migration files.

        Returns:
            AuditResult with all checks.
        """
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        if detected_files is None:
            detected_files = app_map.get("detected_files", [])

        # Detect technologies
        technologies = self._detect_technologies(app_map, detected_files, file_contents)
        logger.info(f"Detected database technologies: {technologies}")

        checks: List[AuditCheck] = []

        # Generate technology-specific checks
        for tech in technologies:
            checks.extend(self._check_for_technology(tech, file_contents))

        # Generic schema checks if we have file contents
        if file_contents:
            for filepath, content in file_contents.items():
                checks.extend(self._check_schema_file(filepath, content, technologies))

        # Check for migration files
        checks.extend(self._check_migration_files(detected_files))

        # Tally results
        passed = sum(1 for c in checks if c.status == AuditCheckStatus.PASSED)
        failed = sum(1 for c in checks if c.status == AuditCheckStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == AuditCheckStatus.WARNING)
        blocked = sum(1 for c in checks if c.status == AuditCheckStatus.BLOCKED)
        skipped = sum(1 for c in checks if c.status == AuditCheckStatus.SKIPPED)

        duration = time.time() - start_time

        result = AuditResult(
            metadata=AuditResultMetadata(
                audit_type="database_audit",
                app_name=app_map.get("metadata", {}).get("app_name", ""),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration,
                generated_by="DatabaseAuditAgent",
            ),
            total_checks=len(checks),
            passed=passed,
            failed=failed,
            warnings=warnings,
            blocked=blocked,
            skipped=skipped,
            checks=checks,
            summary=self._build_summary(checks, technologies),
        )

        self.store.save_artifact("database_audit_results", result.model_dump(), agent="DatabaseAuditAgent")

        logger.info(
            f"Database audit complete: {passed} passed, {failed} failed, "
            f"{warnings} warnings out of {len(checks)} checks"
        )

        return result

    def _detect_technologies(
        self,
        app_map: Dict[str, Any],
        detected_files: List[str],
        file_contents: Optional[Dict[str, str]],
    ) -> List[str]:
        """Detect database technologies from app_map and files."""
        found: List[str] = []
        stack = app_map.get("stack", {})

        # Check stack info
        db_field = stack.get("database", "") or ""
        if db_field:
            found.append(db_field.lower())

        # Check detected file paths
        all_text = " ".join(detected_files).lower()

        # Check file contents if available
        if file_contents:
            all_text += " " + " ".join(file_contents.values()).lower()

        for tech, patterns in TECH_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, all_text, re.IGNORECASE):
                    if tech not in found:
                        found.append(tech)
                    break

        return found

    def _check_for_technology(
        self, tech: str, file_contents: Optional[Dict[str, str]]
    ) -> List[AuditCheck]:
        """Generate checks specific to a detected technology."""
        checks: List[AuditCheck] = []

        if tech in ("sqlite", "drift"):
            checks.append(AuditCheck(
                check_id=f"DB-TECH-{tech.upper()}",
                title=f"SQLite/Drift detected: {tech}",
                description=f"Application uses {tech}. SQLite is not suitable for concurrent writes or production multi-user workloads.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="technology_risk",
                target=tech,
                recommendation="Consider migrating to PostgreSQL or MySQL for production use.",
            ))

        if tech == "firebase":
            checks.append(AuditCheck(
                check_id="DB-TECH-FIREBASE",
                title="Firebase detected",
                description="Firebase/Firestore detected. Verify security rules and offline sync behavior.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="technology_risk",
                target="firebase",
                recommendation="Review Firebase security rules and test offline-to-online sync scenarios.",
            ))

        return checks

    def _check_schema_file(
        self, filepath: str, content: str, technologies: List[str]
    ) -> List[AuditCheck]:
        """Run checks against a single schema file's content."""
        checks: List[AuditCheck] = []
        content_lower = content.lower()

        # 1. Dangerous nullable fields
        for pattern, message in DANGEROUS_NULLABLE_PATTERNS:
            if re.search(pattern, content_lower):
                checks.append(AuditCheck(
                    check_id=f"DB-NULL-{len(checks):03d}",
                    title=f"Dangerous nullable: {message}",
                    description=f"Found potentially dangerous nullable field in {filepath}: {message}",
                    status=AuditCheckStatus.FAILED,
                    severity=AuditSeverity.HIGH,
                    category="schema_design",
                    target=filepath,
                    recommendation="Make this field non-nullable or add a default value.",
                ))

        # 2. Missing indexes on lookup fields
        for field_pattern in LOOKUP_FIELD_PATTERNS:
            if re.search(field_pattern, content_lower):
                has_index = bool(re.search(
                    r"(index|unique|INDEX|UNIQUE).*" + field_pattern,
                    content,
                    re.IGNORECASE,
                ))
                field_name = re.search(field_pattern, content_lower)
                if field_name and not has_index:
                    checks.append(AuditCheck(
                        check_id=f"DB-IDX-{len(checks):03d}",
                        title=f"Missing index: {field_name.group()}",
                        description=f"Field '{field_name.group()}' in {filepath} is likely used for lookups but has no index.",
                        status=AuditCheckStatus.WARNING,
                        severity=AuditSeverity.MEDIUM,
                        category="performance",
                        target=filepath,
                        recommendation=f"Add an index on {field_name.group()} for query performance.",
                    ))

        # 3. Foreign key detection
        fk_pattern = r"(foreign\s+key|references|@ManyToOne|@OneToMany|ForeignKey)"
        has_foreign_keys = bool(re.search(fk_pattern, content, re.IGNORECASE))
        has_references = bool(re.search(r"(user_id|account_id|order_id|_id\b)", content_lower))

        if has_references and not has_foreign_keys:
            checks.append(AuditCheck(
                check_id=f"DB-FK-{len(checks):03d}",
                title="Missing foreign key constraints",
                description=f"File {filepath} contains ID references but no explicit foreign key constraints.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="referential_integrity",
                target=filepath,
                recommendation="Add foreign key constraints to enforce referential integrity.",
            ))

        # 4. created_at/updated_at consistency
        has_created_at = bool(re.search(r"created_at|created_on|createdAt", content_lower))
        has_updated_at = bool(re.search(r"updated_at|updated_on|updatedAt", content_lower))

        if has_created_at and not has_updated_at:
            checks.append(AuditCheck(
                check_id=f"DB-TS-{len(checks):03d}",
                title="Missing updated_at timestamp",
                description=f"File {filepath} has created_at but no updated_at field.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.LOW,
                category="schema_design",
                target=filepath,
                recommendation="Add updated_at timestamp for audit trail.",
            ))

        # 5. Soft-delete / tombstone support
        has_soft_delete = bool(re.search(
            r"deleted_at|is_deleted|soft.?delete|tombstone|is_active",
            content_lower,
        ))
        has_delete_op = bool(re.search(r"\.delete|DELETE\s+FROM|remove\(", content, re.IGNORECASE))

        if has_delete_op and not has_soft_delete:
            checks.append(AuditCheck(
                check_id=f"DB-DEL-{len(checks):03d}",
                title="No soft-delete support",
                description=f"File {filepath} performs hard deletes without soft-delete/tombstone pattern.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="data_safety",
                target=filepath,
                recommendation="Consider soft-delete (deleted_at) for data recovery and audit trail.",
            ))

        # 6. Integer size risk
        int_pattern = r"(INTEGER|INT|SMALLINT|TINYINT|BIGINT)"
        int_matches = re.findall(int_pattern, content, re.IGNORECASE)
        if int_matches:
            has_bigint = any(m.upper() == "BIGINT" for m in int_matches)
            has_id_field = bool(re.search(r"\bid\b.*\b(INTEGER|INT)\b", content_lower))
            if has_id_field and not has_bigint:
                checks.append(AuditCheck(
                    check_id=f"DB-INT-{len(checks):03d}",
                    title="Integer ID size risk",
                    description=f"File {filepath} uses INTEGER for ID fields. May overflow at 2^31 rows.",
                    status=AuditCheckStatus.INFO,
                    severity=AuditSeverity.LOW,
                    category="schema_design",
                    target=filepath,
                    recommendation="Use BIGINT for primary keys to avoid overflow risk.",
                ))

        return checks

    def _check_migration_files(self, detected_files: List[str]) -> List[AuditCheck]:
        """Check for migration file presence and ordering."""
        checks: List[AuditCheck] = []

        migration_files = [
            f for f in detected_files
            if re.search(r"migration|migrate|alembic|versions", f, re.IGNORECASE)
        ]

        if not migration_files:
            # Check if any schema-like files exist
            schema_files = [
                f for f in detected_files
                if re.search(r"schema|models|entities|\.sql$", f, re.IGNORECASE)
            ]
            if schema_files:
                checks.append(AuditCheck(
                    check_id="DB-MIG-001",
                    title="No migration files found",
                    description=f"Found schema files ({', '.join(schema_files[:3])}) but no migration files.",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.MEDIUM,
                    category="migrations",
                    target=", ".join(schema_files[:5]),
                    recommendation="Set up a migration system (Alembic, Prisma Migrate, Knex, etc.).",
                ))
            else:
                checks.append(AuditCheck(
                    check_id="DB-MIG-002",
                    title="No database files detected",
                    description="No schema, model, or migration files were detected in the project.",
                    status=AuditCheckStatus.BLOCKED,
                    severity=AuditSeverity.LOW,
                    category="migrations",
                    blocked_reason="No database-related files found in the project.",
                ))
        else:
            # Check migration ordering
            checks.extend(self._check_migration_ordering(migration_files))

        return checks

    def _check_migration_ordering(self, migration_files: List[str]) -> List[AuditCheck]:
        """Check if migration files appear to be properly ordered."""
        checks: List[AuditCheck] = []

        # Extract timestamps or sequence numbers from filenames
        timestamps: List[Tuple[str, str]] = []
        for f in migration_files:
            ts_match = re.search(r"(\d{8,14}|\d{3,})", f)
            if ts_match:
                timestamps.append((f, ts_match.group(1)))

        if len(timestamps) >= 2:
            sorted_ts = sorted(timestamps, key=lambda x: x[1])
            if timestamps != sorted_ts:
                checks.append(AuditCheck(
                    check_id="DB-MIG-ORD",
                    title="Migration ordering risk",
                    description="Migration files may not be in chronological order.",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.MEDIUM,
                    category="migrations",
                    target=timestamps[0][0],
                    recommendation="Ensure migrations are applied in timestamp order.",
                ))

        return checks

    def _build_summary(
        self, checks: List[AuditCheck], technologies: List[str]
    ) -> Dict[str, Any]:
        """Build a summary of database audit results."""
        by_category: Dict[str, int] = {}
        for c in checks:
            by_category[c.category] = by_category.get(c.category, 0) + 1

        return {
            "technologies_detected": technologies,
            "total_checks": len(checks),
            "by_category": by_category,
            "has_migration_risks": any(
                c.status in (AuditCheckStatus.FAILED, AuditCheckStatus.WARNING)
                and c.category == "migrations"
                for c in checks
            ),
            "has_schema_risks": any(
                c.status == AuditCheckStatus.FAILED and c.category == "schema_design"
                for c in checks
            ),
        }
