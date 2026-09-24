"""Tests for qa_ai.interactive_runtime.database_verifier.DatabaseVerifier."""
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
from qa_ai.interactive_runtime.schemas import VerificationStatus


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sqlite_db(tmp_path):
    """Create a minimal SQLite DB with a test table."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active'
        )
    """)
    conn.execute("INSERT INTO users (id, name, status) VALUES (1, 'Alice', 'active')")
    conn.execute("INSERT INTO users (id, name, status) VALUES (2, 'Bob', 'inactive')")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def enabled_verifier(sqlite_db):
    return DatabaseVerifier(
        db_type="sqlite",
        path=sqlite_db,
        read_only=True,
        enabled=True,
    )


@pytest.fixture
def disabled_verifier():
    return DatabaseVerifier(
        db_type="sqlite",
        enabled=False,
    )


# ── disabled mode ─────────────────────────────────────────────────────────────

class TestDatabaseVerifierDisabled:
    def test_row_exists_returns_skipped_when_disabled(self, disabled_verifier):
        result = disabled_verifier.check_row_exists("users", "id = 1")
        assert result.status == VerificationStatus.SKIPPED

    def test_row_count_returns_skipped_when_disabled(self, disabled_verifier):
        result = disabled_verifier.check_row_count("users")
        assert result.status == VerificationStatus.SKIPPED

    def test_field_value_returns_skipped_when_disabled(self, disabled_verifier):
        result = disabled_verifier.check_field_value("users", "name", "Alice", "id = 1")
        assert result.status == VerificationStatus.SKIPPED

    def test_no_duplicates_returns_skipped_when_disabled(self, disabled_verifier):
        result = disabled_verifier.check_no_duplicates("users", "name")
        assert result.status == VerificationStatus.SKIPPED


# ── read-only guard ────────────────────────────────────────────────────────────

class TestDatabaseVerifierWriteGuard:
    def test_insert_query_raises(self, enabled_verifier):
        with pytest.raises(ValueError, match="read-only"):
            enabled_verifier._guard_write("INSERT INTO users (name) VALUES ('Eve')")

    def test_update_query_raises(self, enabled_verifier):
        with pytest.raises(ValueError, match="read-only"):
            enabled_verifier._guard_write("UPDATE users SET status='deleted' WHERE id=1")

    def test_delete_query_raises(self, enabled_verifier):
        with pytest.raises(ValueError, match="read-only"):
            enabled_verifier._guard_write("DELETE FROM users WHERE id=2")

    def test_drop_query_raises(self, enabled_verifier):
        with pytest.raises(ValueError, match="read-only"):
            enabled_verifier._guard_write("DROP TABLE users")

    def test_alter_query_raises(self, enabled_verifier):
        with pytest.raises(ValueError, match="read-only"):
            enabled_verifier._guard_write("ALTER TABLE users ADD COLUMN email TEXT")

    def test_truncate_query_raises(self, enabled_verifier):
        with pytest.raises(ValueError, match="read-only"):
            enabled_verifier._guard_write("TRUNCATE TABLE users")

    def test_select_query_passes_guard(self, enabled_verifier):
        enabled_verifier._guard_write("SELECT * FROM users")  # no exception


# ── SQLite row_exists ──────────────────────────────────────────────────────────

class TestDatabaseVerifierRowExists:
    def test_row_exists_when_present(self, enabled_verifier):
        result = enabled_verifier.check_row_exists("users", "id = 1")
        assert result.status == VerificationStatus.PASSED

    def test_row_not_found_fails(self, enabled_verifier):
        result = enabled_verifier.check_row_exists("users", "id = 999")
        assert result.status == VerificationStatus.FAILED

    def test_row_exists_returns_check_type_db_row(self, enabled_verifier):
        result = enabled_verifier.check_row_exists("users", "id = 1")
        assert result.check_type == "db_row"


# ── SQLite row_count ───────────────────────────────────────────────────────────

class TestDatabaseVerifierRowCount:
    def test_count_meets_minimum(self, enabled_verifier):
        result = enabled_verifier.check_row_count("users", expected_min=1)
        assert result.status == VerificationStatus.PASSED

    def test_count_exact_minimum(self, enabled_verifier):
        result = enabled_verifier.check_row_count("users", expected_min=2)
        assert result.status == VerificationStatus.PASSED

    def test_count_below_minimum_fails(self, enabled_verifier):
        result = enabled_verifier.check_row_count("users", expected_min=100)
        assert result.status == VerificationStatus.FAILED

    def test_count_with_where_clause(self, enabled_verifier):
        result = enabled_verifier.check_row_count(
            "users", expected_min=1, where_clause="status = 'active'"
        )
        assert result.status == VerificationStatus.PASSED


# ── SQLite field_value ─────────────────────────────────────────────────────────

class TestDatabaseVerifierFieldValue:
    def test_field_value_matches(self, enabled_verifier):
        result = enabled_verifier.check_field_value("users", "name", "Alice", "id = 1")
        assert result.status == VerificationStatus.PASSED

    def test_field_value_mismatch_fails(self, enabled_verifier):
        result = enabled_verifier.check_field_value("users", "name", "Charlie", "id = 1")
        assert result.status == VerificationStatus.FAILED

    def test_field_value_no_row_fails(self, enabled_verifier):
        result = enabled_verifier.check_field_value("users", "name", "X", "id = 999")
        assert result.status == VerificationStatus.FAILED


# ── SQLite no_duplicates ───────────────────────────────────────────────────────

class TestDatabaseVerifierNoDuplicates:
    def test_unique_field_passes(self, enabled_verifier):
        result = enabled_verifier.check_no_duplicates("users", "name")
        assert result.status == VerificationStatus.PASSED

    def test_duplicate_field_fails(self, sqlite_db):
        conn = sqlite3.connect(sqlite_db)
        conn.execute("INSERT INTO users (id, name) VALUES (3, 'Alice')")
        conn.commit()
        conn.close()
        verifier = DatabaseVerifier(db_type="sqlite", path=sqlite_db, enabled=True)
        result = verifier.check_no_duplicates("users", "name")
        assert result.status == VerificationStatus.FAILED


# ── missing SQLite path ────────────────────────────────────────────────────────

class TestDatabaseVerifierMissingPath:
    def test_nonexistent_sqlite_path_returns_failed(self):
        verifier = DatabaseVerifier(
            db_type="sqlite",
            path="/nonexistent/path/db.sqlite",
            enabled=True,
        )
        result = verifier.check_row_exists("users", "id = 1")
        assert result.status == VerificationStatus.FAILED
