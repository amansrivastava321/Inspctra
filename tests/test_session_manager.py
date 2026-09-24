"""
test_session_manager.py - Tests for SessionManager and APISessionManager.
Validates session capture, restore, persistence, and role-based management.
"""

import pytest
from unittest.mock import MagicMock

from qa_ai.live_execution.session_manager import SessionManager, SessionState
from qa_ai.live_execution.api_session_manager import APISessionManager, APISession


class TestSessionManager:
    def test_initializes_with_artifact_store(self, artifact_store):
        manager = SessionManager(artifact_store)
        assert manager.store is artifact_store

    def test_list_sessions_empty(self, artifact_store):
        manager = SessionManager(artifact_store)
        assert manager.list_sessions() == []

    def test_get_nonexistent_session(self, artifact_store):
        manager = SessionManager(artifact_store)
        assert manager.get_session("nonexistent") is None

    def test_session_state_defaults(self):
        state = SessionState(session_id="s1", name="test")
        assert state.session_id == "s1"
        assert state.cookies == []
        assert state.local_storage == {}
        assert state.session_storage == {}

    def test_session_state_to_dict(self):
        state = SessionState(
            session_id="s1",
            name="test",
            cookies=[{"name": "session", "value": "abc123"}],
            local_storage={"token": "xyz"},
            url="http://localhost:3000/dashboard",
        )
        d = state.to_dict()
        assert d["session_id"] == "s1"
        assert d["cookies"] == [{"name": "session", "value": "abc123"}]
        assert d["url"] == "http://localhost:3000/dashboard"

    def test_save_session(self, artifact_store):
        manager = SessionManager(artifact_store)
        # Manually create a session
        state = SessionState(session_id="s1", name="test", url="http://example.com")
        manager._sessions["s1"] = state

        result = manager.save_session("s1")
        assert result is True

    def test_save_nonexistent_session(self, artifact_store):
        manager = SessionManager(artifact_store)
        assert manager.save_session("nonexistent") is False

    def test_restore_session_nonexistent(self, artifact_store):
        manager = SessionManager(artifact_store)
        mock_page = MagicMock()
        result = manager.restore_session(mock_page, "nonexistent")
        assert result is False


class TestAPISessionManager:
    def test_initializes_with_artifact_store(self, artifact_store):
        manager = APISessionManager(artifact_store)
        assert manager.store is artifact_store

    def test_create_session(self, artifact_store):
        manager = APISessionManager(artifact_store)
        session = manager.create_session(
            name="admin-session",
            role="admin",
            base_url="http://localhost:8000",
            token="test-token-123",
        )

        assert session.session_id.startswith("api-session-")
        assert session.role == "admin"
        assert session.token == "test-token-123"

    def test_create_multiple_sessions(self, artifact_store):
        manager = APISessionManager(artifact_store)
        s1 = manager.create_session(role="admin")
        s2 = manager.create_session(role="user")

        assert len(manager.list_sessions()) == 2
        assert s1.session_id != s2.session_id

    def test_get_session(self, artifact_store):
        manager = APISessionManager(artifact_store)
        created = manager.create_session(name="test", role="user")
        retrieved = manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.name == "test"
        assert retrieved.last_used_at is not None

    def test_get_session_by_role(self, artifact_store):
        manager = APISessionManager(artifact_store)
        manager.create_session(role="admin")
        manager.create_session(role="user")
        manager.create_session(role="readonly")

        admin = manager.get_session_by_role("admin")
        assert admin is not None
        assert admin.role == "admin"

    def test_get_session_by_role_not_found(self, artifact_store):
        manager = APISessionManager(artifact_store)
        assert manager.get_session_by_role("nonexistent") is None

    def test_list_roles(self, artifact_store):
        manager = APISessionManager(artifact_store)
        manager.create_session(role="admin")
        manager.create_session(role="user")
        manager.create_session(role="admin")

        roles = manager.list_roles()
        assert "admin" in roles
        assert "user" in roles

    def test_get_auth_header(self):
        session = APISession(
            session_id="s1",
            token="abc123",
            token_type="Bearer",
        )
        header = session.get_auth_header()
        assert header == {"Authorization": "Bearer abc123"}

    def test_get_auth_header_no_token(self):
        session = APISession(session_id="s1")
        assert session.get_auth_header() is None

    def test_save_session(self, artifact_store):
        manager = APISessionManager(artifact_store)
        session = manager.create_session(role="user", token="test-token")
        result = manager.save_session(session.session_id)
        assert result is True

    def test_api_session_to_dict(self):
        session = APISession(
            session_id="s1",
            name="test",
            role="admin",
            base_url="http://localhost:8000",
            token="abc",
        )
        d = session.to_dict()
        assert d["session_id"] == "s1"
        assert d["role"] == "admin"
        assert d["token"] == "abc"

    def test_get_nonexistent_session(self, artifact_store):
        manager = APISessionManager(artifact_store)
        assert manager.get_session("nonexistent") is None
