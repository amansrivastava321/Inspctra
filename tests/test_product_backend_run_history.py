from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.models import EvidenceFile, LiveRunRecord, Provenance
from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.storage import ProductStorage


@pytest.fixture
def history_env(tmp_path: Path):
    db_path = tmp_path / "history.db"
    app = create_product_app(
        artifacts_dir=str(tmp_path / "artifacts"),
        db_path=str(db_path),
    )
    with TestClient(app) as client:
        yield client, client.app.state.storage, db_path


def _run(
    storage: ProductStorage,
    run_id: str,
    *,
    pack_id: str = "pack-1",
    app_id: str = "app-1",
    status: str = "completed",
    provenance: str = "REAL_EXECUTION",
    execution_mode: str = "automated",
    steps: list[dict] | None = None,
    at: str = "2026-08-01T00:00:00+00:00",
    error: str | None = None,
) -> str:
    record = LiveRunRecord(
        id=run_id,
        pack_id=pack_id,
        app_target_id=app_id,
        status=status,
        execution_mode=execution_mode,
        created_at=at,
        provenance=Provenance(provenance),
    )
    storage.create_run(record.model_dump(mode="json"))
    storage._execute(
        "UPDATE live_runs SET status = ?, started_at = ?, completed_at = ?, "
        "step_results = ?, error = ? WHERE id = ?",
        (
            status,
            at,
            at if status in {"completed", "failed", "cancelled"} else None,
            json.dumps(steps or []),
            error,
            run_id,
        ),
    )
    return run_id


def _step(
    step_id: str | None,
    status: str,
    *,
    provenance: str = "REAL_EXECUTION",
    failure_reason: str | None = None,
    error: str | None = None,
    notes: str | None = None,
    evidence_ids: list[str] | None = None,
) -> dict:
    result = {
        "status": status,
        "provenance": provenance,
        "evidence_ids": evidence_ids or [],
    }
    if step_id is not None:
        result["step_id"] = step_id
    if failure_reason is not None:
        result["failure_reason"] = failure_reason
    if error is not None:
        result["error"] = error
    if notes is not None:
        result["notes"] = notes
    return result


def _get(client: TestClient, run_id: str, limit: int | None = None):
    suffix = "" if limit is None else f"?limit={limit}"
    return client.get(f"/api/runs/{run_id}/history{suffix}")


def _base_history(storage: ProductStorage) -> str:
    _run(storage, "pass-old", steps=[_step("login", "passed")], at="2026-08-01T00:00:00+00:00")
    _run(
        storage,
        "fail-new",
        status="failed",
        steps=[_step("login", "failed", failure_reason="Expected home but was login")],
        at="2026-08-02T00:00:00+00:00",
        error="assertion failed",
    )
    return _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")


def test_unknown_run_returns_404(history_env):
    client, _storage, _db = history_env
    response = _get(client, "missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found."


@pytest.mark.parametrize("limit", [0, -1])
def test_limit_lower_bound_is_validated(history_env, limit):
    client, storage, _db = history_env
    current = _base_history(storage)
    assert _get(client, current, limit).status_code == 422


@pytest.mark.parametrize("limit", [51, 500])
def test_limit_upper_bound_is_validated(history_env, limit):
    client, storage, _db = history_env
    current = _base_history(storage)
    assert _get(client, current, limit).status_code == 422


def test_exact_pack_scope(history_env):
    client, storage, _db = history_env
    current = _base_history(storage)
    _run(storage, "other-pack", pack_id="pack-2", steps=[_step("login", "failed")])
    data = _get(client, current).json()
    assert data["scope"]["pack_id"] == "pack-1"
    assert "other-pack" not in {item["run_id"] for item in data["recent_runs"]}


def test_exact_app_target_scope(history_env):
    client, storage, _db = history_env
    current = _base_history(storage)
    _run(storage, "other-app", app_id="app-2", steps=[_step("login", "failed")])
    data = _get(client, current).json()
    assert data["scope"]["app_target_id"] == "app-1"
    assert "other-app" not in {item["run_id"] for item in data["recent_runs"]}


def test_current_run_is_excluded(history_env):
    client, storage, _db = history_env
    current = _base_history(storage)
    data = _get(client, current).json()
    assert current not in {item["run_id"] for item in data["recent_runs"]}


@pytest.mark.parametrize("active_status", ["pending", "queued", "starting", "running"])
def test_active_runs_are_excluded(history_env, active_status):
    client, storage, _db = history_env
    current = _base_history(storage)
    _run(storage, f"active-{active_status}", status=active_status, at="2026-08-04T00:00:00+00:00")
    ids = {item["run_id"] for item in _get(client, current).json()["recent_runs"]}
    assert f"active-{active_status}" not in ids


def test_last_pass_and_failure_are_latest_admissible_runs(history_env):
    client, storage, _db = history_env
    current = _base_history(storage)
    data = _get(client, current).json()
    assert data["last_passed"]["run_id"] == "pass-old"
    assert data["last_failed"]["run_id"] == "fail-new"
    assert data["last_failed"]["citation"] == {
        "run_id": "fail-new",
        "step_id": None,
        "completed_at": "2026-08-02T00:00:00+00:00",
        "provenance": "REAL_EXECUTION",
        "evidence_ids": [],
    }


def test_step_history_matches_exact_id_across_reordering(history_env):
    client, storage, _db = history_env
    _run(storage, "one", steps=[_step("a", "passed"), _step("b", "failed")])
    _run(storage, "two", steps=[_step("b", "passed"), _step("a", "failed")], at="2026-08-02T00:00:00+00:00")
    current = _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")
    items = {item["step_id"]: item for item in _get(client, current).json()["step_history"]}
    assert items["a"]["passed"] == 1 and items["a"]["failed"] == 1
    assert items["b"]["passed"] == 1 and items["b"]["failed"] == 1


def test_different_step_ids_never_merge(history_env):
    client, storage, _db = history_env
    _run(storage, "one", steps=[_step("old-id", "failed", failure_reason="same text")])
    _run(storage, "two", steps=[_step("new-id", "failed", failure_reason="same text")], at="2026-08-02T00:00:00+00:00")
    current = _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")
    items = {item["step_id"]: item for item in _get(client, current).json()["step_history"]}
    assert items["old-id"]["total"] == 1
    assert items["new-id"]["total"] == 1


def test_missing_step_id_is_insufficient_identity_not_a_match(history_env):
    client, storage, _db = history_env
    _run(storage, "one", steps=[_step(None, "failed")])
    _run(storage, "two", steps=[_step(None, "passed")], at="2026-08-02T00:00:00+00:00")
    current = _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")
    missing = [item for item in _get(client, current).json()["step_history"] if item["step_id"] is None]
    assert len(missing) == 2
    assert all(item["insufficient_identity"] and item["total"] == 1 for item in missing)


@pytest.mark.parametrize(
    ("provenance", "reason"),
    [
        ("DRY_RUN", "dry_run"),
        ("SIMULATED", "simulated"),
        ("DEMO_EXAMPLE", "demo_example"),
        ("UNAVAILABLE", "unavailable_provenance"),
    ],
)
def test_non_real_run_provenance_is_excluded(history_env, provenance, reason):
    client, storage, _db = history_env
    _run(storage, "excluded", provenance=provenance, steps=[_step("a", "passed", provenance=provenance)])
    current = _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")
    data = _get(client, current).json()
    assert data["considered_runs"] == 0
    assert data["excluded_runs"] == 1
    assert data["exclusions_by_reason"][reason] == 1
    assert data["failure_rate"]["total"] == 0


def test_mixed_run_only_contributes_explicit_real_steps(history_env):
    client, storage, _db = history_env
    _run(
        storage,
        "mixed",
        status="failed",
        provenance="MIXED",
        steps=[
            _step("real", "failed", failure_reason="timeout", provenance="REAL_EXECUTION"),
            _step("dry", "passed", provenance="DRY_RUN"),
        ],
    )
    current = _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")
    data = _get(client, current).json()
    assert data["failure_rate"]["total"] == 0
    assert data["exclusions_by_reason"]["mixed_run_level"] == 1
    items = {item["step_id"]: item for item in data["step_history"]}
    assert items["real"]["failed"] == 1
    assert "dry" not in items


def test_manual_observations_are_separate(history_env):
    client, storage, _db = history_env
    _run(storage, "manual", execution_mode="manual", steps=[_step("a", "failed")])
    current = _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")
    data = _get(client, current).json()
    assert data["failure_rate"]["total"] == 0
    assert [item["run_id"] for item in data["manual_observations"]] == ["manual"]
    assert data["exclusions_by_reason"]["manual_execution"] == 1


def test_failure_rate_denominator_uses_only_factual_automated_runs(history_env):
    client, storage, _db = history_env
    current = _base_history(storage)
    _run(storage, "dry", provenance="DRY_RUN", steps=[_step("x", "passed", provenance="DRY_RUN")])
    _run(storage, "cancel", status="cancelled", steps=[_step("x", "passed")])
    data = _get(client, current).json()
    assert data["failure_rate"]["failed"] == 1
    assert data["failure_rate"]["total"] == 2
    assert data["failure_rate"]["value"] == 0.5
    assert {c["run_id"] for c in data["failure_rate"]["citations"]} == {"pass-old", "fail-new"}


def test_repeated_failure_signature_requires_exact_normalized_match(history_env):
    client, storage, _db = history_env
    _run(storage, "one", status="failed", steps=[_step("a", "failed", failure_reason="  TIMEOUT   waiting ")])
    _run(storage, "two", status="failed", steps=[_step("a", "failed", failure_reason="timeout waiting")], at="2026-08-02T00:00:00+00:00")
    _run(storage, "three", status="failed", steps=[_step("a", "failed", failure_reason="timeout loading")], at="2026-08-03T00:00:00+00:00")
    current = _run(storage, "current", status="running", at="2026-08-04T00:00:00+00:00")
    signatures = _get(client, current).json()["repeated_failure_signatures"]
    assert len(signatures) == 1
    assert signatures[0]["occurrences"] == 2
    assert signatures[0]["failure_reason"] == "timeout waiting"
    assert {c["run_id"] for c in signatures[0]["citations"]} == {"one", "two"}


def test_evidence_citations_validate_run_and_step_ownership(history_env):
    client, storage, _db = history_env
    _run(storage, "one", status="failed", steps=[_step("a", "failed", evidence_ids=["owned", "wrong-step", "wrong-run", "missing"])])
    _run(storage, "other", pack_id="other", status="failed", steps=[_step("a", "failed")])
    for evidence_id, run_id, step_id in [
        ("owned", "one", "a"),
        ("wrong-step", "one", "b"),
        ("wrong-run", "other", "a"),
    ]:
        storage.create_evidence(EvidenceFile(
            id=evidence_id,
            run_id=run_id,
            step_id=step_id,
            evidence_type="console",
            name=evidence_id,
            relative_path=f"{evidence_id}.txt",
            provenance=Provenance.REAL_EXECUTION,
        ).model_dump(mode="json"))
    current = _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")
    item = next(i for i in _get(client, current).json()["step_history"] if i["step_id"] == "a")
    assert item["citations"][0]["evidence_ids"] == ["owned"]


def test_ordering_is_deterministic_and_newest_first(history_env):
    client, storage, _db = history_env
    _run(storage, "z", steps=[_step("z-step", "passed")], at="2026-08-01T00:00:00+00:00")
    _run(storage, "a", steps=[_step("a-step", "passed")], at="2026-08-02T00:00:00+00:00")
    current = _run(storage, "current", status="running", at="2026-08-03T00:00:00+00:00")
    first = _get(client, current).json()
    second = _get(client, current).json()
    assert first == second
    assert [r["run_id"] for r in first["recent_runs"]] == ["a", "z"]
    assert [s["step_id"] for s in first["step_history"]] == ["a-step", "z-step"]


def test_maximum_history_bound_is_respected(history_env):
    client, storage, _db = history_env
    for index in range(55):
        _run(storage, f"old-{index:02}", steps=[_step("a", "passed")], at=f"2026-08-{(index % 28) + 1:02}T00:00:00+00:00")
    current = _run(storage, "current", status="running", at="2026-09-01T00:00:00+00:00")
    data = _get(client, current, 50).json()
    assert len(data["recent_runs"]) == 50
    assert data["considered_runs"] == 50


def test_storage_restart_produces_identical_history(tmp_path: Path):
    from qa_ai.product_backend.run_history import build_run_history

    db_path = tmp_path / "restart.db"
    first_storage = ProductStorage(str(db_path))
    _base_history(first_storage)
    first = build_run_history(first_storage, "current", limit=20).model_dump(mode="json")
    first_storage.close()
    second_storage = ProductStorage(str(db_path))
    try:
        second = build_run_history(second_storage, "current", limit=20).model_dump(mode="json")
    finally:
        second_storage.close()
    assert first == second


def test_history_endpoint_produces_zero_mutations(history_env):
    client, storage, _db = history_env
    current = _base_history(storage)
    tables = [
        "live_runs", "evidence_files", "validation_packs", "validation_test_cases",
        "validation_test_steps", "ai_evaluation_notes", "ai_root_cause_analyses",
        "ai_root_cause_suggestions",
    ]
    before = {
        table: [dict(row) for row in storage._execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()]
        for table in tables
    }
    run_before = deepcopy(storage.get_run(current))
    response = _get(client, current)
    after = {
        table: [dict(row) for row in storage._execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()]
        for table in tables
    }
    assert response.status_code == 200
    assert after == before
    assert storage.get_run(current) == run_before


def test_missing_historical_config_snapshot_returns_comparability_warning(history_env):
    client, storage, _db = history_env
    current = _base_history(storage)
    data = _get(client, current).json()
    assert data["scope"]["configuration_snapshot_available"] is False
    assert data["comparability_warnings"]
    assert "configuration" in data["comparability_warnings"][0].lower()


def test_history_indexes_are_idempotently_installed(history_env):
    _client, storage, db_path = history_env
    indexes = {row["name"] for row in storage._execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
    assert {
        "idx_live_runs_pack_app_created",
        "idx_live_runs_retest_parent",
        "idx_evidence_run_step_created",
    }.issubset(indexes)
    ProductStorage(str(db_path)).close()


def test_history_indexes_migrate_legacy_additive_columns(tmp_path: Path):
    db_path = tmp_path / "legacy-history.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE live_runs (id TEXT PRIMARY KEY, pack_id TEXT NOT NULL, "
        "app_target_id TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT, "
        "completed_at TEXT, step_results TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE evidence_files (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
        "name TEXT NOT NULL, relative_path TEXT NOT NULL, mime_type TEXT NOT NULL, "
        "size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL)"
    )
    connection.commit()
    connection.close()

    storage = ProductStorage(str(db_path))
    try:
        columns = {
            row["name"]
            for row in storage._execute("PRAGMA table_info(live_runs)").fetchall()
        }
        indexes = {
            row["name"]
            for row in storage._execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "retest_of" in columns
        assert {
            "idx_live_runs_pack_app_created",
            "idx_live_runs_retest_parent",
            "idx_evidence_run_step_created",
        }.issubset(indexes)
    finally:
        storage.close()
