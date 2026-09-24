"""
storage.py - SQLite persistence layer for the product backend.

Security:
- ALL queries use ? parameterized placeholders. Zero f-string interpolation of user data.
- Thread-safe: RLock + check_same_thread=False.
- Idempotent schema: CREATE TABLE IF NOT EXISTS.
- JSON columns for list/dict fields.
- Caller cannot inject SQL through any public method.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.product_backend.models import MAX_RETEST_LINEAGE_DEPTH, Provenance

# Defensive traversal cap for get_retest_lineage_info(). Legitimate chains
# are always <= MAX_RETEST_LINEAGE_DEPTH hops (every hop was itself checked
# against that limit); this buffer only bounds the walk against corrupted
# or cyclic retest_of data so it can never loop unboundedly.
_LINEAGE_TRAVERSAL_BUFFER = 5

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── schema ─────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    provenance  TEXT NOT NULL DEFAULT 'UNAVAILABLE'
);

CREATE TABLE IF NOT EXISTS app_targets (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    app_type    TEXT NOT NULL,
    base_url    TEXT,
    description TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    provenance  TEXT NOT NULL DEFAULT 'UNAVAILABLE'
);

CREATE TABLE IF NOT EXISTS validation_packs (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    steps       TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    provenance  TEXT NOT NULL DEFAULT 'UNAVAILABLE'
);

CREATE TABLE IF NOT EXISTS live_runs (
    id             TEXT PRIMARY KEY,
    pack_id        TEXT NOT NULL,
    app_target_id  TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    started_at     TEXT,
    completed_at   TEXT,
    step_results   TEXT NOT NULL DEFAULT '[]',
    error          TEXT,
    created_at     TEXT NOT NULL,
    retest_of      TEXT,
    execution_mode TEXT NOT NULL DEFAULT 'automated',
    provenance     TEXT NOT NULL DEFAULT 'UNAVAILABLE',
    retest_selection_json TEXT
);

CREATE TABLE IF NOT EXISTS run_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    step_index  INTEGER,
    step_id     TEXT,
    event_type  TEXT NOT NULL,
    message     TEXT NOT NULL DEFAULT '',
    payload     TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES live_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_created
ON run_events(run_id, created_at, id);

CREATE TABLE IF NOT EXISTS permissions (
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    action       TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    risk         TEXT NOT NULL DEFAULT 'medium',
    status       TEXT NOT NULL DEFAULT 'pending',
    requested_at TEXT NOT NULL,
    resolved_at  TEXT,
    reason       TEXT
);

CREATE TABLE IF NOT EXISTS evidence_files (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL,
    step_id       TEXT,
    type          TEXT,
    name          TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    mime_type     TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    sha256        TEXT,
    metadata_json TEXT,
    created_at    TEXT NOT NULL,
    provenance    TEXT NOT NULL DEFAULT 'UNAVAILABLE'
);

CREATE TABLE IF NOT EXISTS reports (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL,
    name          TEXT NOT NULL,
    format        TEXT NOT NULL DEFAULT 'json',
    relative_path TEXT NOT NULL DEFAULT '',
    summary_json  TEXT,
    created_at    TEXT NOT NULL,
    provenance    TEXT NOT NULL DEFAULT 'UNAVAILABLE'
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_test_plans (
    plan_id          TEXT PRIMARY KEY,
    pack_id          TEXT NOT NULL,
    app_id           TEXT,
    generated_from   TEXT NOT NULL DEFAULT 'generic_app_type_template',
    coverage_summary TEXT NOT NULL DEFAULT '{}',
    risk_summary     TEXT NOT NULL DEFAULT '{}',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_test_cases (
    test_case_id      TEXT PRIMARY KEY,
    plan_id           TEXT NOT NULL,
    pack_id           TEXT NOT NULL,
    app_id            TEXT,
    flow_name         TEXT NOT NULL DEFAULT '',
    title             TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    test_type         TEXT NOT NULL DEFAULT 'positive',
    priority          TEXT NOT NULL DEFAULT 'P1',
    risk_level        TEXT NOT NULL DEFAULT 'medium',
    preconditions     TEXT NOT NULL DEFAULT '[]',
    steps             TEXT NOT NULL DEFAULT '[]',
    expected_result   TEXT NOT NULL DEFAULT '',
    expected_evidence TEXT NOT NULL DEFAULT '[]',
    pass_criteria     TEXT NOT NULL DEFAULT '',
    fail_criteria     TEXT NOT NULL DEFAULT '',
    automation_status TEXT NOT NULL DEFAULT 'needs_selector',
    safety_level      TEXT NOT NULL DEFAULT 'safe',
    requires_permission INTEGER NOT NULL DEFAULT 0,
    tags              TEXT NOT NULL DEFAULT '[]',
    enabled           INTEGER NOT NULL DEFAULT 1,
    confidence        REAL,
    rationale         TEXT,
    generated_by      TEXT,
    generation_source TEXT,
    generation_metadata_json TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_test_steps (
    step_id         TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL,
    step_order      INTEGER NOT NULL,
    action_type     TEXT NOT NULL,
    target          TEXT,
    value           TEXT,
    expected        TEXT,
    method          TEXT,
    url             TEXT,
    headers_json    TEXT,
    query_params_json TEXT,
    body_json       TEXT,
    expected_status INTEGER,
    expected_json_path TEXT,
    expected_value  TEXT,
    timeout_ms      INTEGER NOT NULL DEFAULT 30000,
    optional        INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    budget_ms       INTEGER,
    warn_ms         INTEGER,
    metric_name     TEXT,
    confidence      REAL,
    rationale       TEXT,
    generated_by    TEXT,
    generation_source TEXT,
    generation_metadata_json TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES validation_test_cases(test_case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_providers (
    provider_id   TEXT PRIMARY KEY,
    provider_type TEXT NOT NULL,
    name          TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 0,
    base_url      TEXT,
    api_key_env   TEXT,
    secret_ref    TEXT,
    allow_cloud   INTEGER NOT NULL DEFAULT 0,
    local_only    INTEGER NOT NULL DEFAULT 1,
    metadata      TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_routes (
    id                  TEXT PRIMARY KEY,
    task                TEXT NOT NULL,
    provider_id         TEXT NOT NULL,
    model               TEXT NOT NULL,
    priority            INTEGER NOT NULL DEFAULT 1,
    enabled             INTEGER NOT NULL DEFAULT 1,
    fallback_models     TEXT NOT NULL DEFAULT '[]',
    temperature         REAL NOT NULL DEFAULT 0.1,
    timeout_seconds     INTEGER NOT NULL DEFAULT 60,
    estimated_memory_gb REAL NOT NULL DEFAULT 4.0,
    local_only          INTEGER NOT NULL DEFAULT 1,
    requires_approval   INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_usage_events (
    id            TEXT PRIMARY KEY,
    task          TEXT NOT NULL,
    provider_id   TEXT NOT NULL,
    model         TEXT NOT NULL,
    latency_ms    REAL NOT NULL DEFAULT 0.0,
    status        TEXT NOT NULL DEFAULT 'ok',
    fallback_used INTEGER NOT NULL DEFAULT 0,
    tokens_in     INTEGER NOT NULL DEFAULT 0,
    tokens_out    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_discovery_results (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    local_path      TEXT,
    url             TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    result_json     TEXT NOT NULL DEFAULT '{}',
    error_message   TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_maps (
    app_map_id  TEXT PRIMARY KEY,
    app_id      TEXT NOT NULL,
    discovery_id TEXT,
    map_type    TEXT NOT NULL DEFAULT 'fingerprint_based_draft',
    data_json   TEXT NOT NULL DEFAULT '{}',
    confidence  TEXT NOT NULL DEFAULT 'low',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS visual_baselines (
    id            TEXT PRIMARY KEY,
    app_id        TEXT NOT NULL,
    pack_id       TEXT,
    test_case_id  TEXT,
    step_id       TEXT NOT NULL,
    name          TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    baseline_path TEXT,
    width         INTEGER,
    height        INTEGER,
    sha256        TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_evaluation_notes (
    evaluation_id            TEXT PRIMARY KEY,
    run_id                   TEXT NOT NULL,
    step_id                  TEXT,
    verdict_assessment       TEXT NOT NULL,
    suggested_verdict        TEXT,
    confidence               REAL NOT NULL,
    summary                  TEXT NOT NULL,
    evidence_used            TEXT NOT NULL,
    missing_evidence         TEXT NOT NULL,
    risk_flags               TEXT NOT NULL,
    rationale                TEXT NOT NULL,
    generation_source        TEXT NOT NULL,
    generation_metadata_json TEXT,
    created_at               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_root_cause_analyses (
    analysis_id              TEXT PRIMARY KEY,
    run_id                   TEXT NOT NULL,
    status                   TEXT NOT NULL CHECK (status IN ('suggested', 'inconclusive')),
    authoritative            INTEGER NOT NULL DEFAULT 0 CHECK (authoritative = 0),
    source_provenance        TEXT NOT NULL DEFAULT 'UNAVAILABLE',
    generation_source        TEXT NOT NULL,
    generation_metadata_json TEXT NOT NULL DEFAULT '{}',
    missing_evidence         TEXT NOT NULL DEFAULT '[]',
    created_at               TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES live_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_ai_rca_analysis_run_created
ON ai_root_cause_analyses(run_id, created_at);

CREATE TABLE IF NOT EXISTS ai_root_cause_suggestions (
    suggestion_id            TEXT PRIMARY KEY,
    analysis_id              TEXT NOT NULL,
    run_id                   TEXT NOT NULL,
    step_id                  TEXT,
    rank                     INTEGER NOT NULL CHECK (rank >= 1),
    title                    TEXT NOT NULL,
    possible_cause           TEXT NOT NULL,
    category                 TEXT NOT NULL,
    confidence               REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence_refs            TEXT NOT NULL DEFAULT '[]',
    supporting_signals       TEXT NOT NULL DEFAULT '[]',
    contradicting_signals    TEXT NOT NULL DEFAULT '[]',
    missing_evidence         TEXT NOT NULL DEFAULT '[]',
    recommended_verification TEXT NOT NULL DEFAULT '[]',
    suggested_owner_area     TEXT NOT NULL DEFAULT 'unknown',
    source_provenance        TEXT NOT NULL DEFAULT 'UNAVAILABLE',
    generation_source        TEXT NOT NULL,
    generation_metadata_json TEXT NOT NULL DEFAULT '{}',
    authoritative            INTEGER NOT NULL DEFAULT 0 CHECK (authoritative = 0),
    created_at               TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES live_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_ai_rca_run_created
ON ai_root_cause_suggestions(run_id, created_at, rank);
"""


class ActiveRetestChildError(Exception):
    """Raised when a retest child would be created for a parent that already
    has a non-terminal (pending/running) retest child."""

    def __init__(self, parent_run_id: str, active_run_id: str):
        super().__init__(
            f"Parent run {parent_run_id!r} already has an active retest child {active_run_id!r}."
        )
        self.parent_run_id = parent_run_id
        self.active_run_id = active_run_id


class RetestLineageInvalidError(Exception):
    """Raised when a parent's retest_of chain contains a cycle, a broken
    reference, or exceeds the defensive traversal cap. The lineage cannot be
    safely resolved, so it must not be extended with a new child."""

    def __init__(self, parent_run_id: str):
        super().__init__(
            f"Retest lineage for parent {parent_run_id!r} is invalid and cannot be extended."
        )
        self.parent_run_id = parent_run_id


class RetestLineageDepthExceededError(Exception):
    """Raised when parent depth + 1 would exceed MAX_RETEST_LINEAGE_DEPTH."""

    def __init__(self, parent_run_id: str, attempted_depth: int):
        super().__init__(
            f"Parent {parent_run_id!r} is at a depth that would make the new "
            f"child's depth {attempted_depth}, exceeding MAX_RETEST_LINEAGE_DEPTH."
        )
        self.parent_run_id = parent_run_id
        self.attempted_depth = attempted_depth


class ProductStorage:
    """
    Thread-safe SQLite CRUD for the product backend.

    All public methods use ? parameterized queries.
    Never accept raw SQL from callers.
    """

    def __init__(self, db_path: str = "artifacts/inspectra_product.db") -> None:
        self._db_path = str(Path(db_path).resolve())
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._get_conn()
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Additive schema migrations — safe to run on existing DBs."""
        provenance_tables = (
            "projects",
            "app_targets",
            "validation_packs",
            "live_runs",
            "evidence_files",
            "reports",
        )
        with self._lock:
            conn = self._get_conn()
            for table in provenance_tables:
                columns = {
                    row["name"]
                    for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                }
                if "provenance" in columns:
                    continue
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN provenance "
                    "TEXT NOT NULL DEFAULT 'UNAVAILABLE'"
                )
                if table == "live_runs":
                    # Existing runs with durable evidence were produced by a real
                    # execution path before provenance was introduced.
                    conn.execute(
                        "UPDATE live_runs SET provenance = 'REAL_EXECUTION' "
                        "WHERE EXISTS ("
                        "SELECT 1 FROM evidence_files WHERE evidence_files.run_id = live_runs.id"
                        ")"
                    )
            conn.commit()

        migrations = [
            "ALTER TABLE reports ADD COLUMN summary_json TEXT",
            "ALTER TABLE live_runs ADD COLUMN retest_of TEXT",
            # Durable record of which stable step_ids a retest child requested/
            # resolved, so retest correctness never depends on re-deriving it.
            "ALTER TABLE live_runs ADD COLUMN retest_selection_json TEXT",
            # Validation pack app linkage
            "ALTER TABLE validation_packs ADD COLUMN app_id TEXT",
            # App discovery source fields
            "ALTER TABLE app_targets ADD COLUMN source_type TEXT",
            "ALTER TABLE app_targets ADD COLUMN source_path TEXT",
            "ALTER TABLE app_targets ADD COLUMN source_url TEXT",
            "ALTER TABLE app_targets ADD COLUMN launch_command TEXT",
            "ALTER TABLE app_targets ADD COLUMN working_directory TEXT",
            "ALTER TABLE app_targets ADD COLUMN discovery_id TEXT",
            "ALTER TABLE app_targets ADD COLUMN detected_stack TEXT",
            "ALTER TABLE evidence_files ADD COLUMN step_id TEXT",
            "ALTER TABLE evidence_files ADD COLUMN type TEXT",
            "ALTER TABLE evidence_files ADD COLUMN sha256 TEXT",
            "ALTER TABLE evidence_files ADD COLUMN metadata_json TEXT",
            # Deterministic historical-run lookup indexes. Keep these after
            # additive column migrations so legacy databases initialize safely.
            "CREATE INDEX IF NOT EXISTS idx_live_runs_pack_app_created "
            "ON live_runs(pack_id, app_target_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_live_runs_retest_parent "
            "ON live_runs(retest_of, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_evidence_run_step_created "
            "ON evidence_files(run_id, step_id, created_at DESC)",
            # Validation test steps table creation for migration
            "CREATE TABLE IF NOT EXISTS validation_test_steps ("
            "    step_id         TEXT PRIMARY KEY,"
            "    case_id         TEXT NOT NULL,"
            "    step_order      INTEGER NOT NULL,"
            "    action_type     TEXT NOT NULL,"
            "    target          TEXT,"
            "    value           TEXT,"
            "    expected        TEXT,"
            "    method          TEXT,"
            "    url             TEXT,"
            "    headers_json    TEXT,"
            "    query_params_json TEXT,"
            "    body_json       TEXT,"
            "    expected_status INTEGER,"
            "    expected_json_path TEXT,"
            "    expected_value  TEXT,"
            "    timeout_ms      INTEGER NOT NULL DEFAULT 30000,"
            "    optional        INTEGER NOT NULL DEFAULT 0,"
            "    notes           TEXT,"
            "    created_at      TEXT NOT NULL,"
            "    updated_at      TEXT NOT NULL,"
            "    FOREIGN KEY(case_id) REFERENCES validation_test_cases(test_case_id) ON DELETE CASCADE"
            ")",
            "ALTER TABLE live_runs ADD COLUMN execution_mode TEXT DEFAULT 'automated'",
            "ALTER TABLE validation_test_steps ADD COLUMN method TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN url TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN headers_json TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN query_params_json TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN body_json TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN expected_status INTEGER",
            "ALTER TABLE validation_test_steps ADD COLUMN expected_json_path TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN expected_value TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN budget_ms INTEGER",
            "ALTER TABLE validation_test_steps ADD COLUMN warn_ms INTEGER",
            "ALTER TABLE validation_test_steps ADD COLUMN metric_name TEXT",
            "CREATE TABLE IF NOT EXISTS visual_baselines (id TEXT PRIMARY KEY, app_id TEXT NOT NULL, step_id TEXT NOT NULL, name TEXT NOT NULL, relative_path TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
            "ALTER TABLE visual_baselines ADD COLUMN pack_id TEXT",
            "ALTER TABLE visual_baselines ADD COLUMN test_case_id TEXT",
            "ALTER TABLE visual_baselines ADD COLUMN baseline_path TEXT",
            "ALTER TABLE visual_baselines ADD COLUMN width INTEGER",
            "ALTER TABLE visual_baselines ADD COLUMN height INTEGER",
            "ALTER TABLE visual_baselines ADD COLUMN sha256 TEXT",
            "ALTER TABLE validation_test_cases ADD COLUMN confidence REAL",
            "ALTER TABLE validation_test_cases ADD COLUMN rationale TEXT",
            "ALTER TABLE validation_test_cases ADD COLUMN generated_by TEXT",
            "ALTER TABLE validation_test_cases ADD COLUMN generation_source TEXT",
            "ALTER TABLE validation_test_cases ADD COLUMN generation_metadata_json TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN confidence REAL",
            "ALTER TABLE validation_test_steps ADD COLUMN rationale TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN generated_by TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN generation_source TEXT",
            "ALTER TABLE validation_test_steps ADD COLUMN generation_metadata_json TEXT",
            # Schedule columns for validation packs
            "ALTER TABLE validation_packs ADD COLUMN schedule TEXT NOT NULL DEFAULT 'none'",
            "ALTER TABLE validation_packs ADD COLUMN schedule_enabled INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE validation_packs ADD COLUMN next_run_at TEXT",
            "ALTER TABLE validation_packs ADD COLUMN last_scheduled_run_at TEXT",
            "CREATE TABLE IF NOT EXISTS ai_evaluation_notes ("
            "    evaluation_id            TEXT PRIMARY KEY,"
            "    run_id                   TEXT NOT NULL,"
            "    step_id                  TEXT,"
            "    verdict_assessment       TEXT NOT NULL,"
            "    suggested_verdict        TEXT,"
            "    confidence               REAL NOT NULL,"
            "    summary                  TEXT NOT NULL,"
            "    evidence_used            TEXT NOT NULL,"
            "    missing_evidence         TEXT NOT NULL,"
            "    risk_flags               TEXT NOT NULL,"
            "    rationale                TEXT NOT NULL,"
            "    generation_source        TEXT NOT NULL,"
            "    generation_metadata_json TEXT,"
            "    created_at               TEXT NOT NULL"
            ")",
            "CREATE TABLE IF NOT EXISTS ai_root_cause_suggestions ("
            "    suggestion_id            TEXT PRIMARY KEY,"
            "    analysis_id              TEXT NOT NULL,"
            "    run_id                   TEXT NOT NULL,"
            "    step_id                  TEXT,"
            "    rank                     INTEGER NOT NULL CHECK (rank >= 1),"
            "    title                    TEXT NOT NULL,"
            "    possible_cause           TEXT NOT NULL,"
            "    category                 TEXT NOT NULL,"
            "    confidence               REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),"
            "    evidence_refs            TEXT NOT NULL DEFAULT '[]',"
            "    supporting_signals       TEXT NOT NULL DEFAULT '[]',"
            "    contradicting_signals    TEXT NOT NULL DEFAULT '[]',"
            "    missing_evidence         TEXT NOT NULL DEFAULT '[]',"
            "    recommended_verification TEXT NOT NULL DEFAULT '[]',"
            "    suggested_owner_area     TEXT NOT NULL DEFAULT 'unknown',"
            "    source_provenance        TEXT NOT NULL DEFAULT 'UNAVAILABLE',"
            "    generation_source        TEXT NOT NULL,"
            "    generation_metadata_json TEXT NOT NULL DEFAULT '{}',"
            "    authoritative            INTEGER NOT NULL DEFAULT 0 CHECK (authoritative = 0),"
            "    created_at               TEXT NOT NULL,"
            "    FOREIGN KEY (run_id) REFERENCES live_runs(id)"
            ")",
            "CREATE INDEX IF NOT EXISTS idx_ai_rca_run_created "
            "ON ai_root_cause_suggestions(run_id, created_at, rank)",
            "CREATE TABLE IF NOT EXISTS ai_root_cause_analyses ("
            "    analysis_id              TEXT PRIMARY KEY,"
            "    run_id                   TEXT NOT NULL,"
            "    status                   TEXT NOT NULL CHECK (status IN ('suggested', 'inconclusive')),"
            "    authoritative            INTEGER NOT NULL DEFAULT 0 CHECK (authoritative = 0),"
            "    source_provenance        TEXT NOT NULL DEFAULT 'UNAVAILABLE',"
            "    generation_source        TEXT NOT NULL,"
            "    generation_metadata_json TEXT NOT NULL DEFAULT '{}',"
            "    missing_evidence         TEXT NOT NULL DEFAULT '[]',"
            "    created_at               TEXT NOT NULL,"
            "    FOREIGN KEY (run_id) REFERENCES live_runs(id)"
            ")",
            "CREATE INDEX IF NOT EXISTS idx_ai_rca_analysis_run_created "
            "ON ai_root_cause_analyses(run_id, created_at)",
        ]
        with self._lock:
            conn = self._get_conn()
            for sql in migrations:
                try:
                    conn.execute(sql)
                    conn.commit()
                except Exception:
                    pass  # Column already exists

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                isolation_level=None,  # autocommit; we manage transactions manually
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ── helpers ───────────────────────────────────────────────────────────────

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute one parameterized query. Thread-safe."""
        with self._lock:
            return self._get_conn().execute(sql, params)

    def _executemany(self, sql: str, params_seq: list) -> None:
        with self._lock:
            self._get_conn().executemany(sql, params_seq)

    @staticmethod
    def _j(val: Any) -> str:
        """Serialize to JSON string for TEXT columns."""
        return json.dumps(val, default=str)

    @staticmethod
    def _uj(val: Optional[str]) -> Any:
        """Deserialize from TEXT JSON column."""
        if val is None:
            return None
        try:
            return json.loads(val)
        except Exception:
            return val

    @staticmethod
    def _provenance_value(value: Any) -> str:
        """Return a valid persisted enum value, defaulting safely."""
        try:
            return Provenance(value or Provenance.UNAVAILABLE).value
        except ValueError:
            return Provenance.UNAVAILABLE.value

    @staticmethod
    def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return dict(row)

    def _rows_to_list(self, cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        return [dict(r) for r in cursor.fetchall()]

    def _select_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def _select_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ── projects ──────────────────────────────────────────────────────────────

    def create_project(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        self._execute(
            "INSERT INTO projects (id, name, description, tags, created_at, updated_at, provenance) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                rec["id"], rec["name"], rec.get("description", ""),
                self._j(rec.get("tags", [])), rec["created_at"], rec["updated_at"],
                self._provenance_value(rec.get("provenance")),
            ),
        )
        return rec

    def list_projects(self) -> List[Dict[str, Any]]:
        rows = self._rows_to_list(self._execute("SELECT * FROM projects ORDER BY created_at DESC"))
        for r in rows:
            r["tags"] = self._uj(r.get("tags")) or []
            r["provenance"] = self._provenance_value(r.get("provenance"))
        return rows

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(
            self._execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        )
        if row:
            row["tags"] = self._uj(row.get("tags")) or []
            row["provenance"] = self._provenance_value(row.get("provenance"))
        return row

    def update_project(self, project_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sets, params = self._build_update(fields, ["name", "description", "tags", "provenance"])
        if not sets:
            return self.get_project(project_id)
        self._execute(
            f"UPDATE projects SET {sets}, updated_at = ? WHERE id = ?",
            params + (_now_iso(), project_id),
        )
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        cur = self._execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cur.rowcount > 0

    def count_apps_for_project(self, project_id: str) -> int:
        row = self._execute(
            "SELECT COUNT(*) FROM app_targets WHERE project_id = ?", (project_id,)
        ).fetchone()
        return int(row[0]) if row else 0

    def count_packs_for_project(self, project_id: str) -> int:
        row = self._execute(
            "SELECT COUNT(*) FROM validation_packs WHERE project_id = ?", (project_id,)
        ).fetchone()
        return int(row[0]) if row else 0

    def delete_e2e_test_data(self) -> dict:
        """Delete all records with names starting 'E2E-'. Reserved prefix for test data."""
        cur = self._execute(
            "DELETE FROM app_targets WHERE project_id IN "
            "(SELECT id FROM projects WHERE name LIKE ?) OR name LIKE ?",
            ("E2E-%", "E2E-%"),
        )
        apps_deleted = cur.rowcount
        cur = self._execute(
            "DELETE FROM validation_packs WHERE project_id IN "
            "(SELECT id FROM projects WHERE name LIKE ?) OR name LIKE ?",
            ("E2E-%", "E2E-%"),
        )
        packs_deleted = cur.rowcount
        cur = self._execute("DELETE FROM projects WHERE name LIKE ?", ("E2E-%",))
        projects_deleted = cur.rowcount
        return {"projects": projects_deleted, "apps": apps_deleted, "packs": packs_deleted}

    # ── app_targets ───────────────────────────────────────────────────────────

    def create_app_target(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        self._execute(
            "INSERT INTO app_targets "
            "(id, project_id, name, app_type, base_url, description, tags, "
            "source_type, source_path, source_url, launch_command, working_directory, "
            "discovery_id, detected_stack, created_at, updated_at, provenance) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["id"], rec["project_id"], rec["name"], rec["app_type"],
                rec.get("base_url"), rec.get("description", ""),
                self._j(rec.get("tags", [])),
                rec.get("source_type"), rec.get("source_path"), rec.get("source_url"),
                rec.get("launch_command"), rec.get("working_directory"),
                rec.get("discovery_id"), rec.get("detected_stack"),
                rec["created_at"], rec["updated_at"],
                self._provenance_value(rec.get("provenance")),
            ),
        )
        return rec

    def list_app_targets(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if project_id:
            rows = self._rows_to_list(
                self._execute(
                    "SELECT * FROM app_targets WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                )
            )
        else:
            rows = self._rows_to_list(
                self._execute("SELECT * FROM app_targets ORDER BY created_at DESC")
            )
        for r in rows:
            r["tags"] = self._uj(r.get("tags")) or []
            r["provenance"] = self._provenance_value(r.get("provenance"))
        return rows

    def get_app_target(self, target_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(
            self._execute("SELECT * FROM app_targets WHERE id = ?", (target_id,)).fetchone()
        )
        if row:
            row["tags"] = self._uj(row.get("tags")) or []
            row["provenance"] = self._provenance_value(row.get("provenance"))
        return row

    def update_app_target(self, target_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sets, params = self._build_update(
            fields, [
                "name", "app_type", "base_url", "description", "tags",
                "source_type", "source_path", "source_url",
                "launch_command", "working_directory", "discovery_id", "detected_stack",
                "provenance",
            ]
        )
        if not sets:
            return self.get_app_target(target_id)
        self._execute(
            f"UPDATE app_targets SET {sets}, updated_at = ? WHERE id = ?",
            params + (_now_iso(), target_id),
        )
        return self.get_app_target(target_id)

    def delete_app_target(self, target_id: str) -> bool:
        cur = self._execute("DELETE FROM app_targets WHERE id = ?", (target_id,))
        return cur.rowcount > 0

    # ── app_discovery_results ─────────────────────────────────────────────────

    def save_discovery_result(self, result: Any) -> None:
        """
        Persist a DiscoveryResult (Pydantic model or dict).
        Full result serialized as result_json for forward compatibility.
        """
        if hasattr(result, "model_dump"):
            data = result.model_dump()
        else:
            data = dict(result)
        self._execute(
            "INSERT OR REPLACE INTO app_discovery_results "
            "(id, project_id, source_type, local_path, url, status, result_json, "
            "error_message, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["id"], data["project_id"], data["source_type"],
                data.get("local_path"), data.get("url"),
                data.get("status", "pending"),
                self._j(data),
                data.get("error_message"),
                data.get("created_at", _now_iso()),
                data.get("updated_at", _now_iso()),
            ),
        )

    def get_discovery_result(self, discovery_id: str) -> Optional[Any]:
        """Return DiscoveryResult as Pydantic model, or None if not found."""
        from qa_ai.product_backend.discovery_models import DiscoveryResult
        row = self._row_to_dict(
            self._execute(
                "SELECT * FROM app_discovery_results WHERE id = ?", (discovery_id,)
            ).fetchone()
        )
        if row is None:
            return None
        full_data = self._uj(row.get("result_json")) or {}
        if not full_data:
            # Fallback: reconstruct from row columns
            full_data = {
                "id": row["id"], "project_id": row["project_id"],
                "source_type": row["source_type"], "local_path": row.get("local_path"),
                "url": row.get("url"), "status": row.get("status", "pending"),
                "error_message": row.get("error_message"),
                "created_at": row.get("created_at", ""), "updated_at": row.get("updated_at", ""),
            }
        return DiscoveryResult(**full_data)

    # ── app_maps ──────────────────────────────────────────────────────────────

    def save_app_map(self, app_map: Any) -> None:
        """Persist an AppMapDraft (Pydantic model or dict). Upsert by app_map_id."""
        if hasattr(app_map, "model_dump"):
            data = app_map.model_dump()
        else:
            data = dict(app_map)
        self._execute(
            "INSERT OR REPLACE INTO app_maps "
            "(app_map_id, app_id, discovery_id, map_type, data_json, confidence, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["app_map_id"], data["app_id"], data.get("discovery_id"),
                data.get("map_type", "fingerprint_based_draft"),
                self._j(data),
                data.get("confidence", "low"),
                data.get("created_at", _now_iso()),
                data.get("updated_at", _now_iso()),
            ),
        )

    def get_app_map_for_app(self, app_id: str) -> Optional[Any]:
        """Return latest AppMapDraft for an app, or None."""
        from qa_ai.product_backend.app_map_models import AppMapDraft
        row = self._row_to_dict(
            self._execute(
                "SELECT * FROM app_maps WHERE app_id = ? ORDER BY created_at DESC LIMIT 1",
                (app_id,),
            ).fetchone()
        )
        if row is None:
            return None
        data = self._uj(row.get("data_json")) or {}
        if not data:
            return None
        return AppMapDraft(**data)

    def list_app_maps(self, app_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if app_id:
            rows = self._rows_to_list(
                self._execute(
                    "SELECT * FROM app_maps WHERE app_id = ? ORDER BY created_at DESC",
                    (app_id,),
                )
            )
        else:
            rows = self._rows_to_list(
                self._execute("SELECT * FROM app_maps ORDER BY created_at DESC")
            )
        # Parse data_json for each row
        result = []
        for r in rows:
            data = self._uj(r.get("data_json")) or {}
            if data:
                result.append(data)
        return result

    # ── validation_packs ──────────────────────────────────────────────────────

    def create_validation_pack(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        self._execute(
            "INSERT INTO validation_packs "
            "(id, project_id, name, description, steps, app_id, schedule, schedule_enabled, next_run_at, last_scheduled_run_at, created_at, updated_at, provenance) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["id"], rec["project_id"], rec["name"],
                rec.get("description", ""), self._j(rec.get("steps", [])),
                rec.get("app_id"),
                rec.get("schedule") or "none",
                1 if rec.get("schedule_enabled") else 0,
                rec.get("next_run_at"),
                rec.get("last_scheduled_run_at"),
                rec["created_at"], rec["updated_at"],
                self._provenance_value(rec.get("provenance")),
            ),
        )
        return rec

    def list_validation_packs(
        self,
        project_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if project_id and app_id:
            rows = self._rows_to_list(
                self._execute(
                    "SELECT * FROM validation_packs WHERE project_id = ? AND app_id = ? ORDER BY created_at DESC",
                    (project_id, app_id),
                )
            )
        elif project_id:
            rows = self._rows_to_list(
                self._execute(
                    "SELECT * FROM validation_packs WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                )
            )
        elif app_id:
            rows = self._rows_to_list(
                self._execute(
                    "SELECT * FROM validation_packs WHERE app_id = ? ORDER BY created_at DESC",
                    (app_id,),
                )
            )
        else:
            rows = self._rows_to_list(
                self._execute("SELECT * FROM validation_packs ORDER BY created_at DESC")
            )
        for r in rows:
            r["steps"] = self._uj(r.get("steps")) or []
            r["provenance"] = self._provenance_value(r.get("provenance"))
            r["schedule_enabled"] = bool(r.get("schedule_enabled"))
        return rows

    def get_validation_pack(self, pack_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(
            self._execute("SELECT * FROM validation_packs WHERE id = ?", (pack_id,)).fetchone()
        )
        if row:
            row["steps"] = self._uj(row.get("steps")) or []
            row["provenance"] = self._provenance_value(row.get("provenance"))
            row["schedule_enabled"] = bool(row.get("schedule_enabled"))
        return row

    def update_validation_pack(self, pack_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Coerce schedule_enabled to int for SQLite
        if "schedule_enabled" in fields and fields["schedule_enabled"] is not None:
            fields["schedule_enabled"] = 1 if fields["schedule_enabled"] else 0
        sets, params = self._build_update(
            fields,
            ["name", "description", "steps", "app_id", "provenance",
             "schedule", "schedule_enabled", "next_run_at", "last_scheduled_run_at"],
        )
        if not sets:
            return self.get_validation_pack(pack_id)
        self._execute(
            f"UPDATE validation_packs SET {sets}, updated_at = ? WHERE id = ?",
            params + (_now_iso(), pack_id),
        )
        return self.get_validation_pack(pack_id)

    def update_pack_schedule_run(
        self,
        pack_id: str,
        last_scheduled_run_at: Optional[str] = None,
        next_run_at: Optional[str] = None,
    ) -> None:
        """Update schedule timestamps after a scheduled run fires."""
        fields: Dict[str, Any] = {}
        if last_scheduled_run_at is not None:
            fields["last_scheduled_run_at"] = last_scheduled_run_at
        if next_run_at is not None:
            fields["next_run_at"] = next_run_at
        if fields:
            self.update_validation_pack(pack_id, fields)

    def get_scheduled_packs(self) -> List[Dict[str, Any]]:
        """Return all packs with schedule_enabled=1 and a non-empty schedule."""
        rows = self._rows_to_list(
            self._execute(
                "SELECT * FROM validation_packs WHERE schedule_enabled = 1 AND schedule != 'none' AND schedule IS NOT NULL ORDER BY next_run_at ASC"
            )
        )
        for r in rows:
            r["steps"] = self._uj(r.get("steps")) or []
            r["provenance"] = self._provenance_value(r.get("provenance"))
            r["schedule_enabled"] = bool(r.get("schedule_enabled"))
        return rows

    def delete_validation_pack(self, pack_id: str) -> bool:
        cur = self._execute("DELETE FROM validation_packs WHERE id = ?", (pack_id,))
        return cur.rowcount > 0

    # ── live_runs ─────────────────────────────────────────────────────────────

    def create_run(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        retest_selection = rec.get("retest_selection")
        self._execute(
            "INSERT INTO live_runs (id, pack_id, app_target_id, status, step_results, retest_of, execution_mode, created_at, provenance, retest_selection_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["id"], rec["pack_id"], rec["app_target_id"],
                rec.get("status", "pending"), self._j([]),
                rec.get("retest_of"), rec.get("execution_mode", "automated"), rec["created_at"],
                self._provenance_value(rec.get("provenance")),
                self._j(retest_selection) if retest_selection is not None else None,
            ),
        )
        return rec

    def get_active_retest_child(self, parent_run_id: str) -> Optional[Dict[str, Any]]:
        """Non-terminal (pending/running) retest child of this parent, if any.

        Uses idx_live_runs_retest_parent (retest_of, created_at DESC) — no new
        index needed. Returns the most recent one deterministically.
        """
        return self._select_one(
            "SELECT * FROM live_runs WHERE retest_of = ? "
            "AND status NOT IN ('completed', 'failed', 'cancelled') "
            "ORDER BY created_at DESC LIMIT 1",
            (parent_run_id,),
        )

    def create_retest_child_if_none_active(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Atomic check-then-insert for retest child creation.

        Closes the TOCTOU race where two concurrent retest-failed requests
        both observe "no active child" and both insert one. The active-child
        query and the INSERT happen under the same self._lock critical
        section (ProductStorage's single writer lock), so no second caller
        can observe a stale "none active" result between the check and the
        write — not merely an in-process convenience, this is the actual
        correctness guarantee.

        Raises ActiveRetestChildError if a non-terminal child already exists
        for rec["retest_of"]; never partially inserts in that case.
        """
        parent_id = rec.get("retest_of")
        with self._lock:
            if parent_id:
                active = self.get_active_retest_child(parent_id)
                if active is not None:
                    raise ActiveRetestChildError(parent_id, active["id"])
            return self.create_run(rec)

    def get_retest_lineage_info(self, run_id: str) -> Dict[str, Any]:
        """
        Iteratively walk the retest_of chain from run_id up to its root.
        Bounded, cycle-safe: a visited set plus a hard traversal cap means
        this can never loop indefinitely, even on corrupted data.

        Returns a dict:
          depth: hops from the true root to run_id (root itself = 0).
                 None if the lineage could not be resolved cleanly (cycle,
                 broken reference, or traversal cap hit) — callers must
                 treat that as "cannot safely extend this lineage", never
                 guess a depth.
          root_run_id: the id of the run with no retest_of, if resolved.
          lineage_run_ids: [run_id, parent_id, grandparent_id, ...] in walk
                 order, as far as the walk actually got.
          cycle_detected: True if retest_of revisits an already-walked id.
          broken_parent_reference: True if some retest_of points at a
                 run_id that does not exist in storage (run_id itself
                 missing counts as broken, not "root").
          traversal_limit_reached: True if the walk exceeded the internal
                 defensive cap without terminating.
        """
        cap = MAX_RETEST_LINEAGE_DEPTH + _LINEAGE_TRAVERSAL_BUFFER
        lineage_run_ids = [run_id]
        visited = {run_id}

        current = self.get_run(run_id)
        if current is None:
            return {
                "depth": None, "root_run_id": None,
                "lineage_run_ids": lineage_run_ids,
                "cycle_detected": False, "broken_parent_reference": True,
                "traversal_limit_reached": False,
            }

        hops = 0
        while True:
            parent_id = current.get("retest_of")
            if not parent_id:
                return {
                    "depth": hops, "root_run_id": current["id"],
                    "lineage_run_ids": lineage_run_ids,
                    "cycle_detected": False, "broken_parent_reference": False,
                    "traversal_limit_reached": False,
                }
            if parent_id in visited:
                return {
                    "depth": None, "root_run_id": None,
                    "lineage_run_ids": lineage_run_ids,
                    "cycle_detected": True, "broken_parent_reference": False,
                    "traversal_limit_reached": False,
                }
            if hops >= cap:
                return {
                    "depth": None, "root_run_id": None,
                    "lineage_run_ids": lineage_run_ids,
                    "cycle_detected": False, "broken_parent_reference": False,
                    "traversal_limit_reached": True,
                }
            parent_row = self.get_run(parent_id)
            if parent_row is None:
                return {
                    "depth": None, "root_run_id": None,
                    "lineage_run_ids": lineage_run_ids + [parent_id],
                    "cycle_detected": False, "broken_parent_reference": True,
                    "traversal_limit_reached": False,
                }
            lineage_run_ids.append(parent_id)
            visited.add(parent_id)
            current = parent_row
            hops += 1

    def create_retest_child_if_allowed(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Atomic check-then-insert combining lineage-depth/cycle validation
        with the existing active-child guard. Lineage is validated first,
        then delegates to create_retest_child_if_none_active() for the
        active-child check + insert — both still happen inside the same
        self._lock critical section (RLock is reentrant), so nothing is
        duplicated and nothing unlocks between validation and write.

        Raises (never partially inserts):
          RetestLineageInvalidError — parent's retest_of chain has a cycle,
            a broken reference, or hit the traversal cap.
          RetestLineageDepthExceededError — parent depth + 1 would exceed
            MAX_RETEST_LINEAGE_DEPTH.
          ActiveRetestChildError — parent already has a non-terminal child.
        """
        parent_id = rec.get("retest_of")
        with self._lock:
            if parent_id:
                info = self.get_retest_lineage_info(parent_id)
                if info["depth"] is None:
                    raise RetestLineageInvalidError(parent_id)
                new_depth = info["depth"] + 1
                if new_depth > MAX_RETEST_LINEAGE_DEPTH:
                    raise RetestLineageDepthExceededError(parent_id, new_depth)
            return self.create_retest_child_if_none_active(rec)

    def list_runs(self, pack_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 200))
        if pack_id:
            rows = self._select_all(
                "SELECT * FROM live_runs WHERE pack_id = ? ORDER BY created_at DESC LIMIT ?",
                (pack_id, limit),
            )
        else:
            rows = self._select_all(
                "SELECT * FROM live_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        for r in rows:
            self._deserialize_run(r)
        return rows

    def load_run_comparison_snapshot(self, baseline_id: str, comparison_id: str) -> Dict[str, Any]:
        """Raw, bounded observations in one read transaction; no enrichment.

        Missing provenance is deliberately NOT repaired. Presence of evidence is
        returned separately so callers can disclose legacy inference, not trust it.
        Oversized JSON is never loaded/partially matched (duplicates may be beyond
        a prefix). Evidence payloads, paths and contents are not read at all.
        """
        snapshot: Dict[str, Any] = {}
        with self._lock:
            conn = self._get_conn()
            conn.execute("BEGIN")
            try:
                for rid in (baseline_id, comparison_id):
                    row = conn.execute(
                        "SELECT id, pack_id, app_target_id, status, execution_mode, provenance, "
                        "created_at, started_at, completed_at, substr(error,1,4096) AS error, retest_of, "
                        "length(CAST(step_results AS BLOB)) AS result_bytes, "
                        "CASE WHEN length(CAST(step_results AS BLOB)) <= 2097152 "
                        "THEN step_results ELSE NULL END AS step_results "
                        "FROM live_runs WHERE id = ?", (rid,),
                    ).fetchone()
                    evidence = conn.execute(
                        "SELECT id, run_id, step_id, type, sha256, provenance "
                        "FROM evidence_files WHERE run_id = ? ORDER BY id LIMIT 501", (rid,),
                    ).fetchall() if row is not None else []
                    snapshot[rid] = {
                        "run": dict(row) if row is not None else None,
                        "evidence": [dict(item) for item in evidence[:500]],
                        "evidence_complete": len(evidence) <= 500,
                    }
            finally:
                conn.execute("ROLLBACK")
        return snapshot

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        row = self._select_one("SELECT * FROM live_runs WHERE id = ?", (run_id,))
        if row:
            self._deserialize_run(row)
        return row

    def list_comparable_runs(
        self,
        *,
        pack_id: str,
        app_target_id: str,
        exclude_run_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return bounded terminal history for one exact pack/target pair."""
        bounded_limit = max(1, min(int(limit), 50))
        rows = self._select_all(
            "SELECT * FROM live_runs "
            "WHERE pack_id = ? AND app_target_id = ? AND id != ? "
            "AND status IN ('completed', 'failed', 'cancelled') "
            "ORDER BY COALESCE(completed_at, started_at, created_at) DESC, "
            "created_at DESC, id DESC LIMIT ?",
            (pack_id, app_target_id, exclude_run_id, bounded_limit),
        )
        for row in rows:
            self._deserialize_run(row)
        return rows

    def list_run_evidence_for_history(
        self,
        run_id: str,
        *,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Return bounded evidence metadata for ownership-checked citations."""
        bounded_limit = max(1, min(int(limit), 500))
        rows = self._select_all(
            "SELECT * FROM evidence_files WHERE run_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (run_id, bounded_limit),
        )
        return [self._deserialize_evidence(row) for row in rows]

    def _deserialize_run(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize run and per-step provenance, including legacy records."""
        step_results = self._uj(row.get("step_results")) or []
        evidence_rows = self._select_all(
            "SELECT id, step_id FROM evidence_files WHERE run_id = ?",
            (row["id"],),
        )
        evidence_ids = {item["id"] for item in evidence_rows}
        evidence_step_ids = {
            item["step_id"] for item in evidence_rows if item.get("step_id")
        }
        for result in step_results:
            if result.get("provenance"):
                result["provenance"] = self._provenance_value(result["provenance"])
                continue
            result_evidence_ids = set(result.get("evidence_ids") or [])
            has_evidence = bool(
                (result.get("step_id") and result["step_id"] in evidence_step_ids)
                or result_evidence_ids.intersection(evidence_ids)
            )
            result["provenance"] = (
                Provenance.REAL_EXECUTION.value
                if has_evidence
                else Provenance.UNAVAILABLE.value
            )
        row["step_results"] = step_results
        row["provenance"] = self._resolve_run_provenance(row)
        row["retest_selection"] = self._uj(row.get("retest_selection_json"))
        return row

    def _resolve_run_provenance(self, row: Dict[str, Any]) -> str:
        raw = row.get("provenance")
        if raw:
            return self._provenance_value(raw)
        evidence = self._execute(
            "SELECT 1 FROM evidence_files WHERE run_id = ? LIMIT 1",
            (row["id"],),
        ).fetchone()
        if evidence is not None:
            return Provenance.REAL_EXECUTION.value
        return Provenance.UNAVAILABLE.value

    def update_run_provenance(self, run_id: str, provenance: Any) -> None:
        self._execute(
            "UPDATE live_runs SET provenance = ? WHERE id = ?",
            (self._provenance_value(provenance), run_id),
        )

    def update_run_status(
        self,
        run_id: str,
        status: str,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        self._execute(
            "UPDATE live_runs SET status = ?, started_at = COALESCE(?, started_at), "
            "completed_at = COALESCE(?, completed_at), error = COALESCE(?, error) WHERE id = ?",
            (status, started_at, completed_at, error, run_id),
        )

    def append_run_step_result(self, run_id: str, step_num: int, result: Dict[str, Any]) -> None:
        """Append one step result to the JSON array. Thread-safe via RLock."""
        with self._lock:
            row = self._get_conn().execute(
                "SELECT step_results FROM live_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return
            existing: list = json.loads(row["step_results"] or "[]")
            existing.append({"step": step_num, **result})
            self._get_conn().execute(
                "UPDATE live_runs SET step_results = ? WHERE id = ?",
                (json.dumps(existing, default=str), run_id),
            )

    def replace_run_step_results(
        self,
        run_id: str,
        results: List[Dict[str, Any]],
        *,
        status: Optional[str] = None,
        started_at: Optional[str] = None,
    ) -> None:
        """Persist the complete step-result set for manual review updates."""
        self._execute(
            "UPDATE live_runs SET step_results = ?, status = COALESCE(?, status), "
            "started_at = COALESCE(?, started_at) WHERE id = ?",
            (self._j(results), status, started_at, run_id),
        )

    def cancel_run(self, run_id: str) -> bool:
        cur = self._execute(
            "UPDATE live_runs SET status = 'cancelled', completed_at = ? WHERE id = ? AND status IN ('pending','running')",
            (_now_iso(), run_id),
        )
        return cur.rowcount > 0

    def run_counts(self) -> Dict[str, int]:
        rows = self._rows_to_list(
            self._execute("SELECT status, COUNT(*) as cnt FROM live_runs GROUP BY status")
        )
        counts: Dict[str, int] = {}
        for r in rows:
            counts[r["status"]] = r["cnt"]
        return counts

    # ── run_events ───────────────────────────────────────────────────────────

    def create_run_event(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        created_at = rec.get("created_at") or _now_iso()
        cur = self._execute(
            "INSERT INTO run_events "
            "(run_id, step_index, step_id, event_type, message, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                rec["run_id"],
                rec.get("step_index"),
                rec.get("step_id"),
                rec["event_type"],
                rec.get("message", ""),
                self._j(rec.get("payload", {})),
                created_at,
            ),
        )
        return {**rec, "id": int(cur.lastrowid), "created_at": created_at}

    def list_run_events(self, run_id: str) -> List[Dict[str, Any]]:
        rows = self._select_all(
            "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at, id",
            (run_id,),
        )
        for row in rows:
            row["payload"] = self._uj(row.get("payload")) or {}
        return rows

    # ── permissions ───────────────────────────────────────────────────────────

    def create_permission(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        self._execute(
            "INSERT INTO permissions (id, run_id, action, description, risk, status, requested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                rec["id"], rec["run_id"], rec["action"], rec.get("description", ""),
                rec.get("risk", "medium"), "pending", rec["requested_at"],
            ),
        )
        return rec

    def list_permissions(self, run_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        where_clauses = []
        params: list = []
        if run_id:
            where_clauses.append("run_id = ?")
            params.append(run_id)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        return self._rows_to_list(
            self._execute(
                f"SELECT * FROM permissions {where} ORDER BY requested_at DESC",
                tuple(params),
            )
        )

    def get_permission(self, perm_id: str) -> Optional[Dict[str, Any]]:
        return self._row_to_dict(
            self._execute("SELECT * FROM permissions WHERE id = ?", (perm_id,)).fetchone()
        )

    def resolve_permission(
        self, perm_id: str, approved: bool, reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        status = "approved" if approved else "denied"
        self._execute(
            "UPDATE permissions SET status = ?, resolved_at = ?, reason = ? WHERE id = ? AND status = 'pending'",
            (status, _now_iso(), reason, perm_id),
        )
        return self.get_permission(perm_id)

    # ── evidence_files ────────────────────────────────────────────────────────

    def _deserialize_evidence(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row["metadata_json"] = self._uj(row.get("metadata_json")) or {}
        row["provenance"] = self._provenance_value(row.get("provenance"))
        return row

    def create_evidence(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        self._execute(
            "INSERT INTO evidence_files (id, run_id, step_id, type, name, relative_path, mime_type, size_bytes, sha256, metadata_json, created_at, provenance) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["id"], rec["run_id"], rec.get("step_id"), rec.get("evidence_type") or rec.get("type"), rec["name"], rec["relative_path"],
                rec.get("mime_type", "application/octet-stream"),
                int(rec.get("size_bytes", 0)), rec.get("sha256"), self._j(rec.get("metadata_json", {})), rec["created_at"],
                self._provenance_value(rec.get("provenance")),
            ),
        )
        return rec

    def list_evidence(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if run_id:
            rows = self._select_all(
                "SELECT * FROM evidence_files WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            )
        else:
            rows = self._select_all("SELECT * FROM evidence_files ORDER BY created_at DESC")
        return [self._deserialize_evidence(r) for r in rows]

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        row = self._select_one("SELECT * FROM evidence_files WHERE id = ?", (evidence_id,))
        return self._deserialize_evidence(row) if row else None

    def update_evidence(self, evidence_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        clean = dict(fields)
        if "provenance" in clean:
            clean["provenance"] = self._provenance_value(clean["provenance"])
        sets, params = self._build_update(
            clean,
            ["name", "relative_path", "mime_type", "size_bytes", "sha256", "metadata_json", "provenance"],
        )
        if sets:
            self._execute(f"UPDATE evidence_files SET {sets} WHERE id = ?", params + (evidence_id,))
        return self.get_evidence(evidence_id)

    # ── reports ───────────────────────────────────────────────────────────────

    def create_report(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        # Serialize summary fields into summary_json blob
        summary_keys = {"app_name", "pack_name", "verdict", "summary", "pass_count",
                        "fail_count", "unclear_count", "evidence_count", "findings",
                        "api_step_count", "api_pass_count", "api_fail_count", "api_avg_response_time_ms",
                        "perf_total_checks", "perf_passed_budgets", "perf_failed_budgets",
                        "perf_avg_page_load_ms", "perf_avg_api_response_time_ms", "perf_slowest_check_ms",
                        "a11y_total_checks", "a11y_passed_checks", "a11y_failed_checks", "a11y_total_violations",
                        "visual_total_checks", "visual_passed_checks", "visual_failed_checks", "visual_avg_diff_percent", "visual_worst_diff_percent",
                        "security_total_checks", "security_passed_checks", "security_failed_checks", "security_total_findings", "security_critical_findings", "security_warning_findings"}
        summary_data = {k: rec[k] for k in summary_keys if k in rec and rec[k] is not None}
        summary_json = self._j(summary_data) if summary_data else None
        self._execute(
            "INSERT INTO reports (id, run_id, name, format, relative_path, summary_json, created_at, provenance) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["id"], rec["run_id"], rec["name"],
                rec.get("format", "json"), rec.get("relative_path", ""),
                summary_json, rec["created_at"],
                self._provenance_value(rec.get("provenance")),
            ),
        )
        return rec

    def _enrich_report(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Merge summary_json fields into the report row dict."""
        if row.get("summary_json"):
            extra = self._uj(row["summary_json"]) or {}
            row.update(extra)
        row["provenance"] = self._provenance_value(row.get("provenance"))
        return row

    def list_reports(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if run_id:
            rows = self._rows_to_list(
                self._execute(
                    "SELECT * FROM reports WHERE run_id = ? ORDER BY created_at DESC",
                    (run_id,),
                )
            )
        else:
            rows = self._rows_to_list(
                self._execute("SELECT * FROM reports ORDER BY created_at DESC")
            )
        return [self._enrich_report(r) for r in rows]

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(
            self._execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        )
        return self._enrich_report(row) if row else None

    # ── settings ──────────────────────────────────────────────────────────────

    def get_setting(self, key: str) -> Optional[str]:
        row = self._execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self._execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, _now_iso()),
        )

    def list_settings(self) -> List[Dict[str, Any]]:
        return self._rows_to_list(
            self._execute("SELECT * FROM settings ORDER BY key")
        )

    # ── model_providers ───────────────────────────────────────────────────────

    def create_model_provider(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """Store provider config. NEVER stores raw api_key values."""
        now = _now_iso()
        self._execute(
            "INSERT INTO model_providers "
            "(provider_id, provider_type, name, enabled, base_url, api_key_env, "
            "secret_ref, allow_cloud, local_only, metadata, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["provider_id"], rec["provider_type"], rec["name"],
                int(rec.get("enabled", 0)), rec.get("base_url"),
                rec.get("api_key_env"),  # env var NAME only, never the value
                rec.get("secret_ref"),
                int(rec.get("allow_cloud", 0)), int(rec.get("local_only", 1)),
                self._j(rec.get("metadata", {})),
                now, now,
            ),
        )
        return self.get_model_provider(rec["provider_id"]) or rec

    def update_model_provider(self, provider_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        _ALLOWED = ["provider_type", "name", "enabled", "base_url",
                    "api_key_env", "secret_ref", "allow_cloud", "local_only", "metadata"]
        set_clause, params = self._build_update(fields, _ALLOWED)
        if not set_clause:
            return self.get_model_provider(provider_id)
        self._execute(
            f"UPDATE model_providers SET {set_clause}, updated_at = ? WHERE provider_id = ?",
            params + (_now_iso(), provider_id),
        )
        return self.get_model_provider(provider_id)

    def delete_model_provider(self, provider_id: str) -> bool:
        cur = self._execute("DELETE FROM model_providers WHERE provider_id = ?", (provider_id,))
        return bool(cur.rowcount)

    def get_model_provider(self, provider_id: str) -> Optional[Dict[str, Any]]:
        return self._row_to_dict(
            self._execute("SELECT * FROM model_providers WHERE provider_id = ?", (provider_id,)).fetchone()
        )

    def list_model_providers(self) -> List[Dict[str, Any]]:
        return self._rows_to_list(
            self._execute("SELECT * FROM model_providers ORDER BY name")
        )

    # ── model_routes ──────────────────────────────────────────────────────────

    def upsert_model_route(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        now = _now_iso()
        route_id = rec.get("id") or rec.get("task", "")
        self._execute(
            "INSERT INTO model_routes "
            "(id, task, provider_id, model, priority, enabled, fallback_models, "
            "temperature, timeout_seconds, estimated_memory_gb, local_only, requires_approval, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "model = excluded.model, priority = excluded.priority, enabled = excluded.enabled, "
            "fallback_models = excluded.fallback_models, temperature = excluded.temperature, "
            "timeout_seconds = excluded.timeout_seconds, estimated_memory_gb = excluded.estimated_memory_gb, "
            "local_only = excluded.local_only, requires_approval = excluded.requires_approval, "
            "updated_at = excluded.updated_at",
            (
                route_id, rec["task"], rec["provider_id"], rec["model"],
                int(rec.get("priority", 1)), int(rec.get("enabled", 1)),
                self._j(rec.get("fallback_models", [])),
                float(rec.get("temperature", 0.1)),
                int(rec.get("timeout_seconds", 60)),
                float(rec.get("estimated_memory_gb", 4.0)),
                int(rec.get("local_only", 1)),
                int(rec.get("requires_approval", 0)),
                now, now,
            ),
        )
        return self.get_model_route(route_id) or rec

    def get_model_route(self, route_id: str) -> Optional[Dict[str, Any]]:
        return self._row_to_dict(
            self._execute("SELECT * FROM model_routes WHERE id = ?", (route_id,)).fetchone()
        )

    def list_model_routes(self) -> List[Dict[str, Any]]:
        return self._rows_to_list(
            self._execute("SELECT * FROM model_routes ORDER BY task, priority")
        )

    # ── model_usage_events ────────────────────────────────────────────────────

    def record_model_usage(self, event: Dict[str, Any]) -> None:
        """Record a model call event. Does NOT store raw prompts."""
        self._execute(
            "INSERT INTO model_usage_events "
            "(id, task, provider_id, model, latency_ms, status, fallback_used, "
            "tokens_in, tokens_out, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event["id"], event["task"], event["provider_id"], event["model"],
                float(event.get("latency_ms", 0.0)),
                event.get("status", "ok"),
                int(event.get("fallback_used", 0)),
                int(event.get("tokens_in", 0)),
                int(event.get("tokens_out", 0)),
                event.get("created_at", _now_iso()),
            ),
        )

    def list_model_usage(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._rows_to_list(
            self._execute(
                "SELECT * FROM model_usage_events ORDER BY created_at DESC LIMIT ?",
                (min(limit, 500),),
            )
        )

    # ── dashboard counts ──────────────────────────────────────────────────────

    def dashboard_snapshot(self, limit: int = 1000) -> Dict[str, List[Dict[str, Any]]]:
        """Read one bounded, persisted snapshot for dashboard aggregation."""
        bounded_limit = max(1, min(limit, 5000))
        runs = self._select_all(
            "SELECT live_runs.*, validation_packs.name AS pack_name, "
            "app_targets.name AS app_name "
            "FROM live_runs "
            "LEFT JOIN validation_packs ON validation_packs.id = live_runs.pack_id "
            "LEFT JOIN app_targets ON app_targets.id = live_runs.app_target_id "
            "ORDER BY COALESCE(live_runs.completed_at, live_runs.started_at, live_runs.created_at) DESC "
            "LIMIT ?",
            (bounded_limit,),
        )
        for run in runs:
            self._deserialize_run(run)

        evidence = self._select_all(
            "SELECT * FROM evidence_files "
            "WHERE LOWER(COALESCE(type, '')) LIKE '%screenshot%' "
            "OR LOWER(COALESCE(mime_type, '')) LIKE 'image/%' "
            "ORDER BY created_at DESC LIMIT 5000"
        )
        return {
            "projects": self.list_projects(),
            "apps": self.list_app_targets(),
            "packs": self.list_validation_packs(),
            "runs": runs,
            "evidence": [self._deserialize_evidence(row) for row in evidence],
        }

    def count_table(self, table: str) -> int:
        """Count rows in a known table. Table name is from allowlist, not user input."""
        _ALLOWED_TABLES = frozenset({
            "projects", "app_targets", "validation_packs", "live_runs",
            "permissions", "evidence_files", "reports",
            "model_providers", "model_routes", "model_usage_events",
        })
        if table not in _ALLOWED_TABLES:
            raise ValueError(f"count_table: unknown table {table!r}")
        # Table name comes from internal allowlist only — safe to interpolate
        row = self._execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
        return row["cnt"] if row else 0

    # ── validation_test_plans ─────────────────────────────────────────────────

    def create_test_plan(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        self._execute(
            "INSERT INTO validation_test_plans "
            "(plan_id, pack_id, app_id, generated_from, coverage_summary, risk_summary, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["plan_id"], rec["pack_id"], rec.get("app_id"),
                rec.get("generated_from", "generic_app_type_template"),
                self._j(rec.get("coverage_summary", {})),
                self._j(rec.get("risk_summary", {})),
                rec["created_at"], rec["updated_at"],
            ),
        )
        return rec

    def get_test_plan_for_pack(self, pack_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(
            self._execute(
                "SELECT * FROM validation_test_plans WHERE pack_id = ? ORDER BY created_at DESC LIMIT 1",
                (pack_id,),
            ).fetchone()
        )
        if row:
            row["coverage_summary"] = self._uj(row.get("coverage_summary")) or {}
            row["risk_summary"] = self._uj(row.get("risk_summary")) or {}
        return row

    def delete_test_plan_for_pack(self, pack_id: str) -> None:
        # Also delete all test cases for this pack
        self._execute("DELETE FROM validation_test_cases WHERE pack_id = ?", (pack_id,))
        self._execute("DELETE FROM validation_test_plans WHERE pack_id = ?", (pack_id,))

    # ── validation_test_cases ─────────────────────────────────────────────────

    _TC_JSON_COLS = ("preconditions", "steps", "expected_evidence", "tags")

    def _deserialize_test_case(self, row: Dict[str, Any]) -> Dict[str, Any]:
        for col in self._TC_JSON_COLS:
            row[col] = self._uj(row.get(col)) or []
        row["requires_permission"] = bool(row.get("requires_permission", 0))
        row["enabled"] = bool(row.get("enabled", 1))
        row["confidence"] = row.get("confidence")
        row["rationale"] = row.get("rationale")
        row["generated_by"] = row.get("generated_by")
        row["generation_source"] = row.get("generation_source")
        row["generation_metadata"] = self._uj(row.get("generation_metadata_json")) or {}
        row["test_steps"] = self.list_test_steps(row["test_case_id"])
        return row

    def create_test_case(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        self._execute(
            "INSERT INTO validation_test_cases "
            "(test_case_id, plan_id, pack_id, app_id, flow_name, title, description, "
            "test_type, priority, risk_level, preconditions, steps, expected_result, "
            "expected_evidence, pass_criteria, fail_criteria, automation_status, "
            "safety_level, requires_permission, tags, enabled, created_at, updated_at, "
            "confidence, rationale, generated_by, generation_source, generation_metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["test_case_id"], rec["plan_id"], rec["pack_id"], rec.get("app_id"),
                rec.get("flow_name", ""), rec["title"], rec.get("description", ""),
                rec.get("test_type", "positive"), rec.get("priority", "P1"),
                rec.get("risk_level", "medium"),
                self._j(rec.get("preconditions", [])),
                self._j(rec.get("steps", [])),
                rec.get("expected_result", ""),
                self._j(rec.get("expected_evidence", [])),
                rec.get("pass_criteria", ""), rec.get("fail_criteria", ""),
                rec.get("automation_status", "needs_selector"),
                rec.get("safety_level", "safe"),
                int(rec.get("requires_permission", False)),
                self._j(rec.get("tags", [])),
                int(rec.get("enabled", True)),
                rec["created_at"], rec["updated_at"],
                rec.get("confidence"), rec.get("rationale"),
                rec.get("generated_by"), rec.get("generation_source"),
                self._j(rec.get("generation_metadata") if rec.get("generation_metadata") is not None else (self._uj(rec.get("generation_metadata_json")) or {})),
            ),
        )
        return rec

    def list_test_cases(self, pack_id: str) -> List[Dict[str, Any]]:
        rows = self._rows_to_list(
            self._execute(
                "SELECT * FROM validation_test_cases WHERE pack_id = ? ORDER BY created_at ASC",
                (pack_id,),
            )
        )
        return [self._deserialize_test_case(r) for r in rows]

    def get_test_case(self, test_case_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(
            self._execute(
                "SELECT * FROM validation_test_cases WHERE test_case_id = ?",
                (test_case_id,),
            ).fetchone()
        )
        return self._deserialize_test_case(row) if row else None

    def update_test_case(self, test_case_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        _ALLOWED = [
            "flow_name", "title", "description", "test_type", "priority", "risk_level",
            "preconditions", "steps", "expected_result", "expected_evidence",
            "pass_criteria", "fail_criteria", "automation_status", "safety_level",
            "requires_permission", "tags", "enabled",
            "confidence", "rationale", "generated_by", "generation_source", "generation_metadata_json",
        ]
        # Convert bool fields to int for SQLite
        if "requires_permission" in fields and fields["requires_permission"] is not None:
            fields["requires_permission"] = int(bool(fields["requires_permission"]))
        if "enabled" in fields and fields["enabled"] is not None:
            fields["enabled"] = int(bool(fields["enabled"]))
        if "generation_metadata" in fields:
            fields["generation_metadata_json"] = self._j(fields.pop("generation_metadata"))
        sets, params = self._build_update(fields, _ALLOWED)
        if not sets:
            return self.get_test_case(test_case_id)
        self._execute(
            f"UPDATE validation_test_cases SET {sets}, updated_at = ? WHERE test_case_id = ?",
            params + (_now_iso(), test_case_id),
        )
        return self.get_test_case(test_case_id)

    def delete_test_case(self, test_case_id: str) -> bool:
        cur = self._execute(
            "DELETE FROM validation_test_cases WHERE test_case_id = ?", (test_case_id,)
        )
        return cur.rowcount > 0

    # ── validation_test_steps ──────────────────────────────────────────────────

    def _deserialize_test_step(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row["optional"] = bool(row.get("optional", 0))
        row["headers"] = self._uj(row.get("headers_json")) or {}
        row["query_params"] = self._uj(row.get("query_params_json")) or {}
        row["body_json"] = self._uj(row.get("body_json"))
        row["expected_value"] = self._uj(row.get("expected_value"))
        row["confidence"] = row.get("confidence")
        row["rationale"] = row.get("rationale")
        row["generated_by"] = row.get("generated_by")
        row["generation_source"] = row.get("generation_source")
        row["generation_metadata"] = self._uj(row.get("generation_metadata_json")) or {}
        return row

    def create_test_step(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        self._execute(
            "INSERT INTO validation_test_steps "
            "(step_id, case_id, step_order, action_type, target, value, expected, method, url, "
            "headers_json, query_params_json, body_json, expected_status, expected_json_path, expected_value, "
            "timeout_ms, optional, notes, budget_ms, warn_ms, metric_name, "
            "confidence, rationale, generated_by, generation_source, generation_metadata_json, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["step_id"], rec["case_id"], rec.get("step_order", 0),
                rec["action_type"], rec.get("target"), rec.get("value"),
                rec.get("expected"), rec.get("method"), rec.get("url"),
                self._j(rec.get("headers", {})),
                self._j(rec.get("query_params", {})),
                self._j(rec.get("body_json")),
                rec.get("expected_status"),
                rec.get("expected_json_path"),
                self._j(rec.get("expected_value")),
                rec.get("timeout_ms", 30000),
                int(rec.get("optional", False)), rec.get("notes"),
                rec.get("budget_ms"), rec.get("warn_ms"), rec.get("metric_name"),
                rec.get("confidence"), rec.get("rationale"),
                rec.get("generated_by"), rec.get("generation_source"),
                self._j(rec.get("generation_metadata") if rec.get("generation_metadata") is not None else (self._uj(rec.get("generation_metadata_json")) or {})),
                rec.get("created_at") or _now_iso(), rec.get("updated_at") or _now_iso(),
            )
        )
        return rec

    def list_test_steps(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self._select_all(
            "SELECT * FROM validation_test_steps WHERE case_id = ? ORDER BY step_order ASC",
            (case_id,),
        )
        return [self._deserialize_test_step(r) for r in rows]

    def get_test_step(self, step_id: str) -> Optional[Dict[str, Any]]:
        row = self._select_one(
            "SELECT * FROM validation_test_steps WHERE step_id = ?",
            (step_id,),
        )
        return self._deserialize_test_step(row) if row else None

    def update_test_step(self, step_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        _ALLOWED = [
            "action_type", "target", "value", "expected", "method", "url",
            "headers_json", "query_params_json", "body_json",
            "expected_status", "expected_json_path", "expected_value",
            "timeout_ms", "optional", "notes", "budget_ms", "warn_ms", "metric_name",
            "confidence", "rationale", "generated_by", "generation_source", "generation_metadata_json",
        ]
        if "optional" in fields and fields["optional"] is not None:
            fields["optional"] = int(bool(fields["optional"]))
        if "headers" in fields:
            fields["headers_json"] = fields.pop("headers")
        if "query_params" in fields:
            fields["query_params_json"] = fields.pop("query_params")
        if "generation_metadata" in fields:
            fields["generation_metadata_json"] = fields.pop("generation_metadata")
        sets, params = self._build_update(fields, _ALLOWED)
        if not sets:
            return self.get_test_step(step_id)
        self._execute(
            f"UPDATE validation_test_steps SET {sets}, updated_at = ? WHERE step_id = ?",
            params + (_now_iso(), step_id),
        )
        return self.get_test_step(step_id)

    def delete_test_step(self, step_id: str) -> bool:
        cur = self._execute(
            "DELETE FROM validation_test_steps WHERE step_id = ?", (step_id,)
        )
        return cur.rowcount > 0

    def reorder_test_steps(self, case_id: str, step_ids: List[str]) -> None:
        with self._lock:
            conn = self._get_conn()
            for index, step_id in enumerate(step_ids):
                conn.execute(
                    "UPDATE validation_test_steps SET step_order = ?, updated_at = ? WHERE step_id = ? AND case_id = ?",
                    (index, _now_iso(), step_id, case_id)
                )

    def duplicate_test_case_with_steps(self, test_case_id: str) -> Optional[str]:
        case = self.get_test_case(test_case_id)
        if not case:
            return None
        import uuid
        new_case_id = str(uuid.uuid4())
        now = _now_iso()
        new_case = dict(case)
        new_case["test_case_id"] = new_case_id
        new_case["title"] = f"{case['title']} (Copy)"
        new_case["created_at"] = now
        new_case["updated_at"] = now
        new_case.pop("test_steps", None)
        self.create_test_case(new_case)
        steps = self.list_test_steps(test_case_id)
        for s in steps:
            new_step = dict(s)
            new_step["step_id"] = str(uuid.uuid4())
            new_step["case_id"] = new_case_id
            new_step["created_at"] = now
            new_step["updated_at"] = now
            self.create_test_step(new_step)
        return new_case_id

    def create_visual_baseline(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new visual baseline entry."""
        if not rec.get("id"):
            rec = dict(rec, id=str(uuid.uuid4()))
        if "baseline_id" in rec and not rec.get("id"):
            rec["id"] = rec["baseline_id"]
        if "baseline_path" in rec and not rec.get("relative_path"):
            rec["relative_path"] = rec["baseline_path"]
        elif "relative_path" in rec and not rec.get("baseline_path"):
            rec["baseline_path"] = rec["relative_path"]

        now = _now_iso()
        sql = (
            "INSERT INTO visual_baselines (id, app_id, pack_id, test_case_id, step_id, name, relative_path, baseline_path, width, height, sha256, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        self._execute(
            sql,
            (
                rec["id"],
                rec.get("app_id"),
                rec.get("pack_id"),
                rec.get("test_case_id"),
                rec.get("step_id"),
                rec.get("name"),
                rec.get("relative_path"),
                rec.get("baseline_path"),
                rec.get("width"),
                rec.get("height"),
                rec.get("sha256"),
                rec.get("created_at", now),
                rec.get("updated_at", now),
            ),
        )
        return rec

    def get_visual_baseline(self, baseline_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a visual baseline by ID."""
        sql = "SELECT * FROM visual_baselines WHERE id = ?"
        return self._select_one(sql, (baseline_id,))

    def get_visual_baseline_by_step(self, app_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a visual baseline by app_id and step_id."""
        sql = "SELECT * FROM visual_baselines WHERE app_id = ? AND step_id = ?"
        return self._select_one(sql, (app_id, step_id))

    def list_visual_baselines(self, app_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List visual baselines, optionally filtered by app_id."""
        if app_id:
            sql = "SELECT * FROM visual_baselines WHERE app_id = ?"
            return self._select_all(sql, (app_id,))
        sql = "SELECT * FROM visual_baselines"
        return self._select_all(sql)

    def delete_visual_baseline(self, baseline_id: str) -> bool:
        """Delete a visual baseline by ID."""
        sql = "DELETE FROM visual_baselines WHERE id = ?"
        cursor = self._execute(sql, (baseline_id,))
        return cursor.rowcount > 0

    # ── ai_evaluation_notes ───────────────────────────────────────────────────

    def _deserialize_evaluation_note(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row["evidence_used"] = self._uj(row.get("evidence_used")) or []
        row["missing_evidence"] = self._uj(row.get("missing_evidence")) or []
        row["risk_flags"] = self._uj(row.get("risk_flags")) or []
        row["generation_metadata_json"] = self._uj(row.get("generation_metadata_json")) or {}
        return row

    def create_ai_evaluation_note(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new AI evaluation note into the database."""
        self._execute(
            "INSERT INTO ai_evaluation_notes ("
            "    evaluation_id, run_id, step_id, verdict_assessment, suggested_verdict,"
            "    confidence, summary, evidence_used, missing_evidence, risk_flags,"
            "    rationale, generation_source, generation_metadata_json, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["evaluation_id"], rec["run_id"], rec.get("step_id"), rec["verdict_assessment"],
                rec.get("suggested_verdict"), float(rec["confidence"]), rec["summary"],
                self._j(rec.get("evidence_used", [])), self._j(rec.get("missing_evidence", [])),
                self._j(rec.get("risk_flags", [])), rec["rationale"], rec["generation_source"],
                self._j(rec.get("generation_metadata_json", {})), rec["created_at"]
            ),
        )
        return rec

    def list_ai_evaluation_notes(self, run_id: str) -> List[Dict[str, Any]]:
        """List AI evaluation notes for a specific run."""
        rows = self._select_all(
            "SELECT * FROM ai_evaluation_notes WHERE run_id = ? ORDER BY created_at DESC",
            (run_id,),
        )
        return [self._deserialize_evaluation_note(r) for r in rows]

    def get_ai_evaluation_note(self, evaluation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific AI evaluation note by ID."""
        row = self._select_one(
            "SELECT * FROM ai_evaluation_notes WHERE evaluation_id = ?",
            (evaluation_id,),
        )
        return self._deserialize_evaluation_note(row) if row else None

    # ── internal helpers ──────────────────────────────────────────────────────

    # ── ai_root_cause_suggestions ──

    def _deserialize_ai_root_cause_suggestion(
        self, row: Dict[str, Any]
    ) -> Dict[str, Any]:
        for field in (
            "evidence_refs",
            "supporting_signals",
            "contradicting_signals",
            "missing_evidence",
            "recommended_verification",
        ):
            row[field] = self._uj(row.get(field)) or []
        row["generation_metadata"] = (
            self._uj(row.pop("generation_metadata_json", None)) or {}
        )
        row["source_provenance"] = self._provenance_value(
            row.get("source_provenance")
        )
        row["authoritative"] = False
        return row

    def create_ai_root_cause_suggestions(
        self, batch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Persist one immutable draft analysis without changing execution data."""
        suggestions = batch.get("suggestions") or []
        with self._lock:
            conn = self._get_conn()
            conn.execute("BEGIN")
            try:
                conn.execute(
                    "INSERT INTO ai_root_cause_analyses ("
                    "analysis_id, run_id, status, authoritative, source_provenance, "
                    "generation_source, generation_metadata_json, missing_evidence, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        batch["analysis_id"],
                        batch["run_id"],
                        batch["status"],
                        0,
                        self._provenance_value(batch.get("source_provenance")),
                        batch["generation_source"],
                        self._j(batch.get("generation_metadata", {})),
                        self._j(batch.get("missing_evidence", [])),
                        batch["created_at"],
                    ),
                )
                for suggestion in suggestions:
                    conn.execute(
                        "INSERT INTO ai_root_cause_suggestions ("
                        "suggestion_id, analysis_id, run_id, step_id, rank, title, "
                        "possible_cause, category, confidence, evidence_refs, "
                        "supporting_signals, contradicting_signals, missing_evidence, "
                        "recommended_verification, suggested_owner_area, source_provenance, "
                        "generation_source, generation_metadata_json, authoritative, created_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            suggestion["suggestion_id"], batch["analysis_id"],
                            batch["run_id"], suggestion.get("step_id"),
                            int(suggestion["rank"]), suggestion["title"],
                            suggestion["possible_cause"], suggestion["category"],
                            float(suggestion["confidence"]),
                            self._j(suggestion.get("evidence_refs", [])),
                            self._j(suggestion.get("supporting_signals", [])),
                            self._j(suggestion.get("contradicting_signals", [])),
                            self._j(suggestion.get("missing_evidence", [])),
                            self._j(suggestion.get("recommended_verification", [])),
                            suggestion.get("suggested_owner_area", "unknown"),
                            self._provenance_value(suggestion.get("source_provenance")),
                            suggestion.get("generation_source") or batch["generation_source"],
                            self._j(
                                suggestion.get("generation_metadata")
                                or batch.get("generation_metadata", {})
                            ),
                            0,
                            suggestion.get("created_at") or batch["created_at"],
                        ),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return batch

    def list_ai_root_cause_suggestions(
        self, run_id: str
    ) -> List[Dict[str, Any]]:
        rows = self._select_all(
            "SELECT * FROM ai_root_cause_suggestions "
            "WHERE run_id = ? ORDER BY created_at DESC, rank ASC",
            (run_id,),
        )
        return [self._deserialize_ai_root_cause_suggestion(row) for row in rows]

    def get_latest_ai_root_cause_batch(
        self, run_id: str
    ) -> Optional[Dict[str, Any]]:
        latest = self._select_one(
            "SELECT * FROM ai_root_cause_analyses "
            "WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
            (run_id,),
        )
        if latest is None:
            return None
        rows = self._select_all(
            "SELECT * FROM ai_root_cause_suggestions "
            "WHERE analysis_id = ? ORDER BY rank ASC",
            (latest["analysis_id"],),
        )
        suggestions = [
            self._deserialize_ai_root_cause_suggestion(row) for row in rows
        ]
        return {
            "analysis_id": latest["analysis_id"],
            "run_id": latest["run_id"],
            "status": latest["status"],
            "authoritative": False,
            "source_provenance": self._provenance_value(
                latest.get("source_provenance")
            ),
            "generation_source": latest["generation_source"],
            "generation_metadata": self._uj(
                latest.get("generation_metadata_json")
            ) or {},
            "missing_evidence": self._uj(latest.get("missing_evidence")) or [],
            "suggestions": suggestions,
            "created_at": latest["created_at"],
        }

    @staticmethod
    def _aggregate_provenance(values: List[Any]) -> str:
        normalized = {
            ProductStorage._provenance_value(value)
            for value in values
            if value is not None
        }
        if not normalized:
            return Provenance.UNAVAILABLE.value
        if len(normalized) == 1:
            return next(iter(normalized))
        return Provenance.MIXED.value

    def _build_update(
        self, fields: Dict[str, Any], allowed: List[str]
    ) -> tuple:
        """
        Build SET clause for UPDATE from an allowed-key whitelist.
        Returns (set_clause_str, params_tuple).
        Only keys in `allowed` are used; others are silently ignored.
        JSON-serializes lists and dicts.
        """
        sets = []
        params: list = []
        for key in allowed:
            if key not in fields or fields[key] is None:
                continue
            val = fields[key]
            if isinstance(val, (list, dict)):
                val = self._j(val)
            sets.append(f"{key} = ?")
            params.append(val)
        return ", ".join(sets), tuple(params)
