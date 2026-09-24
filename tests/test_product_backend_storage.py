"""
test_product_backend_storage.py - Unit tests for ProductStorage.

All tests use a temporary SQLite DB (tmp_path fixture).
No real filesystem artifacts required.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from qa_ai.product_backend.storage import ProductStorage


@pytest.fixture
def storage(tmp_path: Path) -> ProductStorage:
    db_path = str(tmp_path / "test.db")
    return ProductStorage(db_path=db_path)


# ── schema idempotency ────────────────────────────────────────────────────────

class TestSchemaIdempotency:
    def test_double_init_no_error(self, tmp_path):
        """Double-initializing the same DB raises no error."""
        db = str(tmp_path / "idem.db")
        s1 = ProductStorage(db_path=db)
        s2 = ProductStorage(db_path=db)
        s2.close()
        s1.close()

    def test_schema_creates_all_tables(self, storage):
        """All expected tables exist after init."""
        tables = [
            r["name"]
            for r in storage._rows_to_list(
                storage._execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
            )
        ]
        expected = {
            "app_targets", "evidence_files", "live_runs",
            "permissions", "projects", "reports",
            "settings", "validation_packs",
        }
        assert expected.issubset(set(tables))

    def test_run_events_schema_and_round_trip(self, storage):
        from qa_ai.product_backend.models import LiveRunRecord

        run = LiveRunRecord(pack_id="pack-1", app_target_id="app-1")
        storage.create_run(run.model_dump())
        columns = {
            row["name"]
            for row in storage._execute("PRAGMA table_info(run_events)").fetchall()
        }
        assert columns == {
            "id", "run_id", "step_index", "step_id", "event_type",
            "message", "payload", "created_at",
        }

        first = storage.create_run_event({
            "run_id": run.id,
            "step_index": 1,
            "step_id": "step-1",
            "event_type": "step_started",
            "message": "Step 1 started",
            "payload": {"status": "running"},
            "created_at": "2026-08-14T00:00:00+00:00",
        })
        storage.create_run_event({
            "run_id": run.id,
            "event_type": "step_completed",
            "message": "Step 1 completed: passed",
            "payload": {"status": "passed"},
            "created_at": "2026-08-14T00:00:01+00:00",
        })

        events = storage.list_run_events(run.id)
        assert events[0]["id"] == first["id"]
        assert [item["event_type"] for item in events] == [
            "step_started", "step_completed",
        ]
        assert events[1]["payload"] == {"status": "passed"}


# ── projects ──────────────────────────────────────────────────────────────────

class TestProjects:
    def _make_project(self, storage, name="Test Project"):
        from qa_ai.product_backend.models import Project
        rec = Project(name=name, description="desc", tags=["alpha", "beta"])
        storage.create_project(rec.model_dump())
        return rec

    def test_create_and_get(self, storage):
        rec = self._make_project(storage)
        row = storage.get_project(rec.id)
        assert row is not None
        assert row["name"] == "Test Project"
        assert row["tags"] == ["alpha", "beta"]

    def test_list_projects(self, storage):
        self._make_project(storage, "A")
        self._make_project(storage, "B")
        rows = storage.list_projects()
        names = {r["name"] for r in rows}
        assert {"A", "B"}.issubset(names)

    def test_update_project(self, storage):
        rec = self._make_project(storage)
        updated = storage.update_project(rec.id, {"name": "Updated", "tags": ["x"]})
        assert updated["name"] == "Updated"
        assert updated["tags"] == ["x"]

    def test_update_nonexistent_returns_none(self, storage):
        result = storage.update_project("nonexistent-id", {"name": "X"})
        assert result is None

    def test_delete_project(self, storage):
        rec = self._make_project(storage)
        assert storage.delete_project(rec.id) is True
        assert storage.get_project(rec.id) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_project("fake-id") is False

    def test_tags_roundtrip_as_list(self, storage):
        """Tags are stored as JSON and returned as Python list."""
        from qa_ai.product_backend.models import Project
        rec = Project(name="TagTest", tags=["foo", "bar", "baz"])
        storage.create_project(rec.model_dump())
        row = storage.get_project(rec.id)
        assert isinstance(row["tags"], list)
        assert set(row["tags"]) == {"foo", "bar", "baz"}


# ── app_targets ───────────────────────────────────────────────────────────────

class TestAppTargets:
    def _make_target(self, storage, project_id, name="My App"):
        from qa_ai.product_backend.models import AppTarget
        rec = AppTarget(
            project_id=project_id,
            name=name,
            app_type="web",
            base_url="http://localhost:3000",
            description="test app",
            tags=["web"],
        )
        storage.create_app_target(rec.model_dump())
        return rec

    def test_create_and_get(self, storage):
        from qa_ai.product_backend.models import Project
        proj = Project(name="P")
        storage.create_project(proj.model_dump())
        rec = self._make_target(storage, proj.id)
        row = storage.get_app_target(rec.id)
        assert row is not None
        assert row["app_type"] == "web"
        assert row["base_url"] == "http://localhost:3000"

    def test_list_by_project(self, storage):
        from qa_ai.product_backend.models import Project
        p1 = Project(name="P1")
        p2 = Project(name="P2")
        storage.create_project(p1.model_dump())
        storage.create_project(p2.model_dump())
        self._make_target(storage, p1.id, "A1")
        self._make_target(storage, p1.id, "A2")
        self._make_target(storage, p2.id, "B1")
        p1_rows = storage.list_app_targets(project_id=p1.id)
        assert len(p1_rows) == 2
        p2_rows = storage.list_app_targets(project_id=p2.id)
        assert len(p2_rows) == 1

    def test_update_target(self, storage):
        from qa_ai.product_backend.models import Project
        proj = Project(name="P")
        storage.create_project(proj.model_dump())
        rec = self._make_target(storage, proj.id)
        updated = storage.update_app_target(rec.id, {"name": "Renamed"})
        assert updated["name"] == "Renamed"

    def test_delete_target(self, storage):
        from qa_ai.product_backend.models import Project
        proj = Project(name="P")
        storage.create_project(proj.model_dump())
        rec = self._make_target(storage, proj.id)
        assert storage.delete_app_target(rec.id) is True
        assert storage.get_app_target(rec.id) is None


# ── validation_packs ──────────────────────────────────────────────────────────

class TestValidationPacks:
    def test_create_with_steps(self, storage):
        from qa_ai.product_backend.models import Project, ValidationPack, ValidationStep
        proj = Project(name="P")
        storage.create_project(proj.model_dump())
        step = ValidationStep(description="Click login", action_type="interact", target="#login")
        pack = ValidationPack(project_id=proj.id, name="Login Pack", steps=[step])
        storage.create_validation_pack(pack.model_dump())
        row = storage.get_validation_pack(pack.id)
        assert row is not None
        assert isinstance(row["steps"], list)
        assert len(row["steps"]) == 1
        assert row["steps"][0]["description"] == "Click login"

    def test_update_steps(self, storage):
        from qa_ai.product_backend.models import Project, ValidationPack, ValidationStep
        proj = Project(name="P")
        storage.create_project(proj.model_dump())
        pack = ValidationPack(project_id=proj.id, name="Pack")
        storage.create_validation_pack(pack.model_dump())
        new_steps = [{"step_id": "s1", "order": 0, "description": "New step", "action_type": "verify", "timeout_seconds": 30}]
        updated = storage.update_validation_pack(pack.id, {"steps": new_steps})
        assert len(updated["steps"]) == 1
        assert updated["steps"][0]["description"] == "New step"

    def test_list_by_project(self, storage):
        from qa_ai.product_backend.models import Project, ValidationPack
        proj = Project(name="P")
        storage.create_project(proj.model_dump())
        for i in range(3):
            p = ValidationPack(project_id=proj.id, name=f"Pack {i}")
            storage.create_validation_pack(p.model_dump())
        rows = storage.list_validation_packs(project_id=proj.id)
        assert len(rows) == 3


# ── live_runs ─────────────────────────────────────────────────────────────────

class TestLiveRuns:
    def test_create_run(self, storage):
        from qa_ai.product_backend.models import LiveRunRecord
        rec = LiveRunRecord(pack_id="p1", app_target_id="a1")
        storage.create_run(rec.model_dump())
        row = storage.get_run(rec.id)
        assert row is not None
        assert row["status"] == "pending"
        assert row["step_results"] == []

    def test_update_run_status(self, storage):
        from qa_ai.product_backend.models import LiveRunRecord
        rec = LiveRunRecord(pack_id="p1", app_target_id="a1")
        storage.create_run(rec.model_dump())
        storage.update_run_status(rec.id, "running", started_at="2024-01-01T00:00:00+00:00")
        row = storage.get_run(rec.id)
        assert row["status"] == "running"
        assert row["started_at"] == "2024-01-01T00:00:00+00:00"

    def test_append_step_result(self, storage):
        from qa_ai.product_backend.models import LiveRunRecord
        rec = LiveRunRecord(pack_id="p1", app_target_id="a1")
        storage.create_run(rec.model_dump())
        storage.append_run_step_result(rec.id, 1, {"status": "passed", "notes": "ok"})
        storage.append_run_step_result(rec.id, 2, {"status": "failed", "notes": "not ok"})
        row = storage.get_run(rec.id)
        assert len(row["step_results"]) == 2
        assert row["step_results"][0]["step"] == 1
        assert row["step_results"][1]["step"] == 2

    def test_cancel_run(self, storage):
        from qa_ai.product_backend.models import LiveRunRecord
        rec = LiveRunRecord(pack_id="p1", app_target_id="a1", status="running")
        storage.create_run(rec.model_dump())
        storage.update_run_status(rec.id, "running")
        assert storage.cancel_run(rec.id) is True
        row = storage.get_run(rec.id)
        assert row["status"] == "cancelled"

    def test_cancel_completed_run_noop(self, storage):
        """cancel_run on an already-completed run returns False."""
        from qa_ai.product_backend.models import LiveRunRecord
        rec = LiveRunRecord(pack_id="p1", app_target_id="a1")
        storage.create_run(rec.model_dump())
        storage.update_run_status(rec.id, "completed")
        assert storage.cancel_run(rec.id) is False

    def test_run_counts(self, storage):
        from qa_ai.product_backend.models import LiveRunRecord
        for status in ["completed", "completed", "failed", "running"]:
            rec = LiveRunRecord(pack_id="p1", app_target_id="a1")
            storage.create_run(rec.model_dump())
            storage.update_run_status(rec.id, status)
        counts = storage.run_counts()
        assert counts.get("completed", 0) == 2
        assert counts.get("failed", 0) == 1
        assert counts.get("running", 0) == 1

    def test_list_runs_limit(self, storage):
        from qa_ai.product_backend.models import LiveRunRecord
        for _ in range(15):
            rec = LiveRunRecord(pack_id="p1", app_target_id="a1")
            storage.create_run(rec.model_dump())
        rows = storage.list_runs(limit=10)
        assert len(rows) == 10


# ── permissions ───────────────────────────────────────────────────────────────

class TestPermissions:
    def test_create_and_resolve(self, storage):
        from qa_ai.product_backend.models import PermissionRecord
        rec = PermissionRecord(run_id="r1", action="launch_browser", description="Open browser")
        storage.create_permission(rec.model_dump())
        row = storage.get_permission(rec.id)
        assert row["status"] == "pending"
        updated = storage.resolve_permission(rec.id, approved=True, reason="User approved")
        assert updated["status"] == "approved"
        assert updated["reason"] == "User approved"

    def test_deny_permission(self, storage):
        from qa_ai.product_backend.models import PermissionRecord
        rec = PermissionRecord(run_id="r1", action="write_file", description="Write artifact")
        storage.create_permission(rec.model_dump())
        updated = storage.resolve_permission(rec.id, approved=False, reason="Denied by policy")
        assert updated["status"] == "denied"

    def test_list_by_status(self, storage):
        from qa_ai.product_backend.models import PermissionRecord
        p1 = PermissionRecord(run_id="r1", action="a1", description="")
        p2 = PermissionRecord(run_id="r1", action="a2", description="")
        storage.create_permission(p1.model_dump())
        storage.create_permission(p2.model_dump())
        storage.resolve_permission(p1.id, approved=True)
        pending = storage.list_permissions(status="pending")
        assert len(pending) == 1
        assert pending[0]["id"] == p2.id


# ── evidence_files ────────────────────────────────────────────────────────────

class TestEvidenceFiles:
    def test_create_and_list(self, storage):
        from qa_ai.product_backend.models import EvidenceFile
        ev = EvidenceFile(
            run_id="r1", name="screenshot.png",
            relative_path="r1/screenshot.png",
            mime_type="image/png", size_bytes=4096,
        )
        storage.create_evidence(ev.model_dump())
        rows = storage.list_evidence(run_id="r1")
        assert len(rows) == 1
        assert rows[0]["name"] == "screenshot.png"
        assert rows[0]["mime_type"] == "image/png"


# ── reports ───────────────────────────────────────────────────────────────────

class TestReports:
    def test_create_and_get(self, storage):
        from qa_ai.product_backend.models import ReportRecord
        rep = ReportRecord(run_id="r1", name="report.json", format="json", relative_path="r1/report.json")
        storage.create_report(rep.model_dump())
        row = storage.get_report(rep.id)
        assert row is not None
        assert row["format"] == "json"


# ── settings ──────────────────────────────────────────────────────────────────

class TestSettings:
    def test_set_and_get(self, storage):
        storage.set_setting("log_level", "DEBUG")
        val = storage.get_setting("log_level")
        assert val == "DEBUG"

    def test_upsert_setting(self, storage):
        storage.set_setting("theme", "dark")
        storage.set_setting("theme", "light")
        assert storage.get_setting("theme") == "light"

    def test_list_settings(self, storage):
        storage.set_setting("log_level", "INFO")
        storage.set_setting("theme", "dark")
        rows = storage.list_settings()
        keys = {r["key"] for r in rows}
        assert {"log_level", "theme"}.issubset(keys)

    def test_missing_key_returns_none(self, storage):
        assert storage.get_setting("nonexistent_key") is None


# ── count_table allowlist ─────────────────────────────────────────────────────

class TestCountTableAllowlist:
    def test_known_table_counts(self, storage):
        assert storage.count_table("projects") == 0

    def test_unknown_table_raises(self, storage):
        with pytest.raises(ValueError, match="unknown table"):
            storage.count_table("DROP TABLE projects; --")

    def test_injection_attempt_raises(self, storage):
        with pytest.raises(ValueError):
            storage.count_table("projects; DROP TABLE projects")


# ── build_update no injection ─────────────────────────────────────────────────

class TestBuildUpdateSafety:
    def test_only_allowed_keys_used(self, storage):
        """_build_update silently ignores keys not in allowed list."""
        sets, params = storage._build_update(
            {"name": "Safe", "evil_field": "injected", "tags": ["a"]},
            allowed=["name", "tags"],
        )
        assert "evil_field" not in sets
        assert "Safe" in params

    def test_empty_fields_returns_empty(self, storage):
        sets, params = storage._build_update({}, allowed=["name"])
        assert sets == ""
        assert params == ()
