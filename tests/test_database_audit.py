"""
test_database_audit.py - Tests for the database audit agent.
Validates technology detection, schema checks, migration checks,
and artifact persistence.
"""

import pytest

from qa_ai.audit.database_audit import DatabaseAuditAgent
from qa_ai.schemas.audit_result_schema import AuditCheckStatus, AuditSeverity


class TestDatabaseAuditAgent:
    def test_detects_sqlite_signal(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "stack": {"database": "sqlite"},
            "detected_files": [],
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        assert result.metadata.audit_type == "database_audit"
        assert "sqlite" in result.summary["technologies_detected"]

    def test_detects_drift_signal(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "stack": {},
            "detected_files": ["lib/database/drift_database.dart"],
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        assert "drift" in result.summary["technologies_detected"]

    def test_detects_supabase_signal(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "stack": {},
            "detected_files": ["supabase/config.toml"],
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        assert "postgres" in result.summary["technologies_detected"] or "supabase" in result.summary["technologies_detected"]

    def test_detects_prisma_signal(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "stack": {},
            "detected_files": ["prisma/schema.prisma"],
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        assert "prisma" in result.summary["technologies_detected"]

    def test_detects_sqlalchemy_signal(self, artifact_store):
        file_contents = {
            "models.py": "from sqlalchemy import Column, Integer, String\nBase = declarative_base()",
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        assert "sqlalchemy" in result.summary["technologies_detected"]

    def test_detects_firebase_signal(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "stack": {},
            "detected_files": ["lib/firebase_options.dart"],
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        assert "firebase" in result.summary["technologies_detected"]

    def test_flags_missing_indexes(self, artifact_store):
        file_contents = {
            "models.py": """
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String)
    account_id = Column(Integer)
""",
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        index_checks = [c for c in result.checks if c.category == "performance"]
        assert len(index_checks) > 0

    def test_flags_missing_foreign_keys(self, artifact_store):
        file_contents = {
            "models.py": """
class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
""",
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        fk_checks = [c for c in result.checks if c.category == "referential_integrity"]
        assert len(fk_checks) > 0

    def test_flags_dangerous_nullable(self, artifact_store):
        file_contents = {
            "schema.sql": "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER NULLABLE);",
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        nullable_checks = [c for c in result.checks if c.category == "schema_design" and "nullable" in c.title.lower()]
        assert len(nullable_checks) > 0

    def test_flags_missing_updated_at(self, artifact_store):
        file_contents = {
            "models.py": """
class Record(Base):
    __tablename__ = 'records'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime)
""",
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        ts_checks = [c for c in result.checks if "updated_at" in c.title.lower()]
        assert len(ts_checks) > 0

    def test_flags_hard_delete(self, artifact_store):
        file_contents = {
            "models.py": """
def delete_user(session, user_id):
    session.query(User).filter(User.id == user_id).delete()
""",
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        delete_checks = [c for c in result.checks if c.category == "data_safety"]
        assert len(delete_checks) > 0

    def test_no_migration_files_warning(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "stack": {},
            "detected_files": ["models.py", "schema.sql"],
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        migration_checks = [c for c in result.checks if c.category == "migrations"]
        assert len(migration_checks) > 0

    def test_artifacts_written(self, artifact_store):
        agent = DatabaseAuditAgent(artifact_store)
        agent.run(app_map={"metadata": {"app_name": "test"}, "stack": {}, "detected_files": []})

        assert artifact_store.artifact_exists("database_audit_results")

    def test_empty_input(self, artifact_store):
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map={})

        assert result.total_checks >= 0
        assert result.metadata.audit_type == "database_audit"

    def test_pass_rate_property(self, artifact_store):
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map={"metadata": {"app_name": "test"}, "stack": {}, "detected_files": []})

        assert 0.0 <= result.pass_rate <= 1.0

    def test_migration_ordering_warning(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "stack": {},
            "detected_files": [
                "migrations/20240103_init.py",
                "migrations/20240101_create_users.py",
                "migrations/20240102_add_orders.py",
            ],
        }
        agent = DatabaseAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        ordering_checks = [c for c in result.checks if "ordering" in c.title.lower()]
        assert len(ordering_checks) > 0
