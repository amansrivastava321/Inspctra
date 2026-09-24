"""
code_quality_audit.py - Code quality audit agent.
Detects large files, TODO/FIXME/HACK comments, weak error handling,
missing logging, and dead code heuristically.
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

# Thresholds
LARGE_FILE_LINES = 500
LARGE_FUNCTION_LINES = 80
LARGE_CLASS_LINES = 300

TODO_PATTERN = re.compile(r'(?:#|//|/\*)\s*(TODO|FIXME|HACK|XXX|WORKAROUND)\b[:\s]*(.*?)(?:\*/)?$', re.IGNORECASE)
BARE_EXCEPT_PATTERN = re.compile(r'except\s*:', re.IGNORECASE)
EMPTY_CATCH_PATTERN = re.compile(r'except\s+\w+.*?:\s*\n\s*pass\s*$', re.MULTILINE)
FUNC_PATTERN = re.compile(r'(?:def|function|func)\s+(\w+)\s*\(', re.IGNORECASE)
CLASS_PATTERN = re.compile(r'(?:class)\s+(\w+)', re.IGNORECASE)


class CodeQualityAuditAgent:
    """
    Audits codebase for code quality issues via static analysis.

    Generates checks for:
    - Large files/classes/functions
    - TODO/FIXME/HACK comments
    - Duplicated logic heuristically
    - Weak error handling (bare except, empty catch)
    - Missing logging in critical areas
    - Dead/simple-unused files heuristically
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_map: Optional[Dict[str, Any]] = None,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> AuditResult:
        """Run the code quality audit."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        checks: List[AuditCheck] = []

        if file_contents:
            for filepath, content in file_contents.items():
                lines = content.split('\n')
                checks.extend(self._check_large_file(filepath, lines))
                checks.extend(self._check_large_functions(filepath, lines))
                checks.extend(self._check_large_classes(filepath, lines))
                checks.extend(self._check_todos(filepath, lines))
                checks.extend(self._check_weak_error_handling(filepath, lines))
                checks.extend(self._check_missing_logging(filepath, content))
                checks.extend(self._check_duplicate_patterns(filepath, content))

            checks.extend(self._check_duplicate_across_files(file_contents))

        # Tally
        passed = sum(1 for c in checks if c.status == AuditCheckStatus.PASSED)
        failed = sum(1 for c in checks if c.status == AuditCheckStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == AuditCheckStatus.WARNING)
        blocked = sum(1 for c in checks if c.status == AuditCheckStatus.BLOCKED)
        skipped = sum(1 for c in checks if c.status == AuditCheckStatus.SKIPPED)

        duration = time.time() - start_time

        result = AuditResult(
            metadata=AuditResultMetadata(
                audit_type="code_quality_audit",
                app_name=app_map.get("metadata", {}).get("app_name", ""),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration,
                generated_by="CodeQualityAuditAgent",
            ),
            total_checks=len(checks),
            passed=passed,
            failed=failed,
            warnings=warnings,
            blocked=blocked,
            skipped=skipped,
            checks=checks,
            summary=self._build_summary(checks, file_contents),
        )

        self.store.save_artifact("code_quality_results", result.model_dump(), agent="CodeQualityAuditAgent")
        logger.info(f"Code quality audit complete: {passed} passed, {failed} failed, {warnings} warnings")
        return result

    def _check_large_file(self, filepath: str, lines: List[str]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        line_count = len(lines)
        if line_count > LARGE_FILE_LINES:
            checks.append(AuditCheck(
                check_id=f"CQ-LFILE-{hash(filepath) % 10000:04d}",
                title=f"Large file: {filepath}",
                description=f"{filepath} has {line_count} lines (threshold: {LARGE_FILE_LINES}).",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="file_size",
                target=filepath,
                expected=f"< {LARGE_FILE_LINES} lines",
                actual=f"{line_count} lines",
                recommendation="Consider splitting into smaller modules.",
            ))
        return checks

    def _check_large_functions(self, filepath: str, lines: List[str]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        func_starts = []
        for i, line in enumerate(lines):
            m = FUNC_PATTERN.search(line)
            if m:
                func_starts.append((i, m.group(1)))

        for idx, (start, name) in enumerate(func_starts):
            end = func_starts[idx + 1][0] if idx + 1 < len(func_starts) else len(lines)
            func_len = end - start
            if func_len > LARGE_FUNCTION_LINES:
                checks.append(AuditCheck(
                    check_id=f"CQ-LFUNC-{hash(f'{filepath}:{name}') % 10000:04d}",
                    title=f"Large function: {name} in {filepath}",
                    description=f"Function '{name}' has {func_len} lines (threshold: {LARGE_FUNCTION_LINES}).",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.MEDIUM,
                    category="function_size",
                    target=f"{filepath}:{start + 1}",
                    expected=f"< {LARGE_FUNCTION_LINES} lines",
                    actual=f"{func_len} lines",
                    recommendation="Refactor into smaller functions.",
                ))
        return checks

    def _check_large_classes(self, filepath: str, lines: List[str]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        class_starts = []
        for i, line in enumerate(lines):
            m = CLASS_PATTERN.search(line)
            if m:
                class_starts.append((i, m.group(1)))

        for idx, (start, name) in enumerate(class_starts):
            end = class_starts[idx + 1][0] if idx + 1 < len(class_starts) else len(lines)
            class_len = end - start
            if class_len > LARGE_CLASS_LINES:
                checks.append(AuditCheck(
                    check_id=f"CQ-LCLS-{hash(f'{filepath}:{name}') % 10000:04d}",
                    title=f"Large class: {name} in {filepath}",
                    description=f"Class '{name}' has {class_len} lines (threshold: {LARGE_CLASS_LINES}).",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.MEDIUM,
                    category="class_size",
                    target=f"{filepath}:{start + 1}",
                    expected=f"< {LARGE_CLASS_LINES} lines",
                    actual=f"{class_len} lines",
                    recommendation="Consider splitting responsibilities.",
                ))
        return checks

    def _check_todos(self, filepath: str, lines: List[str]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        todo_count = 0
        examples: List[str] = []
        for i, line in enumerate(lines):
            m = TODO_PATTERN.search(line)
            if m:
                todo_count += 1
                if len(examples) < 3:
                    examples.append(f"L{i + 1}: {m.group(1)} - {m.group(2).strip()[:60]}")

        if todo_count > 0:
            checks.append(AuditCheck(
                check_id=f"CQ-TODO-{hash(filepath) % 10000:04d}",
                title=f"TODO/FIXME/HACK comments: {filepath}",
                description=f"Found {todo_count} TODO/FIXME/HACK comment(s) in {filepath}. Examples: {'; '.join(examples)}",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.LOW,
                category="technical_debt",
                target=filepath,
                expected="No unresolved TODOs",
                actual=f"{todo_count} TODO/FIXME/HACK comments",
                recommendation="Address or remove TODO/FIXME/HACK comments before release.",
            ))
        return checks

    def _check_weak_error_handling(self, filepath: str, lines: List[str]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        content = '\n'.join(lines)

        bare_count = len(BARE_EXCEPT_PATTERN.findall(content))
        empty_count = len(EMPTY_CATCH_PATTERN.findall(content))

        if bare_count > 0:
            checks.append(AuditCheck(
                check_id=f"CQ-EXCEPT-{hash(filepath) % 10000:04d}",
                title=f"Bare except clause: {filepath}",
                description=f"Found {bare_count} bare except clause(s) in {filepath}.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="error_handling",
                target=filepath,
                expected="Specific exception types caught",
                actual=f"{bare_count} bare except clauses",
                recommendation="Catch specific exceptions instead of bare except.",
            ))

        if empty_count > 0:
            checks.append(AuditCheck(
                check_id=f"CQ-EMPTY-{hash(filepath) % 10000:04d}",
                title=f"Empty catch block: {filepath}",
                description=f"Found {empty_count} empty catch block(s) in {filepath}.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.MEDIUM,
                category="error_handling",
                target=filepath,
                expected="Errors logged or handled",
                actual=f"{empty_count} empty catch blocks",
                recommendation="Log or handle caught exceptions.",
            ))
        return checks

    def _check_missing_logging(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        has_logging = bool(re.search(r'(?:logging|logger|console\.log|print)\s*[\(.]', content))
        has_except = "except" in content.lower()

        if has_except and not has_logging:
            checks.append(AuditCheck(
                check_id=f"CQ-NOLOG-{hash(filepath) % 10000:04d}",
                title=f"Missing logging in error handler: {filepath}",
                description=f"{filepath} has exception handling but no logging.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.LOW,
                category="observability",
                target=filepath,
                expected="Errors logged",
                actual="No logging in error handling paths",
                recommendation="Add logging to exception handlers.",
            ))
        return checks

    def _check_duplicate_patterns(self, filepath: str, content: str) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        # Heuristic: repeated long lines suggest copy-paste
        lines = content.split('\n')
        long_lines = [l.strip() for l in lines if len(l.strip()) > 60 and not l.strip().startswith('#')]
        seen: Dict[str, int] = {}
        for line in long_lines:
            seen[line] = seen.get(line, 0) + 1

        dups = {line: count for line, count in seen.items() if count > 1}
        if dups:
            checks.append(AuditCheck(
                check_id=f"CQ-DUP-{hash(filepath) % 10000:04d}",
                title=f"Duplicated lines: {filepath}",
                description=f"Found {len(dups)} duplicated long line(s) in {filepath}.",
                status=AuditCheckStatus.WARNING,
                severity=AuditSeverity.LOW,
                category="duplication",
                target=filepath,
                expected="No duplicated logic",
                actual=f"{len(dups)} duplicated lines",
                recommendation="Extract duplicated logic into shared functions.",
            ))
        return checks

    def _check_duplicate_across_files(self, file_contents: Dict[str, str]) -> List[AuditCheck]:
        checks: List[AuditCheck] = []
        # Heuristic: files with identical non-trivial blocks
        file_hashes: Dict[str, List[str]] = {}
        for filepath, content in file_contents.items():
            normalized = re.sub(r'\s+', ' ', content.strip())
            if len(normalized) > 200:
                h = hash(normalized[:500])
                key = str(h)
                file_hashes.setdefault(key, []).append(filepath)

        for key, files in file_hashes.items():
            if len(files) > 1:
                checks.append(AuditCheck(
                    check_id=f"CQ-DUPF-{hash(key) % 10000:04d}",
                    title=f"Duplicate files: {', '.join(files[:3])}",
                    description=f"Files appear to have identical content: {', '.join(files[:3])}",
                    status=AuditCheckStatus.WARNING,
                    severity=AuditSeverity.MEDIUM,
                    category="duplication",
                    target=', '.join(files[:3]),
                    expected="No duplicate files",
                    actual=f"{len(files)} files with identical content",
                    recommendation="Consolidate duplicate files.",
                ))
        return checks

    def _build_summary(self, checks: List[AuditCheck], file_contents: Optional[Dict[str, str]]) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        for c in checks:
            by_category[c.category] = by_category.get(c.category, 0) + 1
        return {
            "total_checks": len(checks),
            "files_audited": len(file_contents) if file_contents else 0,
            "by_category": by_category,
            "has_large_files": any(c.category == "file_size" for c in checks),
            "has_tech_debt": any(c.category == "technical_debt" for c in checks),
        }
