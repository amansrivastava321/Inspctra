"""Phase 18B disposable comparison fixtures. Reuses guarded 18A temp storage.

Synthetic persisted observations, not newly executed tests. Commands:
seed DIR, snapshot DIR, verify DIR API_URL. Never opens user storage for writes.
"""
import json
import sqlite3
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from run_history import fixture_dir, seed as seed_history, snapshot as history_snapshot


def snapshot(path):
    result = history_snapshot(path)
    result["inventory"] = sorted(str(p.relative_to(path)) for p in path.rglob("*") if p.is_file())
    return result


def seed(path):
    manifest = seed_history(path)  # Refuses nonempty/non-temporary directories.
    from qa_ai.product_backend.storage import ProductStorage
    storage = ProductStorage(str(path / "inspectra_product.db"))

    def step(sid, status="passed", **kw):
        return dict(step_id=sid, status=status, action_type="assert_status",
                    provenance="REAL_EXECUTION", duration_ms=10, **kw)

    baseline = [step("pf", status_code=200), step("fp", "failed"), step("pp"),
                step("same", "failed", error="Timeout"), step("different", "failed", error="Timeout"),
                step("baseline-only"), step(None), step("duplicate"), step("duplicate")]
    current = [step("different", "failed", error="Network"), step("same", "failed", error=" timeout "),
               step("pp"), step("fp"), {**step("pf", "failed", status_code=500), "duration_ms": 30},
               step("comparison-only"), step(None), step("duplicate")]

    def put(rid, steps=None, **kw):
        values = dict(id=rid, pack_id="h18-pack", app_target_id="h18-app", status="failed",
                      provenance="REAL_EXECUTION", execution_mode="automated",
                      created_at="2026-09-01T00:00:00Z", started_at="2026-09-01T00:00:00Z",
                      completed_at="2026-09-02T00:00:00Z", step_results=json.dumps(steps or baseline))
        values.update(kw)
        storage._execute(f"INSERT INTO live_runs ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
        manifest[rid] = {k: v for k, v in values.items() if k != "step_results"}

    put("c18-base")
    put("c18-current", current, completed_at="2026-09-03T00:00:00Z")
    put("c18-newer", completed_at="2026-09-04T00:00:00Z")
    put("c18-unknown", created_at="unknown", started_at=None, completed_at=None)
    put("c18-manual", execution_mode="manual")
    put("c18-inferred", provenance="")
    put("c18-partial")
    for provenance in ("DRY_RUN", "UNAVAILABLE", "MIXED"):
        put(f"c18-{provenance.lower()}", [{**step("pf"), "provenance": provenance}], provenance=provenance)

    for eid, rid, sid in [("c18-owned", "c18-base", "pf"), ("c18-foreign", "h18-other-pack", "pf"),
                          ("c18-inferred-evidence", "c18-inferred", "pf")]:
        storage.create_evidence(dict(id=eid, run_id=rid, step_id=sid, type="console", name=eid,
                                    relative_path="h18-owned.txt", mime_type="text/plain", size_bytes=55,
                                    provenance="REAL_EXECUTION", created_at="2026-09-01T00:00:00Z"))
    for i in range(501):
        storage.create_evidence(dict(id=f"c18-partial-{i:03}", run_id="c18-partial", step_id="pf", type="console",
                                    name="bounded metadata", relative_path="h18-owned.txt", mime_type="text/plain",
                                    size_bytes=55, provenance="REAL_EXECUTION", created_at="2026-09-01T00:00:00Z"))
    baseline[0]["evidence_ids"] = ["c18-owned", "c18-foreign", "absent-evidence"]
    storage._execute("UPDATE live_runs SET step_results=? WHERE id=?", (json.dumps(baseline), "c18-base"))
    storage.close()
    (path / "comparison-fixture.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def verify(path, api):
    before = snapshot(path)

    def get(b="c18-base", c="c18-current", expected=200):
        url = f"{api}/api/runs/{c}/compare?{urlencode({'baseline_run_id': b})}"
        try:
            with urlopen(url, timeout=10) as response:
                assert response.status == expected
                return json.load(response)
        except HTTPError as error:
            assert error.code == expected, (url, error.code, expected)
            return json.load(error)

    data = get()
    assert get() == data
    assert data["scope"] == {"pack_id": "h18-pack", "app_target_id": "h18-app"}
    assert data["selection_mode"] == "explicit"
    assert (data["baseline_run_id"], data["comparison_run_id"]) == ("c18-base", "c18-current")
    assert data["chronology"]["state"] == "forward"
    assert "Execution configuration continuity between these runs cannot be fully verified." in data["comparability_warnings"]
    assert data["summary_counts"] == dict(matched=5, passed_to_failed=1, failed_to_passed=1,
        passed_to_passed=1, failed_to_failed=2, inconclusive_transitions=0, baseline_only=1,
        comparison_only=1, identity_unavailable=2, identity_conflict=1, not_comparable=5)
    rows = {r["step_id"]: r for r in data["step_comparisons"] if r["step_id"]}
    for sid, transition in [("pf", "passed_to_failed"), ("fp", "failed_to_passed"), ("pp", "passed_to_passed"), ("same", "failed_to_failed")]:
        assert rows[sid]["transition"] == transition
    for sid, identity in [("baseline-only", "baseline_only"), ("comparison-only", "comparison_only"), ("duplicate", "identity_conflict")]:
        assert rows[sid]["identity_state"] == identity
    metrics = {m["key"]: m for m in rows["pf"]["metric_comparisons"]}
    assert metrics["duration_ms"]["delta"] == 20
    assert (metrics["status_code"]["baseline_value"], metrics["status_code"]["comparison_value"], metrics["status_code"]["delta"]) == (200, 500, None)
    assert metrics["response_time_ms"]["delta"] is None
    assert metrics["response_time_ms"]["reason"] == "request_identity_unavailable"
    assert rows["same"]["failure_signature_comparison"]["state"] == "same_signature"
    assert rows["different"]["failure_signature_comparison"]["state"] == "different_signature"
    assert rows["pf"]["baseline_citation"]["evidence_ids"] == ["c18-owned"]
    assert get("c18-newer")["chronology"]["state"] == "reverse"
    assert get("c18-unknown")["chronology"]["state"] == "unavailable"
    assert get("c18-manual")["provenance_compatibility"] == "informational"
    assert get("c18-inferred")["baseline"]["provenance_basis"] == "inferred"
    for name in ("dry_run", "unavailable", "mixed"):
        nonreal = get(f"c18-{name}")
        assert nonreal["summary_counts"]["passed_to_failed"] == 0
    partial = get("c18-partial")
    assert not partial["coverage"]["complete"]
    assert next(r for r in partial["step_comparisons"] if r["step_id"] == "pf")["evidence_comparison"]["baseline_count"] is None
    statuses = []
    for b, c, status in [("absent", "c18-current", 404), ("c18-base", "absent", 404),
                         ("", "c18-current", 422), ("c18-current", "c18-current", 422),
                         ("h18-active", "c18-current", 409), ("h18-other-pack", "c18-current", 409),
                         ("h18-other-target", "c18-current", 409)]:
        get(b, c, status)
        statuses.append({"baseline": b, "current": c, "status": status})
    with sqlite3.connect(f"{(path / 'inspectra_product.db').as_uri()}?mode=ro", uri=True) as db:
        for row in data["step_comparisons"] + partial["step_comparisons"]:
            for key in ("baseline_citation", "comparison_citation"):
                citation = row[key]
                if citation:
                    for eid in citation["evidence_ids"]:
                        assert db.execute("SELECT run_id,step_id FROM evidence_files WHERE id=?", (eid,)).fetchone() == (citation["run_id"], citation["step_id"])
    assert snapshot(path) == before, "Comparison mutated fixture state"
    return {"comparison": data, "errors": statuses, "unchanged_table_counts": {t: len(r) for t, r in before["tables"].items()}, "files_unchanged": True}


if __name__ == "__main__":
    command, raw, *args = sys.argv[1:]
    directory = fixture_dir(raw)
    result = seed(directory) if command == "seed" else snapshot(directory) if command == "snapshot" else verify(directory, args[0])
    print(json.dumps(result, sort_keys=True))
