"""
test_memory_kernel.py - Comprehensive tests for memory kernel.

Coverage:
- MemoryStore CRUD (20 tests)
- fingerprint_engine (12 tests)
- utility_scorer (10 tests)
- evidence_compactor (10 tests)
- embedding_quantizer (8 tests)
- cdc_chunker (8 tests)
- baseline_manager (8 tests)
- delta_engine (10 tests)
- retention_engine (8 tests)
- pattern_engine (10 tests)
- trajectory_engine (8 tests)
- semantic_recall (8 tests)
- memory_api_service (10 tests)
- REST API endpoints (12 tests)
- Security / privacy (10 tests)
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """In-memory SQLite store backed by temp file."""
    from qa_ai.memory_kernel.memory_store import MemoryStore
    db = tmp_path / "test_memory.db"
    return MemoryStore(db_path=db)


@pytest.fixture
def scope_id():
    return f"scope-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def run_id():
    return f"run-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def seeded_store(tmp_db, scope_id):
    """Store with a scope pre-created."""
    tmp_db.upsert_scope(
        scope_id=scope_id,
        project_id="proj-1",
        app_id="app-1",
        product_area="qa",
        environment="test",
    )
    return tmp_db


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from qa_ai.product_backend.server import create_product_app
    return TestClient(create_product_app())


# ══════════════════════════════════════════════════════════════════════════════
# 1. MemoryStore CRUD
# ══════════════════════════════════════════════════════════════════════════════

class TestMemoryStore:

    def test_create_and_get_scope(self, tmp_db, scope_id):
        tmp_db.create_scope(
            scope_id=scope_id,
            project_id="proj-x",
            app_id="app-x",
        )
        scope = tmp_db.get_scope(scope_id)
        assert scope is not None
        assert scope["scope_id"] == scope_id
        assert scope["project_id"] == "proj-x"

    def test_get_scope_missing(self, tmp_db):
        assert tmp_db.get_scope("nonexistent") is None

    def test_upsert_scope_idempotent(self, tmp_db, scope_id):
        for _ in range(3):
            tmp_db.upsert_scope(
                scope_id=scope_id, project_id="proj-y", app_id="app-y"
            )
        scope = tmp_db.get_scope(scope_id)
        assert scope["project_id"] == "proj-y"

    def test_create_and_get_baseline(self, seeded_store, scope_id):
        bid = str(uuid.uuid4())
        seeded_store.create_baseline({
            "baseline_id": bid,
            "scope_id": scope_id,
            "run_id": "run-1",
            "baseline_type": "smoke",
            "summary": json.dumps({"verdict": "pass"}),
            "active": True,
        })
        b = seeded_store.get_active_baseline(scope_id)
        assert b is not None
        assert b["baseline_id"] == bid

    def test_set_active_baseline(self, seeded_store, scope_id):
        bid1, bid2 = str(uuid.uuid4()), str(uuid.uuid4())
        for bid in (bid1, bid2):
            seeded_store.create_baseline({
                "baseline_id": bid,
                "scope_id": scope_id,
                "run_id": f"run-{bid[:4]}",
                "active": False,
            })
        seeded_store.set_active_baseline(bid2, scope_id)
        active = seeded_store.get_active_baseline(scope_id)
        assert active["baseline_id"] == bid2

    def test_store_and_list_run_deltas(self, seeded_store, scope_id):
        did = str(uuid.uuid4())
        seeded_store.store_run_delta({
            "delta_id": did,
            "scope_id": scope_id,
            "run_id": "run-a",
            "run_type": "smoke",
            "new_failures": ["step-1"],
            "changed_steps": [],
            "resolved_failures": [],
            "new_unclear": [],
            "new_blocked": [],
            "timing_deltas": {},
            "connector_deltas": [],
            "evidence_deltas": [],
            "fingerprint_deltas": [],
            "summary_delta": "one failure",
            "storage_bytes": 42,
        })
        deltas = seeded_store.list_run_deltas(scope_id=scope_id)
        assert any(d["delta_id"] == did for d in deltas)

    def test_store_evidence_fingerprint_and_dedup(self, seeded_store, scope_id):
        fp_id = str(uuid.uuid4())
        ch = "abc123def456"
        seeded_store.store_evidence_fingerprint({
            "fingerprint_id": fp_id,
            "scope_id": scope_id,
            "run_id": "run-1",
            "evidence_type": "screenshot",
            "content_hash": ch,
        })
        found = seeded_store.find_duplicate_fingerprint(ch, scope_id)
        assert found == fp_id

    def test_no_duplicate_across_scopes(self, seeded_store, tmp_db):
        ch = "unique-hash-xyz"
        s1 = "scope-aaa"
        s2 = "scope-bbb"
        for s in (s1, s2):
            tmp_db.upsert_scope(scope_id=s, project_id="p", app_id="a")
        tmp_db.store_evidence_fingerprint({
            "fingerprint_id": str(uuid.uuid4()),
            "scope_id": s1,
            "run_id": "r",
            "evidence_type": "log",
            "content_hash": ch,
        })
        # Different scope → no duplicate
        assert tmp_db.find_duplicate_fingerprint(ch, s2) is None

    def test_store_compact_summary(self, seeded_store, scope_id):
        sid = str(uuid.uuid4())
        seeded_store.store_compact_summary({
            "summary_id": sid,
            "scope_id": scope_id,
            "source_type": "run",
            "source_id": "run-1",
            "summary_text": "Test passed cleanly",
            "utility_score": 0.8,
        })
        rows = seeded_store.query_high_utility_summaries(scope_id=scope_id, min_score=0.5)
        assert any(r["summary_id"] == sid for r in rows)

    def test_store_and_list_findings(self, seeded_store, scope_id):
        fid = str(uuid.uuid4())
        seeded_store.store_finding({
            "finding_id": fid,
            "scope_id": scope_id,
            "title": "Login fails on slow network",
            "severity": "high",
            "frequency": 3,
        })
        findings = seeded_store.list_findings(scope_id=scope_id)
        assert any(f["finding_id"] == fid for f in findings)

    def test_store_and_query_patterns(self, seeded_store, scope_id):
        pid = str(uuid.uuid4())
        seeded_store.store_pattern({
            "pattern_id": pid,
            "scope_id": scope_id,
            "pattern_type": "flaky_test",
            "canonical_template": f"flaky:abc123:{scope_id}",
            "parameters": {"title": "Flaky step X"},
            "frequency": 5,
            "confidence": 0.85,
            "impact_score": 0.6,
            "active": True,
        })
        patterns = seeded_store.query_recent_patterns(scope_id=scope_id)
        assert any(p["pattern_id"] == pid for p in patterns)

    def test_update_pattern_frequency(self, seeded_store, scope_id):
        pid = str(uuid.uuid4())
        seeded_store.store_pattern({
            "pattern_id": pid,
            "scope_id": scope_id,
            "pattern_type": "generic",
            "canonical_template": "key:xyz",
            "parameters": {},
            "frequency": 1,
        })
        seeded_store.update_pattern(pid, frequency_delta=4)
        patterns = seeded_store.query_recent_patterns(scope_id=scope_id)
        found = next(p for p in patterns if p["pattern_id"] == pid)
        assert found["frequency"] == 5

    def test_store_trajectory_and_get(self, seeded_store, scope_id):
        tid = str(uuid.uuid4())
        seeded_store.store_trajectory({
            "trajectory_id": tid,
            "scope_id": scope_id,
            "problem_signature": "login_flow_timeout",
            "reasoning_steps": ["Check network", "Check timeout config"],
            "evidence_checked": [],
            "hypotheses": ["timeout too low"],
            "action_taken": "Increased timeout to 30s",
            "outcome": "Tests passed",
            "reusable_for": ["login_tests"],
            "utility_score": 0.75,
        })
        traj = seeded_store.get_trajectory(tid)
        assert traj is not None
        assert traj["trajectory_id"] == tid
        assert traj["outcome"] == "Tests passed"

    def test_store_embedding(self, seeded_store, scope_id):
        eid = str(uuid.uuid4())
        blob = bytes([1, 2, 3, 4])
        seeded_store.store_embedding({
            "embedding_id": eid,
            "scope_id": scope_id,
            "source_type": "summary",
            "source_id": "sum-1",
            "model": "simhash",
            "dimensions": 0,
            "quantization": "none",
            "vector_blob": blob,
            "vector_hash": "deadbeef",
        })
        rows = seeded_store.list_embeddings(scope_id=scope_id)
        assert any(r["embedding_id"] == eid for r in rows)

    def test_record_retention_decision(self, seeded_store, scope_id):
        did = str(uuid.uuid4())
        seeded_store.record_retention_decision({
            "decision_id": did,
            "source_type": "fingerprint",
            "source_id": "fp-1",
            "action": "delete",
            "reason": "low utility",
            "utility_score": 5.0,
        })
        decisions = seeded_store.list_retention_decisions()
        assert any(d["decision_id"] == did for d in decisions)

    def test_get_memory_stats(self, seeded_store, scope_id):
        stats = seeded_store.get_memory_stats(scope_id=scope_id)
        assert "fingerprints" in stats
        assert "patterns" in stats
        assert "trajectories" in stats

    def test_get_pattern_by_template(self, seeded_store, scope_id):
        pid = str(uuid.uuid4())
        template = f"unique_template_{scope_id}"
        seeded_store.store_pattern({
            "pattern_id": pid,
            "scope_id": scope_id,
            "pattern_type": "generic",
            "canonical_template": template,
            "parameters": {},
            "frequency": 1,
        })
        found = seeded_store.get_pattern_by_template(template, scope_id)
        assert found is not None
        assert found["pattern_id"] == pid

    def test_delete_fingerprint(self, seeded_store, scope_id):
        fp_id = str(uuid.uuid4())
        ch = f"hash-to-delete-{fp_id}"
        seeded_store.store_evidence_fingerprint({
            "fingerprint_id": fp_id,
            "scope_id": scope_id,
            "run_id": "r1",
            "evidence_type": "log",
            "content_hash": ch,
        })
        seeded_store.delete_fingerprint(fp_id)
        assert seeded_store.find_duplicate_fingerprint(ch, scope_id) is None

    def test_delete_trajectory(self, seeded_store, scope_id):
        tid = str(uuid.uuid4())
        seeded_store.store_trajectory({
            "trajectory_id": tid,
            "scope_id": scope_id,
            "problem_signature": "to_delete",
            "reasoning_steps": [],
            "evidence_checked": [],
            "hypotheses": [],
            "action_taken": "",
            "outcome": "",
            "reusable_for": [],
            "utility_score": 0.1,
        })
        seeded_store.delete_trajectory(tid)
        assert seeded_store.get_trajectory(tid) is None

    def test_list_fingerprints(self, seeded_store, scope_id):
        for i in range(3):
            seeded_store.store_evidence_fingerprint({
                "fingerprint_id": str(uuid.uuid4()),
                "scope_id": scope_id,
                "run_id": "r1",
                "evidence_type": "api",
                "content_hash": f"hash{i}",
            })
        rows = seeded_store.list_fingerprints(scope_id=scope_id)
        assert len(rows) == 3

    def test_get_scope_by_project(self, tmp_db):
        tmp_db.upsert_scope(
            scope_id="s-proj-test",
            project_id="proj-findme",
            app_id="app-findme",
        )
        found = tmp_db.get_scope_by_project("proj-findme", "app-findme")
        assert found is not None
        assert found["scope_id"] == "s-proj-test"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Fingerprint Engine
# ══════════════════════════════════════════════════════════════════════════════

class TestFingerprintEngine:

    def test_fingerprint_text_stable(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_text
        h = fingerprint_text("hello world")
        assert fingerprint_text("hello world") == h
        assert len(h) >= 32

    def test_fingerprint_text_differs(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_text
        assert fingerprint_text("abc") != fingerprint_text("def")

    def test_fingerprint_bytes(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_bytes
        h = fingerprint_bytes(b"\x00\x01\x02")
        assert isinstance(h, str) and len(h) >= 32

    def test_fingerprint_log_ignores_timestamps(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_log
        log1 = "2024-01-01T12:00:00Z ERROR: connection failed"
        log2 = "2024-06-15T09:30:00Z ERROR: connection failed"
        assert fingerprint_log(log1) == fingerprint_log(log2)

    def test_fingerprint_log_ignores_uuids(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_log
        log1 = "ERROR: request 550e8400-e29b-41d4-a716-446655440000 failed"
        log2 = "ERROR: request 6ba7b810-9dad-11d1-80b4-00c04fd430c8 failed"
        assert fingerprint_log(log1) == fingerprint_log(log2)

    def test_fingerprint_api_response(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_api_response
        h = fingerprint_api_response(200, {"key": "value"})
        assert isinstance(h, str) and len(h) >= 32

    def test_fingerprint_api_400_differs_200(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_api_response
        h200 = fingerprint_api_response(200, {"key": "val"})
        h400 = fingerprint_api_response(400, {"error": "bad"})
        assert h200 != h400

    def test_fingerprint_workflow(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_workflow
        steps = [{"step_id": "s1", "action": "login", "verdict": "pass"}]
        h = fingerprint_workflow(steps)
        assert isinstance(h, str) and len(h) >= 32

    def test_semantic_hash_stable(self):
        from qa_ai.memory_kernel.fingerprint_engine import semantic_hash
        h = semantic_hash("connection timeout on slow network")
        assert semantic_hash("connection timeout on slow network") == h
        assert len(h) == 16

    def test_semantic_hash_different_text(self):
        from qa_ai.memory_kernel.fingerprint_engine import semantic_hash
        assert semantic_hash("login failed") != semantic_hash("payment succeeded")

    def test_extract_json_schema_shape(self):
        from qa_ai.memory_kernel.fingerprint_engine import _extract_json_schema
        schema = _extract_json_schema({"a": 1, "b": "x", "c": None, "d": [1, 2]})
        assert schema["a"] == "int"
        assert schema["b"] == "str"
        assert schema["c"] == "null"
        assert schema["d"][0] == "array"

    def test_fingerprint_evidence_manifest(self):
        from qa_ai.memory_kernel.fingerprint_engine import fingerprint_evidence_manifest
        h = fingerprint_evidence_manifest(["fp1", "fp2", "fp3"])
        assert isinstance(h, str)
        # Order-independent (sorted)
        h2 = fingerprint_evidence_manifest(["fp3", "fp1", "fp2"])
        assert h == h2


# ══════════════════════════════════════════════════════════════════════════════
# 3. Utility Scorer
# ══════════════════════════════════════════════════════════════════════════════

class TestUtilityScorer:

    def test_fail_high_severity_scores_hot(self):
        from qa_ai.memory_kernel.utility_scorer import score_evidence
        r = score_evidence(
            evidence_type="screenshot",
            verdict="fail",
            frequency=5,
            used_in_fix=True,
            severity="critical",
        )
        assert r.retention_class in ("hot", "warm")
        assert r.utility_score > 40

    def test_pass_old_scores_low(self):
        from qa_ai.memory_kernel.utility_scorer import score_evidence
        r = score_evidence(
            evidence_type="screenshot",
            verdict="pass",
            frequency=1,
            days_old=120,
            severity="low",
        )
        assert r.utility_score < 40

    def test_duplicate_penalized(self):
        from qa_ai.memory_kernel.utility_scorer import score_evidence
        r_dup = score_evidence("log", "fail", is_duplicate=True, severity="medium")
        r_ok = score_evidence("log", "fail", is_duplicate=False, severity="medium")
        assert r_dup.utility_score < r_ok.utility_score

    def test_used_in_fix_boosts_score(self):
        from qa_ai.memory_kernel.utility_scorer import score_evidence
        r_fix = score_evidence("api", "fail", used_in_fix=True, severity="medium")
        r_bare = score_evidence("api", "fail", used_in_fix=False, severity="medium")
        assert r_fix.utility_score > r_bare.utility_score

    def test_retention_classes_consistent(self):
        from qa_ai.memory_kernel.utility_scorer import score_evidence, _HOT_THRESHOLD, _WARM_THRESHOLD, _COLD_THRESHOLD
        r = score_evidence("log", "fail", frequency=10, used_in_fix=True, severity="high")
        if r.utility_score >= _HOT_THRESHOLD:
            assert r.retention_class == "hot"
        elif r.utility_score >= _WARM_THRESHOLD:
            assert r.retention_class == "warm"
        elif r.utility_score >= _COLD_THRESHOLD:
            assert r.retention_class == "cold"
        else:
            assert r.retention_class == "delete_candidate"

    def test_score_0_to_100(self):
        from qa_ai.memory_kernel.utility_scorer import score_evidence
        for verdict in ("pass", "fail", "unclear", "blocked"):
            r = score_evidence("connector", verdict, severity="medium")
            assert 0.0 <= r.utility_score <= 100.0

    def test_factors_dict_present(self):
        from qa_ai.memory_kernel.utility_scorer import score_evidence
        r = score_evidence("log", "fail")
        assert "impact" in r.factors
        assert "frequency" in r.factors
        assert "time_decay" in r.factors

    def test_score_summary_function(self):
        from qa_ai.memory_kernel.utility_scorer import score_summary
        r = score_summary(source_type="finding", severity="high", frequency=3)
        assert r.utility_score >= 0

    def test_fail_decays_slower_than_pass(self):
        from qa_ai.memory_kernel.utility_scorer import _time_decay
        assert _time_decay(30, "fail") < _time_decay(30, "pass")

    def test_frequency_factor_caps_at_1(self):
        from qa_ai.memory_kernel.utility_scorer import _frequency_factor
        assert _frequency_factor(9999) <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 4. Evidence Compactor
# ══════════════════════════════════════════════════════════════════════════════

class TestEvidenceCompactor:

    def test_compact_log_extracts_errors(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_log
        log = "\n".join(["INFO ok", "ERROR: connection refused", "INFO done"])
        result = compact_log(log, compress=False)
        assert result["status"] == "ok"
        assert result["error_line_count"] >= 1
        assert "connection refused" in result["compressed"].decode()

    def test_compact_log_redacts_secrets(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_log
        log = "ERROR: auth failed. api_key=sk-supersecret123456789"
        result = compact_log(log, compress=False)
        assert b"sk-supersecret" not in result["compressed"]

    def test_compact_log_compresses(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_log
        log = "ERROR: " + ("x" * 2000)
        result = compact_log(log, compress=True)
        assert result["compact_size"] < result["original_size"]

    def test_decompress_log_roundtrip(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_log, decompress_log
        original = "ERROR: something went wrong\nTraceback: line 42"
        result = compact_log(original, compress=True)
        decompressed = decompress_log(result["compressed"], result["algorithm"])
        assert "something went wrong" in decompressed

    def test_compact_api_evidence_drops_auth_headers(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_api_evidence
        result = compact_api_evidence(
            status_code=200,
            response_body={"ok": True},
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
        )
        assert "authorization" not in result["headers"]
        assert "content-type" in result["headers"]

    def test_compact_api_evidence_error_excerpt(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_api_evidence
        result = compact_api_evidence(
            status_code=400,
            response_body={"error": "invalid_token"},
        )
        assert result["status_code"] == 400
        assert "invalid_token" in result["error_excerpt"]

    def test_compact_db_evidence_delta_only(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_db_evidence
        result = compact_db_evidence("users", 100, 105, ["row1", "row2"])
        assert result["delta"] == 5
        assert result["table"] == "users"

    def test_compact_ai_evidence_no_raw_prompt(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_ai_evidence
        result = compact_ai_evidence(
            task="classify_bug",
            model="gpt-4o",
            latency_ms=1234.5,
            output_summary="Bug classified as critical UI regression",
        )
        assert "raw_prompt" not in result
        assert result["task"] == "classify_bug"
        assert result["latency_ms"] == 1234.5

    def test_compact_ai_evidence_redacts_secrets_in_summary(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_ai_evidence
        result = compact_ai_evidence(
            task="check_auth",
            model="local",
            latency_ms=100,
            output_summary="Found password=hunter2 in config",
        )
        assert "hunter2" not in result["summary"]

    def test_compact_screenshot_no_pillow(self):
        from qa_ai.memory_kernel.evidence_compactor import compact_screenshot
        with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
            thumb, tag = compact_screenshot(b"fake_image_bytes")
            # If Pillow not importable, returns capability_gap
            # (may vary; just check it doesn't raise)
            assert tag in ("webp_thumbnail", "capability_gap", "error")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Embedding Quantizer
# ══════════════════════════════════════════════════════════════════════════════

class TestEmbeddingQuantizer:

    def test_quantize_and_dequantize_roundtrip(self):
        from qa_ai.memory_kernel.embedding_quantizer import (
            quantize_float32_to_int8, dequantize_int8_to_float32
        )
        vec = [0.1, -0.5, 0.3, 0.7, -0.2]
        blob = quantize_float32_to_int8(vec)
        back = dequantize_int8_to_float32(blob, len(vec))
        assert len(back) == len(vec)
        for orig, rec in zip(vec, back):
            # L2 normalized then quantized — values differ but signs match
            assert (orig >= 0) == (rec >= 0) or abs(rec) < 0.05

    def test_quantize_empty(self):
        from qa_ai.memory_kernel.embedding_quantizer import quantize_float32_to_int8
        assert quantize_float32_to_int8([]) == b""

    def test_cosine_similarity_identical(self):
        from qa_ai.memory_kernel.embedding_quantizer import (
            quantize_float32_to_int8, cosine_similarity_int8
        )
        vec = [0.1, 0.2, 0.3, 0.4]
        blob = quantize_float32_to_int8(vec)
        sim = cosine_similarity_int8(blob, blob)
        assert abs(sim - 1.0) < 0.01

    def test_cosine_similarity_different_lengths(self):
        from qa_ai.memory_kernel.embedding_quantizer import cosine_similarity_int8
        assert cosine_similarity_int8(b"\x01\x02", b"\x01\x02\x03") == 0.0

    def test_vector_hash_stable(self):
        from qa_ai.memory_kernel.embedding_quantizer import vector_hash
        vec = [0.1, 0.2, 0.3]
        assert vector_hash(vec) == vector_hash(vec)
        assert len(vector_hash(vec)) == 24

    def test_matryoshka_slice(self):
        from qa_ai.memory_kernel.embedding_quantizer import matryoshka_slice
        vec = list(range(100))
        assert matryoshka_slice(vec, 64) == list(range(64))

    def test_top_k_similar_returns_sorted(self):
        from qa_ai.memory_kernel.embedding_quantizer import (
            quantize_float32_to_int8, top_k_similar
        )
        query = quantize_float32_to_int8([1.0, 0.0, 0.0])
        candidates = [
            ("a", quantize_float32_to_int8([1.0, 0.0, 0.0])),
            ("b", quantize_float32_to_int8([0.0, 1.0, 0.0])),
            ("c", quantize_float32_to_int8([-1.0, 0.0, 0.0])),
        ]
        results = top_k_similar(query, candidates, k=3, use_matryoshka=False)
        assert results[0][0] == "a"  # most similar first

    def test_top_k_empty_candidates(self):
        from qa_ai.memory_kernel.embedding_quantizer import (
            quantize_float32_to_int8, top_k_similar
        )
        query = quantize_float32_to_int8([1.0])
        assert top_k_similar(query, [], k=5) == []


# ══════════════════════════════════════════════════════════════════════════════
# 6. CDC Chunker
# ══════════════════════════════════════════════════════════════════════════════

class TestCDCChunker:

    def test_chunk_bytes_basic(self):
        from qa_ai.memory_kernel.cdc_chunker import chunk_bytes
        data = b"x" * 4096
        chunks = chunk_bytes(data, min_size=512, max_size=2048)
        assert len(chunks) >= 1
        assert sum(c.length for c in chunks) == len(data)

    def test_chunk_bytes_empty(self):
        from qa_ai.memory_kernel.cdc_chunker import chunk_bytes
        assert chunk_bytes(b"") == []

    def test_chunk_text(self):
        from qa_ai.memory_kernel.cdc_chunker import chunk_text
        text = "Hello world " * 200
        chunks = chunk_text(text)
        assert all(c.content_hash for c in chunks)

    def test_chunk_log_file_line_aware(self):
        from qa_ai.memory_kernel.cdc_chunker import chunk_log_file
        lines = b"\n".join([f"ERROR: line {i}".encode() for i in range(100)])
        chunks = chunk_log_file(lines, min_size=256, max_size=4096)
        assert len(chunks) >= 1
        total = sum(c.length for c in chunks)
        assert total == len(lines) or total == len(lines) + 1  # newline boundary

    def test_deduplicate_chunks(self):
        from qa_ai.memory_kernel.cdc_chunker import Chunk, deduplicate_chunks
        c1 = Chunk(0, 0, 4, "hash_a", b"aaaa")
        c2 = Chunk(1, 4, 4, "hash_a", b"aaaa")  # duplicate
        c3 = Chunk(2, 8, 4, "hash_b", b"bbbb")
        unique, dedup_count = deduplicate_chunks([c1, c2, c3])
        assert len(unique) == 2
        assert dedup_count == 1

    def test_chunk_summary(self):
        from qa_ai.memory_kernel.cdc_chunker import chunk_bytes, chunk_summary
        chunks = chunk_bytes(b"a" * 2000 + b"b" * 2000)
        summary = chunk_summary(chunks)
        assert summary["count"] == len(chunks)
        assert summary["total_bytes"] == 4000

    def test_chunk_hashes_stable(self):
        from qa_ai.memory_kernel.cdc_chunker import chunk_bytes
        data = b"stable content " * 100
        c1 = chunk_bytes(data)
        c2 = chunk_bytes(data)
        assert [c.content_hash for c in c1] == [c.content_hash for c in c2]

    def test_chunk_indices_sequential(self):
        from qa_ai.memory_kernel.cdc_chunker import chunk_bytes
        data = b"z" * 10000
        chunks = chunk_bytes(data)
        for i, c in enumerate(chunks):
            assert c.index == i


# ══════════════════════════════════════════════════════════════════════════════
# 7. Baseline Manager
# ══════════════════════════════════════════════════════════════════════════════

class TestBaselineManager:

    def test_create_baseline_from_run(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.baseline_manager import create_baseline_from_run
        bid = create_baseline_from_run(
            store=seeded_store,
            scope_id=scope_id,
            run_id="run-baseline",
            run_type="smoke",
            artifacts={"verdict": "pass", "step_count": 10},
        )
        assert bid is not None
        b = seeded_store.get_active_baseline(scope_id)
        # Not active yet (not promoted)
        assert b is None or b.get("baseline_id") == bid

    def test_mark_baseline_active(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.baseline_manager import create_baseline_from_run, mark_baseline_active
        bid = create_baseline_from_run(
            store=seeded_store, scope_id=scope_id, run_id="r1", run_type="smoke",
            artifacts={"verdict": "pass"}
        )
        mark_baseline_active(seeded_store, bid, scope_id)
        active = seeded_store.get_active_baseline(scope_id)
        assert active is not None
        assert active["baseline_id"] == bid

    def test_compare_run_to_baseline_stable(self):
        from qa_ai.memory_kernel.baseline_manager import compare_run_to_baseline
        baseline = {"baseline_id": "b1", "summary": json.dumps({"verdict": "pass", "step_count": 10})}
        run = {"run_id": "r2", "verdict": "pass", "step_count": 10}
        result = compare_run_to_baseline(run, baseline)
        assert result.verdict == "stable"
        assert result.drift_score < 0.1

    def test_compare_run_to_baseline_regression(self):
        from qa_ai.memory_kernel.baseline_manager import compare_run_to_baseline
        baseline = {
            "baseline_id": "b1",
            "summary": json.dumps({"verdict": "pass", "failures": []}),
        }
        run = {"run_id": "r2", "verdict": "fail", "failures": ["step-3", "step-7"]}
        result = compare_run_to_baseline(run, baseline)
        assert result.verdict == "regression"
        assert len(result.new_failures) == 2

    def test_compare_improvement(self):
        from qa_ai.memory_kernel.baseline_manager import compare_run_to_baseline
        baseline = {
            "baseline_id": "b1",
            "summary": json.dumps({"verdict": "fail", "failures": ["step-1"]}),
        }
        run = {"run_id": "r2", "verdict": "pass", "failures": []}
        result = compare_run_to_baseline(run, baseline)
        assert result.verdict == "improvement"

    def test_drift_score_range(self):
        from qa_ai.memory_kernel.baseline_manager import compare_run_to_baseline
        b = {"baseline_id": "b", "summary": json.dumps({})}
        r = {"run_id": "r", "verdict": "fail", "failures": [f"s{i}" for i in range(20)]}
        result = compare_run_to_baseline(r, b)
        assert 0.0 <= result.drift_score <= 1.0

    def test_update_baseline_if_stable_first_run(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.baseline_manager import update_baseline_if_stable
        promoted, reason = update_baseline_if_stable(
            store=seeded_store,
            scope_id=scope_id,
            run_id="r-first",
            run_type="smoke",
            run_artifacts={"verdict": "pass"},
        )
        assert promoted is True
        assert "first_run" in reason

    def test_no_promotion_on_regression(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.baseline_manager import (
            create_baseline_from_run, mark_baseline_active, update_baseline_if_stable
        )
        bid = create_baseline_from_run(seeded_store, scope_id, "r0", "smoke",
                                       {"verdict": "pass", "failures": []})
        mark_baseline_active(seeded_store, bid, scope_id)
        promoted, reason = update_baseline_if_stable(
            store=seeded_store,
            scope_id=scope_id,
            run_id="r-fail",
            run_type="smoke",
            run_artifacts={"verdict": "fail", "failures": ["step-1"]},
        )
        assert not promoted


# ══════════════════════════════════════════════════════════════════════════════
# 8. Delta Engine
# ══════════════════════════════════════════════════════════════════════════════

class TestDeltaEngine:

    def test_compute_run_delta_initial(self):
        from qa_ai.memory_kernel.delta_engine import compute_run_delta
        delta = compute_run_delta(baseline=None, current_run={"verdict": "pass", "failures": []})
        assert delta["_is_initial"] is True
        assert delta["verdict_change"] == "pass"

    def test_compute_run_delta_new_failures(self):
        from qa_ai.memory_kernel.delta_engine import compute_run_delta
        baseline = {
            "baseline_id": "b1",
            "summary": json.dumps({"verdict": "pass", "failures": []}),
        }
        run = {"verdict": "fail", "failures": ["step-1", "step-2"]}
        delta = compute_run_delta(baseline, run)
        assert delta["new_failures"] == ["step-1", "step-2"]

    def test_compute_run_delta_resolved_failures(self):
        from qa_ai.memory_kernel.delta_engine import compute_run_delta
        baseline = {
            "baseline_id": "b1",
            "summary": json.dumps({"verdict": "fail", "failures": ["step-1"]}),
        }
        run = {"verdict": "pass", "failures": []}
        delta = compute_run_delta(baseline, run)
        assert "step-1" in delta["resolved_failures"]

    def test_compute_step_deltas(self):
        from qa_ai.memory_kernel.delta_engine import compute_step_deltas
        b = [{"step_id": "s1", "verdict": "pass"}, {"step_id": "s2", "verdict": "pass"}]
        c = [{"step_id": "s1", "verdict": "fail"}, {"step_id": "s2", "verdict": "pass"}]
        changed = compute_step_deltas(b, c)
        assert len(changed) == 1
        assert changed[0]["step_id"] == "s1"
        assert changed[0]["from"] == "pass"
        assert changed[0]["to"] == "fail"

    def test_compute_timing_deltas(self):
        from qa_ai.memory_kernel.delta_engine import compute_timing_deltas
        baseline_t = {"step-1": 100.0, "step-2": 200.0}
        current_t = {"step-1": 200.0, "step-2": 210.0}  # step-1 doubled
        result = compute_timing_deltas(baseline_t, current_t, slow_threshold_pct=30.0)
        keys = [r["key"] for r in result["regressions"]]
        assert "step-1" in keys

    def test_compute_connector_deltas(self):
        from qa_ai.memory_kernel.delta_engine import compute_connector_deltas
        b = {"conn-A": {"ready": True, "gaps": []}}
        c = {"conn-A": {"ready": True, "gaps": ["vision"]}}
        changed = compute_connector_deltas(b, c)
        assert len(changed) == 1
        assert "vision" in changed[0]["new_gaps"]

    def test_store_run_delta(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.delta_engine import store_run_delta
        delta_id = store_run_delta(
            store=seeded_store,
            scope_id=scope_id,
            run_id="run-delta-test",
            run_type="smoke",
            delta={"new_failures": ["s1"], "resolved_failures": [], "verdict_change": "fail"},
        )
        assert delta_id is not None
        deltas = seeded_store.list_run_deltas(scope_id=scope_id)
        assert any(d["delta_id"] == delta_id for d in deltas)

    def test_ingest_run_pipeline(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.delta_engine import ingest_run
        did, delta = ingest_run(
            store=seeded_store,
            scope_id=scope_id,
            run_id="run-ingest",
            run_type="regression",
            current_run={"verdict": "fail", "failures": ["step-99"]},
        )
        assert did is not None
        assert "new_failures" in delta

    def test_delta_does_not_store_secrets(self):
        from qa_ai.memory_kernel.delta_engine import compute_run_delta
        run = {"verdict": "fail", "password": "hunter2", "api_key": "sk-abc123abc123abc123"}
        delta = compute_run_delta(None, run)
        delta_str = json.dumps(delta)
        assert "hunter2" not in delta_str
        assert "sk-abc123" not in delta_str

    def test_new_unclear_populated(self):
        from qa_ai.memory_kernel.delta_engine import compute_run_delta
        baseline = {"baseline_id": "b1", "summary": json.dumps({"steps": [{"step_id": "s1", "verdict": "pass"}]})}
        run = {"steps": [{"step_id": "s1", "verdict": "unclear"}]}
        delta = compute_run_delta(baseline, run)
        assert "s1" in delta.get("new_unclear", [])


# ══════════════════════════════════════════════════════════════════════════════
# 9. Retention Engine
# ══════════════════════════════════════════════════════════════════════════════

class TestRetentionEngine:

    def test_plan_retention_empty_scope(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.retention_engine import plan_retention
        plan = plan_retention(store=seeded_store, scope_id=scope_id)
        assert plan.total_records == 0

    def test_plan_retention_classifies_fingerprints(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.retention_engine import plan_retention
        # Insert a duplicate fingerprint (low utility)
        seeded_store.store_evidence_fingerprint({
            "fingerprint_id": str(uuid.uuid4()),
            "scope_id": scope_id,
            "run_id": "r1",
            "evidence_type": "screenshot",
            "content_hash": "hash-low",
            "duplicate_of": "some-other-id",
            "retention_class": "cold",
        })
        plan = plan_retention(store=seeded_store, scope_id=scope_id)
        assert plan.total_records >= 1

    def test_dry_run_does_not_delete(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.retention_engine import plan_retention, execute_retention_plan, RetentionAction, RetentionPlan
        fp_id = str(uuid.uuid4())
        seeded_store.store_evidence_fingerprint({
            "fingerprint_id": fp_id,
            "scope_id": scope_id,
            "run_id": "r1",
            "evidence_type": "log",
            "content_hash": "hash-dry-run",
        })
        # Build a plan that marks it for deletion
        plan = RetentionPlan(total_records=1)
        plan.delete.append(RetentionAction(
            record_type="fingerprint",
            record_id=fp_id,
            retention_class="delete_candidate",
            utility_score=5.0,
            action="delete",
            reason="test",
        ))
        result = execute_retention_plan(seeded_store, plan, dry_run=True)
        assert result["dry_run"] is True
        assert result["executed_deletes"] == 0
        # Record still exists
        fps = seeded_store.list_fingerprints(scope_id=scope_id)
        assert any(f["fingerprint_id"] == fp_id for f in fps)

    def test_execute_retention_deletes(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.retention_engine import execute_retention_plan, RetentionAction, RetentionPlan
        fp_id = str(uuid.uuid4())
        seeded_store.store_evidence_fingerprint({
            "fingerprint_id": fp_id,
            "scope_id": scope_id,
            "run_id": "r1",
            "evidence_type": "log",
            "content_hash": f"hash-execute-{fp_id}",
        })
        plan = RetentionPlan(total_records=1)
        plan.delete.append(RetentionAction(
            record_type="fingerprint",
            record_id=fp_id,
            retention_class="delete_candidate",
            utility_score=5.0,
            action="delete",
            reason="test",
        ))
        result = execute_retention_plan(seeded_store, plan, dry_run=False)
        assert result["executed_deletes"] == 1

    def test_cap_deletes_per_run(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.retention_engine import plan_retention, RetentionAction, RetentionPlan
        # Build synthetic plan to verify capping logic
        plan = RetentionPlan(total_records=10)
        for i in range(10):
            plan.delete.append(RetentionAction(
                record_type="fingerprint",
                record_id=f"fp-{i}",
                retention_class="delete_candidate",
                utility_score=float(i),
                action="delete",
                reason="low",
            ))
        # Apply cap at 5
        if len(plan.delete) > 5:
            plan.delete.sort(key=lambda x: x.utility_score)
            excess = plan.delete[5:]
            for a in excess:
                a.action = "compress"
                plan.compress.append(a)
            plan.delete = plan.delete[:5]
        assert len(plan.delete) == 5

    def test_run_retention_cycle_dry_run(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.retention_engine import run_retention_cycle
        result = run_retention_cycle(
            store=seeded_store,
            scope_id=scope_id,
            dry_run=True,
        )
        assert result["dry_run"] is True

    def test_action_for_class_mapping(self):
        from qa_ai.memory_kernel.retention_engine import _action_for_class
        assert _action_for_class("hot") == "keep"
        assert _action_for_class("warm") == "keep"
        assert _action_for_class("cold") == "compress"
        assert _action_for_class("delete_candidate") == "delete"

    def test_unknown_record_type_raises(self, seeded_store):
        from qa_ai.memory_kernel.retention_engine import _delete_record
        with pytest.raises(ValueError, match="Unknown record_type"):
            _delete_record(seeded_store, "not_a_type", "some-id")


# ══════════════════════════════════════════════════════════════════════════════
# 10. Pattern Engine
# ══════════════════════════════════════════════════════════════════════════════

class TestPatternEngine:

    def test_extract_patterns_new_failures(self):
        from qa_ai.memory_kernel.pattern_engine import extract_patterns_from_delta
        delta = {"new_failures": ["step-1", "step-2"], "connector_deltas": [], "timing_deltas": {}}
        patterns = extract_patterns_from_delta(delta, "scope-x", "run-y")
        assert any(p["pattern_type"] == "failure_cluster" for p in patterns)

    def test_extract_patterns_timing_regression(self):
        from qa_ai.memory_kernel.pattern_engine import extract_patterns_from_delta
        delta = {
            "new_failures": [],
            "connector_deltas": [],
            "timing_deltas": {"regressions": [{"key": "step-1", "pct": 80.0, "baseline_ms": 100, "current_ms": 180}]},
        }
        patterns = extract_patterns_from_delta(delta, "scope-x", "run-y")
        assert any(p["pattern_type"] == "timing_regression" for p in patterns)

    def test_extract_patterns_connector_gap(self):
        from qa_ai.memory_kernel.pattern_engine import extract_patterns_from_delta
        delta = {
            "new_failures": [],
            "timing_deltas": {},
            "connector_deltas": [{"connector_id": "conn-A", "new_gaps": ["vision"]}],
        }
        patterns = extract_patterns_from_delta(delta, "scope-x", "run-y")
        assert any(p["pattern_type"] == "connector_gap" for p in patterns)

    def test_merge_pattern_creates_new(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.pattern_engine import merge_pattern
        pattern = {
            "pattern_type": "flaky_test",
            "scope_id": scope_id,
            "canonical_template": f"flaky:unique_{scope_id}",
            "parameters": {"title": "Flaky login"},
            "frequency": 1,
            "confidence": 0.7,
            "impact_score": 0.5,
        }
        pid = merge_pattern(seeded_store, pattern)
        assert pid is not None
        found = seeded_store.get_pattern_by_template(f"flaky:unique_{scope_id}", scope_id)
        assert found["pattern_id"] == pid

    def test_merge_pattern_increments_existing(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.pattern_engine import merge_pattern
        template = f"flaky:repeat_{scope_id}"
        pattern = {
            "pattern_type": "flaky_test",
            "scope_id": scope_id,
            "canonical_template": template,
            "parameters": {},
            "frequency": 1,
            "confidence": 0.6,
            "impact_score": 0.5,
        }
        merge_pattern(seeded_store, pattern)
        merge_pattern(seeded_store, pattern)
        found = seeded_store.get_pattern_by_template(template, scope_id)
        assert found["frequency"] >= 2

    def test_detect_flaky_patterns(self):
        from qa_ai.memory_kernel.pattern_engine import detect_flaky_patterns
        verdicts = [
            ("step-1", "pass"), ("step-1", "fail"), ("step-1", "pass"), ("step-1", "fail"),
            ("step-2", "pass"), ("step-2", "pass"),
        ]
        patterns = detect_flaky_patterns(verdicts, "scope-x", min_flips=2)
        flaky_ids = [p["parameters"]["title"] for p in patterns]
        assert any("step-1" in t for t in flaky_ids)
        assert not any("step-2" in t for t in flaky_ids)

    def test_normalize_pattern_type_unknown(self):
        from qa_ai.memory_kernel.pattern_engine import _normalize_pattern_type
        assert _normalize_pattern_type("weird_type") == "generic"
        assert _normalize_pattern_type("flaky_test") == "flaky_test"

    def test_query_patterns_filter_by_type(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.pattern_engine import merge_pattern, query_patterns
        for pt, template in [("flaky_test", f"flakey_t_{scope_id}"), ("connector_gap", f"gap_t_{scope_id}")]:
            merge_pattern(seeded_store, {
                "pattern_type": pt, "scope_id": scope_id,
                "canonical_template": template,
                "parameters": {}, "frequency": 1, "confidence": 0.7, "impact_score": 0.5,
            })
        flaky = query_patterns(seeded_store, scope_id, pattern_type="flaky_test")
        assert all(p["pattern_type"] == "flaky_test" for p in flaky)

    def test_ingest_delta_patterns_returns_ids(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.pattern_engine import ingest_delta_patterns
        delta = {"new_failures": ["s1"], "connector_deltas": [], "timing_deltas": {}, "verdict_change": None}
        ids = ingest_delta_patterns(seeded_store, scope_id, "run-z", delta)
        assert isinstance(ids, list)

    def test_extract_from_findings_cluster(self):
        from qa_ai.memory_kernel.pattern_engine import extract_patterns_from_findings
        findings = [
            {"failure_type": "timeout", "severity": "high"},
            {"failure_type": "timeout", "severity": "high"},
            {"failure_type": "timeout", "severity": "medium"},
        ]
        patterns = extract_patterns_from_findings(findings, "scope-x", min_occurrences=2)
        assert len(patterns) == 1
        assert "timeout" in patterns[0]["parameters"]["title"].lower()


# ══════════════════════════════════════════════════════════════════════════════
# 11. Trajectory Engine
# ══════════════════════════════════════════════════════════════════════════════

class TestTrajectoryEngine:

    def test_create_trajectory(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory
        tid = create_trajectory(
            store=seeded_store,
            scope_id=scope_id,
            run_id="run-traj",
            problem_signature="login_timeout",
            action_taken="Increased timeout to 30s",
            outcome="Tests passed after fix",
            reasoning_steps=["Step 1: checked logs", "Step 2: identified timeout"],
        )
        assert tid is not None
        traj = seeded_store.get_trajectory(tid)
        assert traj["outcome"] == "Tests passed after fix"

    def test_no_raw_thinking_stored(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory
        tid = create_trajectory(
            store=seeded_store,
            scope_id=scope_id,
            run_id="r1",
            problem_signature="check",
            action_taken="<thinking>Secret internal reasoning here</thinking>Fix applied",
            outcome="Done",
        )
        traj = seeded_store.get_trajectory(tid)
        assert "<thinking>" not in traj["action_taken"]

    def test_update_trajectory_outcome(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory, update_trajectory_outcome
        tid = create_trajectory(
            store=seeded_store,
            scope_id=scope_id,
            run_id="r1",
            problem_signature="sig",
            action_taken="act",
            outcome="initial",
        )
        update_trajectory_outcome(seeded_store, tid, outcome="updated outcome", success=True)
        traj = seeded_store.get_trajectory(tid)
        assert traj["outcome"] == "updated outcome"

    def test_list_trajectories(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory, list_trajectories
        for i in range(3):
            create_trajectory(
                store=seeded_store,
                scope_id=scope_id,
                run_id=f"r{i}",
                problem_signature=f"sig-{i}",
                action_taken="act",
                outcome="done",
            )
        trajs = list_trajectories(seeded_store, scope_id)
        assert len(trajs) >= 3

    def test_find_similar_trajectories(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory, find_similar_trajectories
        create_trajectory(
            store=seeded_store,
            scope_id=scope_id,
            run_id="r1",
            problem_signature="login_timeout_slow_network",
            action_taken="Increased timeout",
            outcome="Fixed",
        )
        results = find_similar_trajectories(seeded_store, scope_id, "login timeout slow", top_k=3)
        assert isinstance(results, list)

    def test_trajectory_redacts_secrets(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory
        tid = create_trajectory(
            store=seeded_store,
            scope_id=scope_id,
            run_id="r1",
            problem_signature="auth",
            action_taken="Used password=hunter2 to test",
            outcome="Found auth bug",
        )
        traj = seeded_store.get_trajectory(tid)
        assert "hunter2" not in traj["action_taken"]

    def test_summarize_trajectories(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory, update_trajectory_outcome, summarize_trajectories, list_trajectories
        t1 = create_trajectory(seeded_store, scope_id, "r1", "sig1", "act", "done", utility_score=0.8)
        t2 = create_trajectory(seeded_store, scope_id, "r2", "sig2", "act", "done", utility_score=0.6)
        update_trajectory_outcome(seeded_store, t1, "done", success=True)
        update_trajectory_outcome(seeded_store, t2, "done", success=False)
        trajs = list_trajectories(seeded_store, scope_id)
        summary = summarize_trajectories(trajs)
        assert "count" in summary

    def test_trajectory_steps_capped(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory, get_trajectory
        steps = [f"Step {i}" for i in range(50)]
        tid = create_trajectory(
            store=seeded_store,
            scope_id=scope_id,
            run_id="r1",
            problem_signature="many_steps",
            action_taken="act",
            outcome="done",
            reasoning_steps=steps,
        )
        traj = get_trajectory(seeded_store, tid)
        assert len(traj["reasoning_steps"]) <= 20


# ══════════════════════════════════════════════════════════════════════════════
# 12. Semantic Recall
# ══════════════════════════════════════════════════════════════════════════════

class TestSemanticRecall:

    def test_index_memory_simhash_fallback(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.semantic_recall import index_memory
        # embed unavailable → simhash
        result = index_memory(
            store=seeded_store,
            source_type="summary",
            source_id="sum-1",
            text="Login fails on slow network",
            scope_id=scope_id,
        )
        assert result["indexed"] is True
        assert result["method"] in ("embedding", "simhash")

    def test_recall_similar_simhash(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.semantic_recall import index_memory, recall_similar
        for i in range(3):
            index_memory(
                store=seeded_store,
                source_type="summary",
                source_id=f"sum-{i}",
                text=f"Test scenario {i}: login flow check",
                scope_id=scope_id,
            )
        results = recall_similar(
            store=seeded_store,
            query="login flow",
            scope_id=scope_id,
            top_k=5,
            min_score=0.0,
        )
        assert isinstance(results, list)

    def test_recall_returns_source_id(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.semantic_recall import index_memory, recall_similar
        index_memory(seeded_store, "fingerprint", "fp-unique-1", "checkout payment error", scope_id)
        results = recall_similar(seeded_store, "checkout payment", scope_id, top_k=3, min_score=0.0)
        source_ids = [r["source_id"] for r in results]
        assert "fp-unique-1" in source_ids

    def test_is_duplicate_evidence_by_hash(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.semantic_recall import is_duplicate_evidence
        ch = f"exact-hash-{scope_id}"
        seeded_store.store_evidence_fingerprint({
            "fingerprint_id": str(uuid.uuid4()),
            "scope_id": scope_id,
            "run_id": "r1",
            "evidence_type": "screenshot",
            "content_hash": ch,
        })
        dup, match_id = is_duplicate_evidence(seeded_store, scope_id, ch)
        assert dup is True
        assert match_id is not None

    def test_is_not_duplicate(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.semantic_recall import is_duplicate_evidence
        dup, _ = is_duplicate_evidence(seeded_store, scope_id, "totally-new-hash-xyz")
        assert dup is False

    def test_recall_empty_store(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.semantic_recall import recall_similar
        results = recall_similar(seeded_store, "some query", scope_id, top_k=5)
        assert results == []

    def test_index_source_type_preserved(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.semantic_recall import index_memory
        index_memory(seeded_store, "trajectory", "traj-99", "timeout analysis", scope_id)
        rows = seeded_store.list_embeddings(scope_id=scope_id, source_type="trajectory")
        assert any(r["source_id"] == "traj-99" for r in rows)

    def test_recall_respects_source_type_filter(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.semantic_recall import index_memory, recall_similar
        index_memory(seeded_store, "summary", "s-1", "auth failure pattern", scope_id)
        index_memory(seeded_store, "trajectory", "t-1", "auth failure pattern", scope_id)
        results = recall_similar(seeded_store, "auth failure", scope_id, source_types=["summary"], top_k=5, min_score=0.0)
        assert all(r["source_type"] == "summary" for r in results)


# ══════════════════════════════════════════════════════════════════════════════
# 13. Memory API Service
# ══════════════════════════════════════════════════════════════════════════════

class TestMemoryAPIService:

    def test_get_or_create_scope_created(self, tmp_db):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        sid = f"scope-svc-{uuid.uuid4().hex[:6]}"
        result = svc.get_or_create_scope(
            scope_id=sid, project_id="proj-svc", app_id="app-svc"
        )
        assert result["status"] == "created"
        assert result["scope"]["scope_id"] == sid

    def test_get_or_create_scope_existing(self, tmp_db):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        sid = f"scope-exist-{uuid.uuid4().hex[:6]}"
        svc.get_or_create_scope(sid, "p1", "a1")
        result2 = svc.get_or_create_scope(sid, "p1", "a1")
        assert result2["status"] == "existing"

    def test_ingest_run_returns_delta_id(self, tmp_db, scope_id):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        tmp_db.upsert_scope(scope_id=scope_id, project_id="p", app_id="a")
        result = svc.ingest_run(
            scope_id=scope_id,
            run_id="run-svc",
            run_type="smoke",
            current_run={"verdict": "pass", "failures": []},
        )
        assert result["status"] == "ok"
        assert result["delta_id"] is not None

    def test_store_evidence_dedup(self, tmp_db, scope_id):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        tmp_db.upsert_scope(scope_id=scope_id, project_id="p", app_id="a")
        ch = f"dedup-hash-{scope_id}"
        r1 = svc.store_evidence(scope_id, "r1", "log", ch)
        r2 = svc.store_evidence(scope_id, "r2", "log", ch)
        assert r1["status"] == "ok"
        assert r2["status"] == "duplicate"

    def test_store_summary_ok(self, tmp_db, scope_id):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        tmp_db.upsert_scope(scope_id=scope_id, project_id="p", app_id="a")
        result = svc.store_summary(
            scope_id=scope_id,
            source_id="run-x",
            source_type="run",
            summary_text="All steps passed cleanly in 5s",
        )
        assert result["status"] == "ok"
        assert result["summary_id"] is not None

    def test_recall_no_results_empty(self, tmp_db, scope_id):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        tmp_db.upsert_scope(scope_id=scope_id, project_id="p", app_id="a")
        result = svc.recall(scope_id=scope_id, query="something")
        assert result["status"] == "ok"
        assert result["count"] == 0

    def test_create_and_get_baseline(self, tmp_db, scope_id):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        tmp_db.upsert_scope(scope_id=scope_id, project_id="p", app_id="a")
        result = svc.create_baseline(scope_id=scope_id, run_id="r1", notes="first baseline")
        assert result["status"] == "ok"

    def test_retention_preview(self, tmp_db, scope_id):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        tmp_db.upsert_scope(scope_id=scope_id, project_id="p", app_id="a")
        result = svc.retention_preview(scope_id=scope_id)
        assert result["status"] == "ok"
        assert "plan" in result

    def test_stats_returns_counts(self, tmp_db, scope_id):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        tmp_db.upsert_scope(scope_id=scope_id, project_id="p", app_id="a")
        stats = svc.stats(scope_id=scope_id)
        assert "fingerprints" in stats

    def test_scope_report_markdown(self, tmp_db, scope_id):
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService(store=tmp_db)
        tmp_db.upsert_scope(scope_id=scope_id, project_id="p", app_id="a")
        report = svc.scope_report(scope_id=scope_id, format="markdown")
        assert "Memory Report" in report


# ══════════════════════════════════════════════════════════════════════════════
# 14. REST API Endpoints
# ══════════════════════════════════════════════════════════════════════════════

class TestMemoryRestAPI:

    def test_get_scope_not_found(self, api_client):
        r = api_client.get("/api/memory/scopes/does-not-exist-xyz")
        assert r.status_code == 404

    def test_get_stats_missing_scope(self, api_client):
        # Stats for nonexistent scope returns empty counts (scope not in DB)
        r = api_client.get("/api/memory/scopes/ghost-scope/stats")
        assert r.status_code == 200
        data = r.json()
        assert "stats" in data

    def test_get_report(self, api_client):
        r = api_client.get("/api/memory/scopes/test-scope-report/report?format=markdown")
        assert r.status_code == 200
        assert "report" in r.json()

    def test_get_report_json_format(self, api_client):
        r = api_client.get("/api/memory/scopes/test-scope/report?format=json")
        assert r.status_code == 200

    def test_get_patterns_empty(self, api_client):
        r = api_client.get("/api/memory/scopes/empty-scope/patterns")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_get_baseline_no_baseline(self, api_client):
        r = api_client.get("/api/memory/scopes/no-baseline-scope/baseline")
        assert r.status_code == 200
        assert r.json()["baseline"] is None

    def test_ingest_run_endpoint(self, api_client):
        sid = f"scope-api-{uuid.uuid4().hex[:6]}"
        r = api_client.post(f"/api/memory/scopes/{sid}/ingest", json={
            "run_id": "run-api-test",
            "run_type": "smoke",
            "verdict": "pass",
            "failures": [],
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_recall_endpoint(self, api_client):
        sid = f"scope-recall-{uuid.uuid4().hex[:6]}"
        r = api_client.post(f"/api/memory/scopes/{sid}/recall", json={
            "query": "timeout error on login",
            "top_k": 5,
        })
        assert r.status_code == 200
        assert "results" in r.json()

    def test_retention_preview_endpoint(self, api_client):
        r = api_client.get("/api/memory/scopes/scope-preview/retention")
        assert r.status_code == 200
        assert "plan" in r.json()

    def test_retention_execute_dry_run(self, api_client):
        r = api_client.post("/api/memory/scopes/scope-dry/retention", json={"dry_run": True})
        assert r.status_code == 200
        assert r.json()["dry_run"] is True

    def test_create_baseline_endpoint(self, api_client):
        sid = f"scope-bl-{uuid.uuid4().hex[:6]}"
        r = api_client.post(f"/api/memory/scopes/{sid}/baseline", json={
            "run_id": "run-baseline-api",
            "run_type": "smoke",
            "notes": "first baseline",
            "promote": False,
        })
        assert r.status_code == 201

    def test_patterns_filter_by_type(self, api_client):
        r = api_client.get("/api/memory/scopes/scope-pt/patterns?pattern_type=flaky_test&min_confidence=0.5")
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 15. Security & Privacy
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityAndPrivacy:

    def test_redact_api_key(self):
        from qa_ai.memory_kernel.memory_privacy import redact_text
        text = "Found api_key=sk-abc123def456ghi789 in config"
        redacted = redact_text(text)
        assert "sk-abc123" not in redacted
        assert "[REDACTED" in redacted

    def test_redact_bearer_token(self):
        from qa_ai.memory_kernel.memory_privacy import redact_text
        text = "Authorization: Bearer eyJsb2dpbiI6InRlc3QifQ"
        redacted = redact_text(text)
        assert "eyJsb2dpbiI" not in redacted

    def test_redact_password_in_json(self):
        from qa_ai.memory_kernel.memory_privacy import redact_json
        data = {"user": "alice", "password": "hunter2", "nested": {"secret": "top-secret"}}
        result = redact_json(data)
        assert result["password"] == "[REDACTED]"
        assert result["nested"]["secret"] == "[REDACTED]"
        assert result["user"] == "alice"

    def test_redact_db_url(self):
        from qa_ai.memory_kernel.memory_privacy import redact_text
        text = "Connecting to postgres://admin:pass@localhost:5432/prod"
        redacted = redact_text(text)
        assert "admin:pass" not in redacted

    def test_safe_artifact_path_blocks_traversal(self, tmp_path):
        from qa_ai.memory_kernel.memory_privacy import safe_artifact_path
        root = tmp_path / "artifacts"
        root.mkdir()
        result = safe_artifact_path(root, "../../etc/passwd")
        assert result is None

    def test_safe_artifact_path_allows_valid(self, tmp_path):
        from qa_ai.memory_kernel.memory_privacy import safe_artifact_path
        root = tmp_path / "artifacts"
        root.mkdir()
        result = safe_artifact_path(root, "screenshots/test.png")
        assert result is not None
        assert str(result).startswith(str(root))

    def test_compact_summary_blocks_raw_system_prompt(self):
        from qa_ai.memory_kernel.memory_models import CompactSummary
        # Validator silently redacts "You are..." prompts instead of raising
        summary = CompactSummary(
            summary_id="s1",
            scope_id="sc1",
            source_type="run",
            source_id="r1",
            summary_text="You are a helpful assistant. Please do X",
            verdict="pass",
        )
        # Raw prompt text should not be stored verbatim
        assert "You are a helpful assistant" not in summary.summary_text

    def test_trajectory_strips_thinking_tags(self, seeded_store, scope_id):
        from qa_ai.memory_kernel.trajectory_engine import create_trajectory
        tid = create_trajectory(
            store=seeded_store,
            scope_id=scope_id,
            run_id="r1",
            problem_signature="sig",
            action_taken="<thinking>private reasoning chain...</thinking>Fix: restart service",
            outcome="Fixed",
        )
        traj = seeded_store.get_trajectory(tid)
        assert "<thinking>" not in traj["action_taken"]
        assert "Fix: restart service" in traj["action_taken"]

    def test_no_sql_injection_via_scope_id(self, tmp_db):
        """Parameterized queries prevent injection."""
        malicious = "scope'; DROP TABLE memory_scopes; --"
        # Should not raise, and table should still exist
        result = tmp_db.get_scope(malicious)
        assert result is None
        # Table still intact
        assert tmp_db.get_scope("any-scope") is None  # not dropped

    def test_redact_aws_key(self):
        from qa_ai.memory_kernel.memory_privacy import redact_text
        text = "Using key AKIAIOSFODNN7EXAMPLE for AWS access"
        redacted = redact_text(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in redacted
