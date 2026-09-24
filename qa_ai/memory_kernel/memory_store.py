"""
memory_store.py - SQLite persistence for the memory kernel.

Security:
- ALL queries use ? parameterized placeholders.
- No f-string SQL interpolation.
- WAL mode, foreign keys, idempotent schema.
- Thread-safe: RLock.
- Safe migration table.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_DEFAULT_DB_PATH = Path("artifacts/memory_kernel.db")

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version  INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_scopes (
    scope_id     TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    app_id       TEXT NOT NULL,
    product_area TEXT NOT NULL DEFAULT '',
    environment  TEXT NOT NULL DEFAULT 'default',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS golden_baselines (
    baseline_id               TEXT PRIMARY KEY,
    scope_id                  TEXT NOT NULL,
    baseline_name             TEXT NOT NULL,
    baseline_type             TEXT NOT NULL DEFAULT 'smoke',
    app_type                  TEXT NOT NULL DEFAULT '',
    run_id                    TEXT NOT NULL,
    flow_ids                  TEXT NOT NULL DEFAULT '[]',
    workflow_fingerprint      TEXT NOT NULL DEFAULT '',
    screen_fingerprints       TEXT NOT NULL DEFAULT '[]',
    api_fingerprints          TEXT NOT NULL DEFAULT '[]',
    db_fingerprints           TEXT NOT NULL DEFAULT '[]',
    connector_fingerprints    TEXT NOT NULL DEFAULT '[]',
    evidence_manifest_hash    TEXT NOT NULL DEFAULT '',
    summary                   TEXT NOT NULL DEFAULT '',
    created_at                TEXT NOT NULL,
    updated_at                TEXT NOT NULL,
    active                    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS run_deltas (
    delta_id           TEXT PRIMARY KEY,
    scope_id           TEXT NOT NULL,
    baseline_id        TEXT NOT NULL,
    run_id             TEXT NOT NULL,
    run_type           TEXT NOT NULL DEFAULT 'regression',
    verdict_change     TEXT,
    changed_steps      TEXT NOT NULL DEFAULT '[]',
    new_failures       TEXT NOT NULL DEFAULT '[]',
    resolved_failures  TEXT NOT NULL DEFAULT '[]',
    new_unclear        TEXT NOT NULL DEFAULT '[]',
    new_blocked        TEXT NOT NULL DEFAULT '[]',
    timing_deltas      TEXT NOT NULL DEFAULT '{}',
    connector_deltas   TEXT NOT NULL DEFAULT '[]',
    evidence_deltas    TEXT NOT NULL DEFAULT '[]',
    fingerprint_deltas TEXT NOT NULL DEFAULT '[]',
    summary_delta      TEXT NOT NULL DEFAULT '',
    storage_bytes      INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_fingerprints (
    fingerprint_id    TEXT PRIMARY KEY,
    scope_id          TEXT NOT NULL,
    run_id            TEXT NOT NULL,
    step_id           TEXT NOT NULL DEFAULT '',
    evidence_type     TEXT NOT NULL DEFAULT 'unknown',
    content_hash      TEXT NOT NULL DEFAULT '',
    perceptual_hash   TEXT NOT NULL DEFAULT '',
    semantic_hash     TEXT NOT NULL DEFAULT '',
    schema_hash       TEXT NOT NULL DEFAULT '',
    state_hash        TEXT NOT NULL DEFAULT '',
    workflow_hash     TEXT NOT NULL DEFAULT '',
    size_bytes        INTEGER NOT NULL DEFAULT 0,
    compact_size_bytes INTEGER NOT NULL DEFAULT 0,
    duplicate_of      TEXT,
    value_score       REAL NOT NULL DEFAULT 0.5,
    retention_class   TEXT NOT NULL DEFAULT 'warm',
    artifact_ref      TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS compact_summaries (
    summary_id    TEXT PRIMARY KEY,
    scope_id      TEXT NOT NULL,
    source_type   TEXT NOT NULL DEFAULT 'run',
    source_id     TEXT NOT NULL DEFAULT '',
    summary_text  TEXT NOT NULL,
    summary_hash  TEXT NOT NULL DEFAULT '',
    entities      TEXT NOT NULL DEFAULT '[]',
    tags          TEXT NOT NULL DEFAULT '[]',
    severity      TEXT NOT NULL DEFAULT 'info',
    confidence    REAL NOT NULL DEFAULT 0.5,
    utility_score REAL NOT NULL DEFAULT 0.5,
    embedding_ref TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings_memory (
    finding_id              TEXT PRIMARY KEY,
    scope_id                TEXT NOT NULL,
    canonical_failure_hash  TEXT NOT NULL,
    title                   TEXT NOT NULL,
    failure_type            TEXT NOT NULL DEFAULT 'unknown',
    severity                TEXT NOT NULL DEFAULT 'medium',
    confidence              REAL NOT NULL DEFAULT 0.5,
    first_seen              TEXT NOT NULL,
    last_seen               TEXT NOT NULL,
    frequency               INTEGER NOT NULL DEFAULT 1,
    affected_flows          TEXT NOT NULL DEFAULT '[]',
    affected_components     TEXT NOT NULL DEFAULT '[]',
    evidence_refs           TEXT NOT NULL DEFAULT '[]',
    status                  TEXT NOT NULL DEFAULT 'open',
    pattern_id              TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fixes_memory (
    fix_id             TEXT PRIMARY KEY,
    scope_id           TEXT NOT NULL,
    finding_id         TEXT NOT NULL,
    fix_attempt_id     TEXT NOT NULL DEFAULT '',
    commit_hash        TEXT NOT NULL DEFAULT '',
    change_summary     TEXT NOT NULL DEFAULT '',
    before_verdict     TEXT NOT NULL DEFAULT 'fail',
    after_verdict      TEXT NOT NULL DEFAULT 'unknown',
    retest_run_id      TEXT NOT NULL DEFAULT '',
    regression_status  TEXT NOT NULL DEFAULT 'unknown',
    confidence         REAL NOT NULL DEFAULT 0.5,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patterns_memory (
    pattern_id         TEXT PRIMARY KEY,
    scope_id           TEXT NOT NULL,
    pattern_type       TEXT NOT NULL,
    canonical_template TEXT NOT NULL,
    parameters         TEXT NOT NULL DEFAULT '{}',
    frequency          INTEGER NOT NULL DEFAULT 1,
    confidence         REAL NOT NULL DEFAULT 0.5,
    impact_score       REAL NOT NULL DEFAULT 0.5,
    first_seen         TEXT NOT NULL,
    last_seen          TEXT NOT NULL,
    related_findings   TEXT NOT NULL DEFAULT '[]',
    related_fixes      TEXT NOT NULL DEFAULT '[]',
    embedding_ref      TEXT,
    active             INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reasoning_trajectories (
    trajectory_id    TEXT PRIMARY KEY,
    scope_id         TEXT NOT NULL,
    problem_signature TEXT NOT NULL,
    reasoning_steps  TEXT NOT NULL DEFAULT '[]',
    evidence_checked TEXT NOT NULL DEFAULT '[]',
    hypotheses       TEXT NOT NULL DEFAULT '[]',
    action_taken     TEXT NOT NULL DEFAULT '',
    outcome          TEXT NOT NULL DEFAULT '',
    reusable_for     TEXT NOT NULL DEFAULT '[]',
    success_count    INTEGER NOT NULL DEFAULT 0,
    failure_count    INTEGER NOT NULL DEFAULT 0,
    utility_score    REAL NOT NULL DEFAULT 0.5,
    embedding_ref    TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    embedding_id  TEXT PRIMARY KEY,
    scope_id      TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    model         TEXT NOT NULL DEFAULT 'bge-m3:latest',
    dimensions    INTEGER NOT NULL DEFAULT 1024,
    quantization  TEXT NOT NULL DEFAULT 'int8',
    vector_blob   BLOB NOT NULL,
    vector_hash   TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retention_decisions (
    decision_id  TEXT PRIMARY KEY,
    source_type  TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    action       TEXT NOT NULL,
    reason       TEXT NOT NULL DEFAULT '',
    utility_score REAL NOT NULL DEFAULT 0.0,
    before_bytes INTEGER NOT NULL DEFAULT 0,
    after_bytes  INTEGER NOT NULL DEFAULT 0,
    executed_at  TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_baselines_scope ON golden_baselines(scope_id, active);
CREATE INDEX IF NOT EXISTS idx_deltas_scope_run ON run_deltas(scope_id, run_id);
CREATE INDEX IF NOT EXISTS idx_fingerprints_hash ON evidence_fingerprints(content_hash);
CREATE INDEX IF NOT EXISTS idx_fingerprints_scope ON evidence_fingerprints(scope_id, run_id);
CREATE INDEX IF NOT EXISTS idx_summaries_scope ON compact_summaries(scope_id, utility_score);
CREATE INDEX IF NOT EXISTS idx_findings_hash ON findings_memory(canonical_failure_hash);
CREATE INDEX IF NOT EXISTS idx_findings_scope ON findings_memory(scope_id, status);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns_memory(pattern_type, active);
CREATE INDEX IF NOT EXISTS idx_patterns_scope ON patterns_memory(scope_id, last_seen);
CREATE INDEX IF NOT EXISTS idx_trajectories_scope ON reasoning_trajectories(scope_id, utility_score);
CREATE INDEX IF NOT EXISTS idx_embeddings_source ON memory_embeddings(source_type, source_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """
    SQLite-backed persistent store for the memory kernel.

    Thread-safe. WAL mode. Parameterized SQL only.
    """

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        conn = self._get_conn()
        with self._lock:
            conn.executescript(_SCHEMA_SQL)
            conn.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(?,?)",
                (_SCHEMA_VERSION, _now_iso()),
            )
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    # ── Scopes ─────────────────────────────────────────────────────────────────

    def create_scope(
        self,
        scope_id: str,
        project_id: str,
        app_id: str,
        product_area: str = "",
        environment: str = "default",
    ) -> None:
        now = _now_iso()
        with self._lock:
            self._get_conn().execute(
                """INSERT OR IGNORE INTO memory_scopes
                   (scope_id, project_id, app_id, product_area, environment, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (scope_id, project_id, app_id, product_area, environment, now, now),
            )
            self._get_conn().commit()

    def get_scope(self, scope_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM memory_scopes WHERE scope_id=?", (scope_id,)
            ).fetchone()
            return dict(row) if row else None

    def upsert_scope(
        self,
        scope_id: str,
        project_id: str,
        app_id: str,
        product_area: str = "",
        environment: str = "default",
    ) -> None:
        now = _now_iso()
        with self._lock:
            self._get_conn().execute(
                """INSERT INTO memory_scopes
                   (scope_id, project_id, app_id, product_area, environment, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(scope_id) DO UPDATE SET
                     product_area=excluded.product_area,
                     environment=excluded.environment,
                     updated_at=excluded.updated_at""",
                (scope_id, project_id, app_id, product_area, environment, now, now),
            )
            self._get_conn().commit()

    # ── Baselines ──────────────────────────────────────────────────────────────

    def create_baseline(self, baseline: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO golden_baselines
                   (baseline_id, scope_id, baseline_name, baseline_type, app_type,
                    run_id, flow_ids, workflow_fingerprint, screen_fingerprints,
                    api_fingerprints, db_fingerprints, connector_fingerprints,
                    evidence_manifest_hash, summary, created_at, updated_at, active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    baseline["baseline_id"],
                    baseline["scope_id"],
                    baseline.get("baseline_name", ""),
                    baseline.get("baseline_type", "smoke"),
                    baseline.get("app_type", ""),
                    baseline["run_id"],
                    json.dumps(baseline.get("flow_ids", [])),
                    baseline.get("workflow_fingerprint", ""),
                    json.dumps(baseline.get("screen_fingerprints", [])),
                    json.dumps(baseline.get("api_fingerprints", [])),
                    json.dumps(baseline.get("db_fingerprints", [])),
                    json.dumps(baseline.get("connector_fingerprints", [])),
                    baseline.get("evidence_manifest_hash", ""),
                    baseline.get("summary", ""),
                    baseline.get("created_at", _now_iso()),
                    baseline.get("updated_at", _now_iso()),
                    1 if baseline.get("active", True) else 0,
                ),
            )
            self._get_conn().commit()

    def get_active_baseline(self, scope_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM golden_baselines WHERE scope_id=? AND active=1 ORDER BY created_at DESC LIMIT 1",
                (scope_id,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            for field in ("flow_ids", "screen_fingerprints", "api_fingerprints",
                          "db_fingerprints", "connector_fingerprints"):
                d[field] = json.loads(d[field])
            return d

    def set_active_baseline(self, baseline_id: str, scope_id: str) -> None:
        now = _now_iso()
        with self._lock:
            self._get_conn().execute(
                "UPDATE golden_baselines SET active=0, updated_at=? WHERE scope_id=?",
                (now, scope_id),
            )
            self._get_conn().execute(
                "UPDATE golden_baselines SET active=1, updated_at=? WHERE baseline_id=?",
                (now, baseline_id),
            )
            self._get_conn().commit()

    def list_baselines(self, scope_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM golden_baselines WHERE scope_id=? ORDER BY created_at DESC",
                (scope_id,),
            ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                for field in ("flow_ids", "screen_fingerprints", "api_fingerprints",
                              "db_fingerprints", "connector_fingerprints"):
                    d[field] = json.loads(d[field])
                result.append(d)
            return result

    # ── Run Deltas ─────────────────────────────────────────────────────────────

    def store_run_delta(self, delta: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO run_deltas
                   (delta_id, scope_id, baseline_id, run_id, run_type, verdict_change,
                    changed_steps, new_failures, resolved_failures, new_unclear,
                    new_blocked, timing_deltas, connector_deltas, evidence_deltas,
                    fingerprint_deltas, summary_delta, storage_bytes, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    delta["delta_id"],
                    delta["scope_id"],
                    delta.get("baseline_id", ""),
                    delta["run_id"],
                    delta.get("run_type", "regression"),
                    delta.get("verdict_change"),
                    json.dumps(delta.get("changed_steps", [])),
                    json.dumps(delta.get("new_failures", [])),
                    json.dumps(delta.get("resolved_failures", [])),
                    json.dumps(delta.get("new_unclear", [])),
                    json.dumps(delta.get("new_blocked", [])),
                    json.dumps(delta.get("timing_deltas", {})),
                    json.dumps(delta.get("connector_deltas", [])),
                    json.dumps(delta.get("evidence_deltas", [])),
                    json.dumps(delta.get("fingerprint_deltas", [])),
                    delta.get("summary_delta", ""),
                    delta.get("storage_bytes", 0),
                    delta.get("created_at", _now_iso()),
                ),
            )
            self._get_conn().commit()

    def list_run_deltas(self, scope_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM run_deltas WHERE scope_id=? ORDER BY created_at DESC LIMIT ?",
                (scope_id, limit),
            ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                for field in ("changed_steps", "new_failures", "resolved_failures",
                              "new_unclear", "new_blocked", "connector_deltas",
                              "evidence_deltas", "fingerprint_deltas"):
                    d[field] = json.loads(d[field])
                d["timing_deltas"] = json.loads(d["timing_deltas"])
                result.append(d)
            return result

    # ── Evidence Fingerprints ─────────────────────────────────────────────────

    def store_evidence_fingerprint(self, fp: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO evidence_fingerprints
                   (fingerprint_id, scope_id, run_id, step_id, evidence_type,
                    content_hash, perceptual_hash, semantic_hash, schema_hash,
                    state_hash, workflow_hash, size_bytes, compact_size_bytes,
                    duplicate_of, value_score, retention_class, artifact_ref, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    fp["fingerprint_id"],
                    fp["scope_id"],
                    fp["run_id"],
                    fp.get("step_id", ""),
                    fp.get("evidence_type", "unknown"),
                    fp.get("content_hash", ""),
                    fp.get("perceptual_hash", ""),
                    fp.get("semantic_hash", ""),
                    fp.get("schema_hash", ""),
                    fp.get("state_hash", ""),
                    fp.get("workflow_hash", ""),
                    fp.get("size_bytes", 0),
                    fp.get("compact_size_bytes", 0),
                    fp.get("duplicate_of"),
                    fp.get("value_score", 0.5),
                    fp.get("retention_class", "warm"),
                    fp.get("artifact_ref", ""),
                    fp.get("created_at", _now_iso()),
                ),
            )
            self._get_conn().commit()

    def find_duplicate_fingerprint(
        self, content_hash: str, scope_id: str
    ) -> Optional[str]:
        """Return fingerprint_id of existing match, or None."""
        if not content_hash:
            return None
        with self._lock:
            row = self._get_conn().execute(
                """SELECT fingerprint_id FROM evidence_fingerprints
                   WHERE content_hash=? AND scope_id=? AND duplicate_of IS NULL
                   ORDER BY created_at ASC LIMIT 1""",
                (content_hash, scope_id),
            ).fetchone()
            return row[0] if row else None

    # ── Compact Summaries ─────────────────────────────────────────────────────

    def store_compact_summary(self, summary: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO compact_summaries
                   (summary_id, scope_id, source_type, source_id, summary_text,
                    summary_hash, entities, tags, severity, confidence,
                    utility_score, embedding_ref, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    summary["summary_id"],
                    summary["scope_id"],
                    summary.get("source_type", "run"),
                    summary.get("source_id", ""),
                    summary["summary_text"],
                    summary.get("summary_hash", ""),
                    json.dumps(summary.get("entities", [])),
                    json.dumps(summary.get("tags", [])),
                    summary.get("severity", "info"),
                    summary.get("confidence", 0.5),
                    summary.get("utility_score", 0.5),
                    summary.get("embedding_ref"),
                    summary.get("created_at", _now_iso()),
                ),
            )
            self._get_conn().commit()

    def query_high_utility_summaries(
        self, scope_id: str, min_score: float = 0.6, limit: int = 20
    ) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT * FROM compact_summaries
                   WHERE scope_id=? AND utility_score>=?
                   ORDER BY utility_score DESC LIMIT ?""",
                (scope_id, min_score, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Findings ──────────────────────────────────────────────────────────────

    def store_finding(self, finding: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO findings_memory
                   (finding_id, scope_id, canonical_failure_hash, title, failure_type,
                    severity, confidence, first_seen, last_seen, frequency,
                    affected_flows, affected_components, evidence_refs, status,
                    pattern_id, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    finding["finding_id"],
                    finding["scope_id"],
                    finding.get("canonical_failure_hash", ""),
                    finding["title"],
                    finding.get("failure_type", "unknown"),
                    finding.get("severity", "medium"),
                    finding.get("confidence", 0.5),
                    finding.get("first_seen", _now_iso()),
                    finding.get("last_seen", _now_iso()),
                    finding.get("frequency", 1),
                    json.dumps(finding.get("affected_flows", [])),
                    json.dumps(finding.get("affected_components", [])),
                    json.dumps(finding.get("evidence_refs", [])),
                    finding.get("status", "open"),
                    finding.get("pattern_id"),
                    finding.get("created_at", _now_iso()),
                    finding.get("updated_at", _now_iso()),
                ),
            )
            self._get_conn().commit()

    def update_finding_frequency(self, canonical_hash: str, scope_id: str) -> None:
        now = _now_iso()
        with self._lock:
            self._get_conn().execute(
                """UPDATE findings_memory
                   SET frequency=frequency+1, last_seen=?, updated_at=?
                   WHERE canonical_failure_hash=? AND scope_id=?""",
                (now, now, canonical_hash, scope_id),
            )
            self._get_conn().commit()

    def list_findings(
        self, scope_id: str, status: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._lock:
            if status:
                rows = self._get_conn().execute(
                    """SELECT * FROM findings_memory
                       WHERE scope_id=? AND status=?
                       ORDER BY frequency DESC, last_seen DESC LIMIT ?""",
                    (scope_id, status, limit),
                ).fetchall()
            else:
                rows = self._get_conn().execute(
                    """SELECT * FROM findings_memory WHERE scope_id=?
                       ORDER BY frequency DESC, last_seen DESC LIMIT ?""",
                    (scope_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Fixes ─────────────────────────────────────────────────────────────────

    def store_fix(self, fix: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO fixes_memory
                   (fix_id, scope_id, finding_id, fix_attempt_id, commit_hash,
                    change_summary, before_verdict, after_verdict, retest_run_id,
                    regression_status, confidence, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    fix["fix_id"],
                    fix["scope_id"],
                    fix["finding_id"],
                    fix.get("fix_attempt_id", ""),
                    fix.get("commit_hash", ""),
                    fix.get("change_summary", ""),
                    fix.get("before_verdict", "fail"),
                    fix.get("after_verdict", "unknown"),
                    fix.get("retest_run_id", ""),
                    fix.get("regression_status", "unknown"),
                    fix.get("confidence", 0.5),
                    fix.get("created_at", _now_iso()),
                ),
            )
            self._get_conn().commit()

    # ── Patterns ──────────────────────────────────────────────────────────────

    def store_pattern(self, pattern: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO patterns_memory
                   (pattern_id, scope_id, pattern_type, canonical_template, parameters,
                    frequency, confidence, impact_score, first_seen, last_seen,
                    related_findings, related_fixes, embedding_ref, active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pattern["pattern_id"],
                    pattern["scope_id"],
                    pattern["pattern_type"],
                    pattern["canonical_template"],
                    json.dumps(pattern.get("parameters", {})),
                    pattern.get("frequency", 1),
                    pattern.get("confidence", 0.5),
                    pattern.get("impact_score", 0.5),
                    pattern.get("first_seen", _now_iso()),
                    pattern.get("last_seen", _now_iso()),
                    json.dumps(pattern.get("related_findings", [])),
                    json.dumps(pattern.get("related_fixes", [])),
                    pattern.get("embedding_ref"),
                    1 if pattern.get("active", True) else 0,
                ),
            )
            self._get_conn().commit()

    def update_pattern(
        self, pattern_id: str, frequency_delta: int = 1, impact_score: Optional[float] = None
    ) -> None:
        now = _now_iso()
        with self._lock:
            if impact_score is not None:
                self._get_conn().execute(
                    """UPDATE patterns_memory
                       SET frequency=frequency+?, last_seen=?, impact_score=?
                       WHERE pattern_id=?""",
                    (frequency_delta, now, impact_score, pattern_id),
                )
            else:
                self._get_conn().execute(
                    "UPDATE patterns_memory SET frequency=frequency+?, last_seen=? WHERE pattern_id=?",
                    (frequency_delta, now, pattern_id),
                )
            self._get_conn().commit()

    def query_recent_patterns(
        self, scope_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT * FROM patterns_memory
                   WHERE scope_id=? AND active=1
                   ORDER BY frequency DESC, last_seen DESC LIMIT ?""",
                (scope_id, limit),
            ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["parameters"] = json.loads(d["parameters"])
                d["related_findings"] = json.loads(d["related_findings"])
                d["related_fixes"] = json.loads(d["related_fixes"])
                result.append(d)
            return result

    # ── Trajectories ──────────────────────────────────────────────────────────

    def store_trajectory(self, traj: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO reasoning_trajectories
                   (trajectory_id, scope_id, problem_signature, reasoning_steps,
                    evidence_checked, hypotheses, action_taken, outcome, reusable_for,
                    success_count, failure_count, utility_score, embedding_ref,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    traj["trajectory_id"],
                    traj["scope_id"],
                    traj["problem_signature"],
                    json.dumps(traj.get("reasoning_steps", [])),
                    json.dumps(traj.get("evidence_checked", [])),
                    json.dumps(traj.get("hypotheses", [])),
                    traj.get("action_taken", ""),
                    traj.get("outcome", ""),
                    json.dumps(traj.get("reusable_for", [])),
                    traj.get("success_count", 0),
                    traj.get("failure_count", 0),
                    traj.get("utility_score", 0.5),
                    traj.get("embedding_ref"),
                    traj.get("created_at", _now_iso()),
                    traj.get("updated_at", _now_iso()),
                ),
            )
            self._get_conn().commit()

    def list_trajectories(self, scope_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT * FROM reasoning_trajectories WHERE scope_id=?
                   ORDER BY utility_score DESC LIMIT ?""",
                (scope_id, limit),
            ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                for field in ("reasoning_steps", "evidence_checked", "hypotheses", "reusable_for"):
                    d[field] = json.loads(d[field])
                result.append(d)
            return result

    # ── Embeddings ────────────────────────────────────────────────────────────

    def store_embedding(self, emb: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO memory_embeddings
                   (embedding_id, scope_id, source_type, source_id, model,
                    dimensions, quantization, vector_blob, vector_hash, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    emb["embedding_id"],
                    emb["scope_id"],
                    emb["source_type"],
                    emb["source_id"],
                    emb.get("model", "bge-m3:latest"),
                    emb.get("dimensions", 1024),
                    emb.get("quantization", "int8"),
                    emb["vector_blob"],
                    emb.get("vector_hash", ""),
                    emb.get("created_at", _now_iso()),
                ),
            )
            self._get_conn().commit()

    def get_embedding(self, source_type: str, source_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(
                """SELECT * FROM memory_embeddings
                   WHERE source_type=? AND source_id=? ORDER BY created_at DESC LIMIT 1""",
                (source_type, source_id),
            ).fetchone()
            return dict(row) if row else None

    def list_embeddings(self, scope_id: str, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if source_type:
                rows = self._get_conn().execute(
                    "SELECT * FROM memory_embeddings WHERE scope_id=? AND source_type=?",
                    (scope_id, source_type),
                ).fetchall()
            else:
                rows = self._get_conn().execute(
                    "SELECT * FROM memory_embeddings WHERE scope_id=?", (scope_id,)
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Retention ─────────────────────────────────────────────────────────────

    def record_retention_decision(self, decision: Dict[str, Any]) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO retention_decisions
                   (decision_id, source_type, source_id, action, reason,
                    utility_score, before_bytes, after_bytes, executed_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    decision["decision_id"],
                    decision["source_type"],
                    decision["source_id"],
                    decision["action"],
                    decision.get("reason", ""),
                    decision.get("utility_score", 0.0),
                    decision.get("before_bytes", 0),
                    decision.get("after_bytes", 0),
                    decision.get("executed_at"),
                ),
            )
            self._get_conn().commit()

    def list_retention_decisions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM retention_decisions ORDER BY executed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Supplementary query/delete methods ───────────────────────────────────

    def get_scope_by_project(
        self, project_id: str, app_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Return first scope matching project_id (and app_id if given)."""
        with self._lock:
            if app_id:
                row = self._get_conn().execute(
                    "SELECT * FROM memory_scopes WHERE project_id=? AND app_id=? LIMIT 1",
                    (project_id, app_id),
                ).fetchone()
            else:
                row = self._get_conn().execute(
                    "SELECT * FROM memory_scopes WHERE project_id=? LIMIT 1",
                    (project_id,),
                ).fetchone()
            return dict(row) if row else None

    def list_fingerprints(
        self, scope_id: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """List evidence fingerprints for a scope."""
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT * FROM evidence_fingerprints WHERE scope_id=?
                   ORDER BY created_at DESC LIMIT ?""",
                (scope_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_trajectory(self, trajectory_id: str) -> Optional[Dict[str, Any]]:
        """Get single trajectory by ID."""
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM reasoning_trajectories WHERE trajectory_id=? LIMIT 1",
                (trajectory_id,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            for field in ("reasoning_steps", "evidence_checked", "hypotheses", "reusable_for"):
                d[field] = json.loads(d[field])
            return d

    def update_trajectory(
        self,
        trajectory_id: str,
        outcome: Optional[str] = None,
        action_taken: Optional[str] = None,
        utility_score: Optional[float] = None,
        success_count_delta: int = 0,
        failure_count_delta: int = 0,
    ) -> bool:
        """Partial update of trajectory fields."""
        now = _now_iso()
        parts = ["updated_at=?"]
        vals: List[Any] = [now]
        if outcome is not None:
            parts.append("outcome=?")
            vals.append(outcome)
        if action_taken is not None:
            parts.append("action_taken=?")
            vals.append(action_taken)
        if utility_score is not None:
            parts.append("utility_score=?")
            vals.append(utility_score)
        # Integer literals are safe — int() conversion guarantees no injection
        if success_count_delta:
            parts.append(f"success_count=success_count+{int(success_count_delta)}")
        if failure_count_delta:
            parts.append(f"failure_count=failure_count+{int(failure_count_delta)}")
        vals.append(trajectory_id)
        with self._lock:
            self._get_conn().execute(
                f"UPDATE reasoning_trajectories SET {', '.join(parts)} WHERE trajectory_id=?",
                vals,
            )
            self._get_conn().commit()
        return True

    def get_pattern_by_template(self, canonical_template: str, scope_id: str) -> Optional[Dict[str, Any]]:
        """Find pattern by its canonical_template + scope."""
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM patterns_memory WHERE canonical_template=? AND scope_id=? LIMIT 1",
                (canonical_template, scope_id),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["parameters"] = json.loads(d["parameters"])
            d["related_findings"] = json.loads(d["related_findings"])
            d["related_fixes"] = json.loads(d["related_fixes"])
            return d

    def delete_fingerprint(self, fingerprint_id: str) -> None:
        with self._lock:
            self._get_conn().execute(
                "DELETE FROM evidence_fingerprints WHERE fingerprint_id=?", (fingerprint_id,)
            )
            self._get_conn().commit()

    def delete_summary(self, summary_id: str) -> None:
        with self._lock:
            self._get_conn().execute(
                "DELETE FROM compact_summaries WHERE summary_id=?", (summary_id,)
            )
            self._get_conn().commit()

    def delete_finding(self, finding_id: str) -> None:
        with self._lock:
            self._get_conn().execute(
                "DELETE FROM findings_memory WHERE finding_id=?", (finding_id,)
            )
            self._get_conn().commit()

    def delete_pattern(self, pattern_id: str) -> None:
        with self._lock:
            self._get_conn().execute(
                "DELETE FROM patterns_memory WHERE pattern_id=?", (pattern_id,)
            )
            self._get_conn().commit()

    def delete_trajectory(self, trajectory_id: str) -> None:
        with self._lock:
            self._get_conn().execute(
                "DELETE FROM reasoning_trajectories WHERE trajectory_id=?", (trajectory_id,)
            )
            self._get_conn().commit()

    def delete_run_delta(self, delta_id: str) -> None:
        with self._lock:
            self._get_conn().execute(
                "DELETE FROM run_deltas WHERE delta_id=?", (delta_id,)
            )
            self._get_conn().commit()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_memory_stats(self, scope_id: str) -> Dict[str, Any]:
        with self._lock:
            c = self._get_conn()
            baselines = c.execute(
                "SELECT COUNT(*) FROM golden_baselines WHERE scope_id=?", (scope_id,)
            ).fetchone()[0]
            deltas = c.execute(
                "SELECT COUNT(*), COALESCE(SUM(storage_bytes),0) FROM run_deltas WHERE scope_id=?",
                (scope_id,),
            ).fetchone()
            fps = c.execute(
                "SELECT COUNT(*), COALESCE(SUM(size_bytes),0), COALESCE(SUM(compact_size_bytes),0) FROM evidence_fingerprints WHERE scope_id=?",
                (scope_id,),
            ).fetchone()
            summaries = c.execute(
                "SELECT COUNT(*) FROM compact_summaries WHERE scope_id=?", (scope_id,)
            ).fetchone()[0]
            patterns = c.execute(
                "SELECT COUNT(*) FROM patterns_memory WHERE scope_id=?", (scope_id,)
            ).fetchone()[0]
            trajectories = c.execute(
                "SELECT COUNT(*) FROM reasoning_trajectories WHERE scope_id=?", (scope_id,)
            ).fetchone()[0]
            embeddings = c.execute(
                "SELECT COUNT(*) FROM memory_embeddings WHERE scope_id=?", (scope_id,)
            ).fetchone()[0]
            findings = c.execute(
                "SELECT COUNT(*) FROM findings_memory WHERE scope_id=?", (scope_id,)
            ).fetchone()[0]

            raw = fps[1] or 0
            compact = fps[2] or 0
            ratio = round(raw / compact, 2) if compact > 0 else 1.0

        return {
            "scope_id": scope_id,
            "baselines": baselines,
            "run_deltas": deltas[0],
            "delta_storage_bytes": deltas[1],
            "fingerprints": fps[0],
            "raw_bytes_seen": raw,
            "compacted_bytes": compact,
            "compression_ratio": ratio,
            "summaries": summaries,
            "patterns": patterns,
            "trajectories": trajectories,
            "embeddings": embeddings,
            "findings": findings,
        }


# ── Process-level singleton ────────────────────────────────────────────────────

_default_store: Optional[MemoryStore] = None
_store_lock = threading.Lock()


def get_default_store(db_path: Optional[Path] = None) -> MemoryStore:
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = MemoryStore(db_path or _DEFAULT_DB_PATH)
    return _default_store
