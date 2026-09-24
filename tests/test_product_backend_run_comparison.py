"""Deterministic persisted-observation comparison contract; no execution needed."""
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.server import create_product_app


def step(sid="s", status="passed", **extra):
    return dict(step_id=sid, status=status, action_type="api_request",
                provenance="REAL_EXECUTION", **extra)


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "comparison.db"
    app = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(db))
    with TestClient(app) as client:
        storage = app.state.storage

        def put(rid, steps=None, **kw):
            values = dict(id=rid, pack_id="p", app_target_id="a", status="completed",
                          execution_mode="automated", provenance="REAL_EXECUTION",
                          created_at="2026-09-01T00:00:00Z",
                          completed_at="2026-09-02T00:00:00Z" if rid == "c" else "2026-09-01T00:00:00Z",
                          step_results=json.dumps([step()] if steps is None else steps))
            values.update(kw)
            columns = ",".join(values)
            storage._execute(f"INSERT OR REPLACE INTO live_runs ({columns}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))

        put("b")
        put("c", [step(status="failed")])
        yield client, storage, put, db


def get(env, baseline="b", current="c"):
    return env[0].get(f"/api/runs/{current}/compare", params={"baseline_run_id": baseline})


def result(env):
    response = get(env)
    assert response.status_code == 200, response.text
    return response.json()


def row(env):
    return result(env)["step_comparisons"][0]


@pytest.mark.parametrize("baseline,current,code", [("absent", "c", 404), ("b", "absent", 404), ("c", "c", 422), ("", "c", 422), ("   ", "c", 422)])
def test_invalid_pair(env, baseline, current, code):
    assert get(env, baseline, current).status_code == code


def test_baseline_required(env):
    assert env[0].get("/api/runs/c/compare").status_code == 422


@pytest.mark.parametrize("rid", ["b", "c"])
@pytest.mark.parametrize("field,value", [("status", "running"), ("status", "pending"), ("pack_id", "other"), ("app_target_id", "other"), ("pack_id", " "), ("app_target_id", "")])
def test_scope_and_terminal(env, rid, field, value):
    env[2](rid, **{field: value})
    assert get(env).status_code == 409


@pytest.mark.parametrize("before,after", [("passed", "failed"), ("failed", "passed"), ("passed", "passed"), ("failed", "failed"), ("error", "passed"), ("blocked", "failed"), ("inconclusive", "passed"), ("strange", "passed"), ("skipped", "pending")])
def test_transitions(env, before, after):
    env[2]("b", [step(status=before)])
    env[2]("c", [step(status=after)])
    normalize = lambda s: "passed" if s == "passed" else "failed" if s in ("failed", "error") else "inconclusive"
    data = row(env)
    assert data["transition"] == f"{normalize(before)}_to_{normalize(after)}"
    assert (data["baseline_status"], data["comparison_status"]) == (before, after)


def test_reordered_subset_and_one_sided(env):
    env[2]("b", [step("x"), step("s"), step("z")])
    env[2]("c", [step("s", "failed"), step("x"), step("new")], retest_of="b")
    rows = {r["step_id"]: r for r in result(env)["step_comparisons"]}
    assert rows["s"]["transition"] == "passed_to_failed"
    assert rows["x"]["transition"] == "passed_to_passed"
    assert rows["z"]["identity_state"] == "baseline_only"
    assert rows["new"]["identity_state"] == "comparison_only"


@pytest.mark.parametrize("sid", [None, "", "   ", 7])
def test_missing_identity_no_ordinal_fallback(env, sid):
    env[2]("b", [step(sid, step=1)])
    env[2]("c", [step(sid, step=1)])
    rows = result(env)["step_comparisons"]
    assert len(rows) == 2
    assert all(r["identity_state"] == "identity_unavailable" for r in rows)


def test_no_trim_equivalence(env):
    env[2]("c", [step(" s ")])
    assert result(env)["summary_counts"]["matched"] == 0


@pytest.mark.parametrize("rid", ["b", "c"])
def test_duplicate_conflict(env, rid):
    env[2](rid, [step(), step(status="failed")])
    r = row(env)
    assert r["identity_state"] == "identity_conflict"
    assert r["transition"] == "not_comparable"
    assert not r["metric_comparisons"]


def test_case_and_action_conflict(env):
    env[2]("b", [step(case_id="one")])
    env[2]("c", [step(case_id="two")])
    assert row(env)["identity_state"] == "identity_conflict"
    changed = step()
    changed["action_type"] = "navigate"
    env[2]("c", [changed])
    assert "action_mismatch" in row(env)["reason_codes"]


@pytest.mark.parametrize("provenance", ["DRY_RUN", "UNAVAILABLE", "SIMULATED", "DEMO_EXAMPLE", None, "invalid"])
def test_nonreal_step_excluded(env, provenance):
    s = step()
    s["provenance"] = provenance
    env[2]("c", [s])
    assert row(env)["transition"] == "not_comparable"


@pytest.mark.parametrize("mode", ["manual", "automated"])
def test_manual_informational(env, mode):
    env[2]("b", execution_mode="manual")
    env[2]("c", execution_mode=mode)
    assert row(env)["comparison_state"] == "informational"
    assert result(env)["summary_counts"]["passed_to_failed"] == 0


def test_mixed_explicit_steps(env):
    env[2]("c", [step(status="failed")], provenance="MIXED")
    assert row(env)["transition"] == "passed_to_failed"


def test_legacy_provenance_never_promoted(env):
    # Fresh schema is NOT NULL; INSERT OR REPLACE with NULL substitutes default.
    # Empty persisted value represents legacy missing provenance without DDL.
    env[2]("b", provenance="")
    evidence(env, "legacy", "b")
    data = result(env)
    assert data["baseline"]["provenance_basis"] == "inferred"
    assert data["step_comparisons"][0]["transition"] == "not_comparable"


@pytest.mark.parametrize("at,state", [("2026-09-03T00:00:00Z", "reverse"), ("2026-09-02T00:00:00Z", "same_time"), ("2026-09-01T00:00:00Z", "forward")])
def test_chronology(env, at, state):
    env[2]("b", completed_at=at)
    c = result(env)["chronology"]
    assert c["state"] == state
    assert c["basis"] == "completed_at"


def test_chronology_common_basis_and_unknown(env):
    env[2]("b", completed_at="bad", created_at="2026-01-01T00:00:00Z")
    assert result(env)["chronology"]["basis"] == "created_at"
    env[2]("b", completed_at="bad", created_at="2026-01-01T00:00:00")
    assert result(env)["chronology"]["state"] == "unavailable"


def test_metrics(env):
    request = dict(method="GET", url="https://example.com", headers={}, query_params={}, body_json=None)
    env[2]("b", [step(duration_ms=10, response_time_ms=20, status_code=200, **request)])
    env[2]("c", [step(duration_ms=30, response_time_ms=15, status_code=503, **request)])
    r = row(env)
    metrics = {m["key"]: m for m in r["metric_comparisons"]}
    assert metrics["duration_ms"]["delta"] == 20
    assert metrics["response_time_ms"]["delta"] == -5
    assert metrics["status_code"]["baseline_value"] == 200
    assert metrics["status_code"]["comparison_value"] == 503
    assert metrics["status_code"]["delta"] is None


@pytest.mark.parametrize("value", [None, True, -1, float("inf"), float("nan"), "20"])
def test_bad_numeric(env, value):
    env[2]("b", [step(duration_ms=value)])
    env[2]("c", [step(duration_ms=5)])
    metric = next(m for m in row(env)["metric_comparisons"] if m["key"] == "duration_ms")
    assert metric["delta"] is None
    assert metric["baseline_value"] is None


def test_request_identity_required(env):
    env[2]("b", [step(response_time_ms=2)])
    env[2]("c", [step(response_time_ms=4)])
    metric = next(m for m in row(env)["metric_comparisons"] if m["key"] == "response_time_ms")
    assert metric["delta"] is None
    assert metric["reason"] == "request_identity_unavailable"


def evidence(env, eid, rid, sid="s"):
    env[1].create_evidence(dict(id=eid, run_id=rid, step_id=sid, type="screenshot", name="sample",
                               relative_path="not-read.png", mime_type="image/png", size_bytes=2,
                               created_at="2026-01-01T00:00:00Z", provenance="REAL_EXECUTION"))


def test_evidence_ownership_and_deduplication(env):
    evidence(env, "owned", "b")
    evidence(env, "foreign-run", "c")
    evidence(env, "foreign-step", "b", "other")
    env[2]("b", [step(evidence_ids=["owned", "owned", "foreign-run", "foreign-step", "missing"])])
    assert row(env)["baseline_citation"]["evidence_ids"] == ["owned"]


def test_evidence_bound(env):
    for i in range(501):
        evidence(env, f"e-{i:04}", "b")
    data = result(env)
    assert data["coverage"]["complete"] is False
    assert data["coverage"]["omissions"]
    assert row(env)["evidence_comparison"]["baseline_count"] is None


@pytest.mark.parametrize(
    "a,b,state",
    [("Timeout", " timeout ", "same_signature"), ("Timeout", "Network", "different_signature"), ("", "", "unavailable"), ("x" * 513, "x" * 514, "unavailable")],
    ids=["normalized-match", "different", "empty", "oversized"],
)
def test_signature(env, a, b, state):
    env[2]("b", [step(status="failed", error=a)])
    env[2]("c", [step(status="failed", error=b)])
    sig = row(env)["failure_signature_comparison"]
    assert sig["state"] == state
    assert sig["algorithm"] == "history_v1"


def test_signature_http_category_not_exact_code(env):
    env[2]("b", [step(status="failed", error="server error", status_code=500)])
    env[2]("c", [step(status="failed", error="server error", status_code=503)])
    r = row(env)
    assert r["failure_signature_comparison"]["state"] == "same_signature"
    assert next(m for m in r["metric_comparisons"] if m["key"] == "status_code")["comparison_value"] == 503


def test_text_redaction(env):
    secret = "Authorization: Bearer very-secret\nCookie: first=hidden; second=alsohidden\npassword=passsecret\nX-API-Key: keysecret\n-----BEGIN PRIVATE KEY-----\nkeymaterial\n-----END PRIVATE KEY-----"
    env[2]("b", [step(error=secret, expected={"nested": {"apiKey": "nestedsecret"}})], error=secret)
    text = json.dumps(result(env))
    for value in ["very-secret", "hidden", "alsohidden", "passsecret", "keysecret", "keymaterial", "nestedsecret"]:
        assert value not in text


def test_no_enriched_loading_or_mutation(env, monkeypatch, tmp_path):
    artifact = tmp_path / "artifacts" / "fixture.png"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_bytes(b"fixture evidence")
    memory = tmp_path / "memory_kernel.db"
    memory.write_bytes(b"fixture memory")
    def snapshot():
        with sqlite3.connect(env[3]) as conn:
            return list(conn.iterdump())
    before = snapshot()
    files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (artifact, memory)}
    def forbidden(*args, **kwargs):
        pytest.fail("comparison accessed execution/enriched data")
    monkeypatch.setattr(env[1], "get_run", forbidden)
    monkeypatch.setattr(env[1], "get_validation_pack", forbidden)
    first = result(env)
    assert result(env) == first
    env[1].close()
    assert result(env) == first
    assert snapshot() == before
    assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (artifact, memory)} == files
    assert first["comparability_warnings"]
    assert "authoritative" not in first


def test_unexpected_error_sanitized(env, monkeypatch):
    def fail(*args):
        raise RuntimeError("password=NEVER-RETURN-THIS")
    monkeypatch.setattr(env[1], "load_run_comparison_snapshot", fail, raising=False)
    response = get(env)
    assert response.status_code == 500
    assert "NEVER-RETURN-THIS" not in response.text


@pytest.mark.parametrize("action", ["assert_status", "assert_json_path", "assert_api_response_time_under"])
def test_supported_api_action_timing(env, action):
    s = step(method="GET", url="https://example.com", response_time_ms=10, headers={}, query_params={}, body_json=None)
    s["action_type"] = action
    env[2]("b", [s])
    env[2]("c", [{**s, "response_time_ms": 25}])
    metric = next(m for m in row(env)["metric_comparisons"] if m["key"] == "response_time_ms")
    assert metric["delta"] == 15


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("equal", [True, False])
def test_unique_owned_type_hash_comparison(env, count, equal):
    for rid in ("b", "c"):
        for i in range(count):
            eid = f"{rid}-{i}"
            evidence(env, eid, rid)
            digest = "a" * 64 if rid == "b" or equal else "b" * 64
            env[1]._execute("UPDATE evidence_files SET sha256 = ? WHERE id = ?", (digest, eid))
    summary = row(env)["evidence_comparison"]
    assert summary["hash_comparison"] == ("unavailable" if count > 1 else "same_hash" if equal else "different_hash")


@pytest.mark.parametrize(
    "payload",
    ["not json", "{}", '["not a result"]', json.dumps([step()] * 501), json.dumps([step(notes="x" * 2_097_152)])],
    ids=["invalid-json", "not-array", "invalid-result", "too-many-results", "oversized-result"],
)
def test_unusable_result_set_never_invents_one_sided(env, payload):
    env[2]("b", step_results=payload)
    data = result(env)
    assert data["coverage"]["complete"] is False
    assert data["step_comparisons"] == []
    assert data["comparability"]["state"] == "unavailable"


def test_no_current_definition_dependence(env):
    before = result(env)
    env[1]._execute("INSERT INTO validation_packs (id, project_id, name, steps, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("p", "project", "Current title", '[{"step_id":"different","target":"new selector"}]', "now", "now"))
    assert result(env) == before
    env[1]._execute("UPDATE validation_packs SET steps = ?, name = ? WHERE id = ?", ("[]", "Changed", "p"))
    assert result(env) == before


def test_artifact_reads_and_execution_paths_forbidden(env, monkeypatch, tmp_path):
    import builtins
    from qa_ai.ai.evidence_evaluator import AIEvidenceEvaluator
    from qa_ai.ai.root_cause_suggester import AIRootCauseSuggester
    from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
    from qa_ai.product_backend.run_manager import RunManager
    from qa_ai.product_backend.routers import live_runs

    artifact = tmp_path / "artifacts" / "not-read.png"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_bytes(b"not decoded by comparison")
    with sqlite3.connect(tmp_path / "memory_kernel.db") as conn:
        conn.execute("CREATE TABLE sentinel (value TEXT)")
        conn.execute("INSERT INTO sentinel VALUES ('untouched')")
    evidence(env, "file", "b")
    def files():
        # WAL read marks legitimately change in shared-memory coordination even
        # for SELECT-only transactions. Keep its existence, not its byte hash.
        return {str(p): "coordination" if p.name.endswith("-shm") else hashlib.sha256(p.read_bytes()).hexdigest()
                for p in tmp_path.rglob("*") if p.is_file()}
    before = files()
    def forbidden(*args, **kw):
        pytest.fail("Forbidden comparison side effect or artifact read")
    original_open = builtins.open
    original_path_open = Path.open
    def guarded_open(path, *args, **kw):
        if isinstance(path, (str, Path)) and str(tmp_path / "artifacts") in str(path):
            forbidden()
        return original_open(path, *args, **kw)
    def guarded_path_open(path, *args, **kw):
        if str(tmp_path / "artifacts") in str(path):
            forbidden()
        return original_path_open(path, *args, **kw)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", guarded_open)
        patch.setattr(Path, "open", guarded_path_open)
        for cls, method in [(RunManager, "start_run"), (RunManager, "schedule_run"),
                            (RunManager, "_execute"), (MemoryAPIService, "ingest_run"),
                            (AIEvidenceEvaluator, "evaluate_run"), (AIRootCauseSuggester, "suggest"),
                            (live_runs, "retest_failed")]:
            patch.setattr(cls, method, forbidden)
        result(env)
        result(env)
    assert files() == before


def test_snapshot_is_one_read_transaction(env):
    trace = []
    env[1]._get_conn().set_trace_callback(trace.append)
    result(env)
    env[1]._get_conn().set_trace_callback(None)
    assert trace[0] == "BEGIN"
    assert trace[-1] == "ROLLBACK"
    assert all(sql.startswith("SELECT") for sql in trace[1:-1])


@pytest.mark.parametrize("status", ["cancelled", "failed", "completed"])
def test_terminal_partial_observations(env, status):
    env[2]("c", [step(status="failed")], status=status)
    assert row(env)["transition"] == "passed_to_failed"


def test_exact_configuration_warning(env):
    assert "Execution configuration continuity between these runs cannot be fully verified." in result(env)["comparability_warnings"]


@pytest.mark.parametrize("key", ["body", "body_json", "headers", "headers_json", "query_params", "query_params_json"])
def test_known_request_configuration_difference_withholds_timing(env, key):
    s = step(method="POST", url="https://example.com", response_time_ms=10, headers={}, query_params={}, body_json=None)
    env[2]("b", [{**s, key: {"value": "one"}}])
    env[2]("c", [{**s, key: {"value": "two"}, "response_time_ms": 20}])
    metric = next(m for m in row(env)["metric_comparisons"] if m["key"] == "response_time_ms")
    assert metric["delta"] is None


def test_signature_guard_uses_effective_history_fields(env):
    env[2]("b", [step(status="failed", error_code=" ", code="ONE")])
    env[2]("c", [step(status="failed", error_code=" ", code="TWO")])
    assert row(env)["failure_signature_comparison"]["state"] == "unavailable"


def test_method_url_alone_cannot_prove_request_identity(env):
    s = step(method="GET", url="https://example.com", response_time_ms=10)
    env[2]("b", [s])
    env[2]("c", [{**s, "response_time_ms": 20}])
    assert next(m for m in row(env)["metric_comparisons"] if m["key"] == "response_time_ms")["delta"] is None


def test_redacted_request_identity_is_unknown(env):
    s = step(method="POST", url="https://example.com", response_time_ms=10,
             headers={"Authorization": "[REDACTED]"}, query_params={}, body_json=None)
    env[2]("b", [s])
    env[2]("c", [{**s, "response_time_ms": 20}])
    assert next(m for m in row(env)["metric_comparisons"] if m["key"] == "response_time_ms")["delta"] is None
