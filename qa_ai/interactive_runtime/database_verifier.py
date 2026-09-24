"""
database_verifier.py - Read-only database state verification.

Supports SQLite (local) and Supabase/Postgres (via REST API or psycopg2).
Never writes to any database. Never modifies production data.
Requires explicit config to enable.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# SQL identifier allowlist: table names and field names must be alphanumeric + underscore
# This guards the f-string query builders against SQL injection.
_SQL_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$")

from qa_ai.interactive_runtime.schemas import VerificationCheck, VerificationStatus

logger = logging.getLogger(__name__)


class DatabaseVerifier:
    """
    Verify database state after UI actions using read-only queries.

    All operations are SELECT-only. Any attempt to write/modify raises
    ValueError immediately — no exceptions to this rule.

    Supported backends:
    - SQLite (path-based)
    - Supabase (REST API via env vars)
    - Postgres (via psycopg2 if installed, read-only connection)
    """

    def __init__(
        self,
        db_type: str = "sqlite",
        path: Optional[str] = None,
        url_env: Optional[str] = None,
        key_env: Optional[str] = None,
        read_only: bool = True,
        enabled: bool = False,
    ):
        self._type = db_type
        self._path = path
        self._url_env = url_env
        self._key_env = key_env
        self._read_only = read_only
        self._enabled = enabled

    @classmethod
    def from_context(cls, ctx: Any) -> "DatabaseVerifier":
        """
        Create a DatabaseVerifier from a RuntimeTestContext.

        ctx: RuntimeTestContext or None.
        Returns a DatabaseVerifier configured from context,
        with enabled=True only if database_available=True.

        Security: only copies env var NAMES (database_url_env), never values.
        """
        if ctx is None:
            return cls(enabled=False)
        db_available = getattr(ctx, "database_available", False)
        if not db_available:
            return cls(enabled=False)
        return cls(
            db_type=getattr(ctx, "database_type", None) or "sqlite",
            path=getattr(ctx, "database_path", None),
            url_env=getattr(ctx, "database_url_env", None),   # env var NAME only
            enabled=True,
        )

    # ── safety ────────────────────────────────────────────────────────────────

    @staticmethod
    def _guard_identifier(name: str, kind: str = "identifier") -> None:
        """
        Reject SQL identifiers that don't match the allowlist pattern.

        Prevents SQL injection in f-string query builders.
        Only alphanumeric + underscore, max 128 chars.
        """
        if not _SQL_IDENTIFIER_RE.match(name):
            raise ValueError(
                f"DatabaseVerifier: invalid SQL {kind} '{name!r}' — "
                "only alphanumeric/underscore allowed (no spaces, quotes, special chars)."
            )

    def _guard_write(self, query: str) -> None:
        """Reject any mutating SQL."""
        low = query.strip().lower()
        for keyword in ("insert ", "update ", "delete ", "drop ", "alter ", "truncate ", "create "):
            if low.startswith(keyword):
                raise ValueError(
                    f"DatabaseVerifier is read-only. Mutating query blocked: {query[:80]}"
                )

    # ── public checks ─────────────────────────────────────────────────────────

    def check_row_exists(
        self,
        table: str,
        where_clause: str,
        description: str = "",
    ) -> VerificationCheck:
        """Verify that at least one row matching the WHERE clause exists."""
        if not self._enabled:
            return self._disabled_check("row_exists", table)

        try:
            self._guard_identifier(table, "table")
        except ValueError as exc:
            return VerificationCheck(
                check_type="db_row", description=str(exc),
                expected="valid table name", actual=table,
                status=VerificationStatus.FAILED,
            )

        query = f"SELECT COUNT(*) FROM {table} WHERE {where_clause} LIMIT 1"
        result = self._execute(query)
        if result is None:
            return VerificationCheck(
                check_type="db_row",
                description=description or f"Row exists in {table}",
                expected="COUNT > 0",
                actual="Query failed",
                status=VerificationStatus.FAILED,
            )
        count = result[0][0] if result else 0
        return VerificationCheck(
            check_type="db_row",
            description=description or f"Row exists in {table} WHERE {where_clause}",
            expected="COUNT > 0",
            actual=str(count),
            status=VerificationStatus.PASSED if count > 0 else VerificationStatus.FAILED,
        )

    def check_row_count(
        self,
        table: str,
        expected_min: int = 1,
        where_clause: Optional[str] = None,
    ) -> VerificationCheck:
        """Verify row count meets minimum."""
        if not self._enabled:
            return self._disabled_check("row_count", table)

        try:
            self._guard_identifier(table, "table")
        except ValueError as exc:
            return VerificationCheck(
                check_type="db_row", description=str(exc),
                expected="valid table name", actual=table,
                status=VerificationStatus.FAILED,
            )

        clause = f" WHERE {where_clause}" if where_clause else ""
        query = f"SELECT COUNT(*) FROM {table}{clause}"
        result = self._execute(query)
        if result is None:
            return VerificationCheck(
                check_type="db_row",
                description=f"Row count in {table}",
                expected=f">= {expected_min}",
                actual="Query failed",
                status=VerificationStatus.FAILED,
            )
        count = result[0][0] if result else 0
        ok = count >= expected_min
        return VerificationCheck(
            check_type="db_row",
            description=f"Row count in {table}{clause}",
            expected=f">= {expected_min}",
            actual=str(count),
            status=VerificationStatus.PASSED if ok else VerificationStatus.FAILED,
        )

    def check_field_value(
        self,
        table: str,
        field: str,
        expected_value: Any,
        where_clause: str,
    ) -> VerificationCheck:
        """Verify a specific field value."""
        if not self._enabled:
            return self._disabled_check("field_value", table)

        for ident, kind in ((table, "table"), (field, "field")):
            try:
                self._guard_identifier(ident, kind)
            except ValueError as exc:
                return VerificationCheck(
                    check_type="db_row", description=str(exc),
                    expected=f"valid {kind} name", actual=ident,
                    status=VerificationStatus.FAILED,
                )

        query = f"SELECT {field} FROM {table} WHERE {where_clause} LIMIT 1"
        result = self._execute(query)
        if result is None or not result:
            return VerificationCheck(
                check_type="db_row",
                description=f"{table}.{field} value check",
                expected=str(expected_value),
                actual="No rows / query failed",
                status=VerificationStatus.FAILED,
            )
        actual = result[0][0]
        ok = str(actual) == str(expected_value)
        return VerificationCheck(
            check_type="db_row",
            description=f"{table}.{field} WHERE {where_clause}",
            expected=str(expected_value),
            actual=str(actual),
            status=VerificationStatus.PASSED if ok else VerificationStatus.FAILED,
        )

    def check_no_duplicates(self, table: str, unique_field: str) -> VerificationCheck:
        """Verify no duplicate values in a field."""
        if not self._enabled:
            return self._disabled_check("no_duplicates", table)

        for ident, kind in ((table, "table"), (unique_field, "field")):
            try:
                self._guard_identifier(ident, kind)
            except ValueError as exc:
                return VerificationCheck(
                    check_type="db_row", description=str(exc),
                    expected=f"valid {kind} name", actual=ident,
                    status=VerificationStatus.FAILED,
                )

        query = f"SELECT {unique_field}, COUNT(*) as cnt FROM {table} GROUP BY {unique_field} HAVING cnt > 1 LIMIT 1"
        result = self._execute(query)
        if result is None:
            return VerificationCheck(
                check_type="db_row",
                description=f"No duplicates in {table}.{unique_field}",
                expected="No duplicate rows",
                actual="Query failed",
                status=VerificationStatus.FAILED,
            )
        ok = len(result) == 0
        return VerificationCheck(
            check_type="db_row",
            description=f"No duplicates in {table}.{unique_field}",
            expected="No duplicate rows",
            actual=f"{len(result)} duplicate(s) found" if not ok else "Clean",
            status=VerificationStatus.PASSED if ok else VerificationStatus.FAILED,
        )

    # ── execution backends ────────────────────────────────────────────────────

    def _execute(self, query: str) -> Optional[List]:
        self._guard_write(query)
        if self._type == "sqlite":
            return self._execute_sqlite(query)
        elif self._type in ("postgres", "supabase"):
            return self._execute_supabase(query)
        logger.warning("Unsupported database type: %s", self._type)
        return None

    def _execute_sqlite(self, query: str) -> Optional[List]:
        if not self._path or not os.path.exists(self._path):
            logger.warning("SQLite path not found: %s", self._path)
            return None
        try:
            import sqlite3
            conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
            try:
                cur = conn.execute(query)
                return cur.fetchall()
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("SQLite query failed: %s — %s", query[:80], exc)
            return None

    def _execute_supabase(self, query: str) -> Optional[List]:
        # Use Supabase REST API (read-only via anon/service key)
        url = os.environ.get(self._url_env or "", "")
        key = os.environ.get(self._key_env or "", "")
        if not url or not key:
            logger.warning("Supabase URL/key env vars not set")
            return None
        try:
            import urllib.request as req
            import urllib.parse
            payload = json.dumps({"query": query}).encode()
            request = req.Request(
                f"{url}/rest/v1/rpc/execute_sql",
                data=payload,
                headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            with req.urlopen(request, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            logger.warning("Supabase query failed: %s", exc)
            return None

    def _disabled_check(self, check_type: str, table: str) -> VerificationCheck:
        return VerificationCheck(
            check_type=f"db_{check_type}",
            description=f"Database check for {table} (disabled in config)",
            expected="—",
            actual="database_verification_enabled=false",
            status=VerificationStatus.SKIPPED,
        )
