"""Disposable Phase 18A fixtures and read-only verification; never use user storage.

Run from the repository with venv/bin/python. Commands: seed DIR,
snapshot DIR, verify DIR API_URL. DIR must be a new inspectra-history-18a-*
directory inside the OS temporary directory. Start the product factory with
INSPECTRA_ARTIFACTS_DIR=DIR before verify or the corresponding browser test.
These are synthetic persisted records, not claims of newly executed tests.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def fixture_dir(raw: str) -> Path:
    path = Path(raw).resolve()
    temp_roots = [Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()]
    if not any(path.is_relative_to(root) for root in temp_roots) or not path.name.startswith("inspectra-history-18a-"):
        raise ValueError("Use a disposable inspectra-history-18a-* directory under the OS temp directory")
    return path


def seed(path: Path) -> dict:
    from qa_ai.product_backend.models import (
        AppTarget, EvidenceFile, LiveRunRecord, Project, TestCase,
        TestCaseStep, ValidationPack,
    )
    from qa_ai.product_backend.storage import ProductStorage

    if any(path.iterdir()):
        raise ValueError("Fixture directory must be empty; existing data will not be overwritten")
    storage = ProductStorage(str(path / "inspectra_product.db"))
    storage.create_project(Project(id="h18-project", name="Phase 18A disposable verification").model_dump(mode="json"))
    for app_id in ["h18-app", "h18-other-app"]:
        storage.create_app_target(AppTarget(id=app_id, project_id="h18-project", name=app_id, app_type="api", base_url="http://127.0.0.1:8765").model_dump(mode="json"))
    for pack_id in ["h18-pack", "h18-other-pack", "h18-empty-pack", "h18-thin-pack", "h18-nonreal-pack"]:
        storage.create_validation_pack(ValidationPack(id=pack_id, project_id="h18-project", app_id="h18-app", name=pack_id).model_dump(mode="json"))
    storage.create_test_case(TestCase(test_case_id="h18-case", plan_id="h18-plan", pack_id="h18-pack", app_id="h18-app", title="History API assertion", automation_status="ready").model_dump(mode="json"))
    for order, step_id in enumerate(["h18-check", "h18-other-step"]):
        storage.create_test_step(TestCaseStep(step_id=step_id, case_id="h18-case", step_order=order, action_type="assert_status", expected_status=200, target="#unchanged-selector").model_dump(mode="json"))

    def step(step_id="h18-check", status="passed", provenance="REAL_EXECUTION", reason=None, evidence=()):
        result = dict(status=status, provenance=provenance, evidence_ids=list(evidence), action_type="assert_status", description="Identical label", selector="#identical", duration_ms=10)
        if step_id is not None:
            result["step_id"] = step_id
        if reason:
            result["failure_reason"] = reason
        return result

    manifest = {}

    def run(name, day, *, steps=None, status="completed", provenance="REAL_EXECUTION", mode="automated", pack="h18-pack", app="h18-app"):
        run_id = f"h18-{name}"
        at = f"2026-08-{day:02}T10:00:00+00:00"
        record = LiveRunRecord(id=run_id, pack_id=pack, app_target_id=app, status=status, provenance=provenance, execution_mode=mode, created_at=at)
        storage.create_run(record.model_dump(mode="json"))
        storage._execute("UPDATE live_runs SET started_at=?, completed_at=?, step_results=?, error=? WHERE id=?", (at, at if status in {"completed", "failed", "cancelled"} else None, json.dumps(steps or [step()]), "Fixture assertion failed" if status == "failed" else None, run_id))
        manifest[name] = dict(id=run_id, type=provenance, mode=mode, status=status, pack=pack, app=app)

    run("pass", 15, steps=[step(), step("h18-other-step")])
    run("fail-1", 2, status="failed", steps=[step("h18-other-step"), step(status="failed", reason="  TIMEOUT   waiting ", evidence=["h18-owned", "h18-wrong-step", "h18-wrong-run", "h18-missing-evidence"])])
    run("fail-2", 16, status="failed", steps=[step(status="failed", reason="timeout waiting")])
    run("similar", 4, status="failed", steps=[step(status="failed", reason="timeout loading")])
    run("different-step", 5, steps=[step("h18-new-check")])
    run("missing-step", 6, steps=[step(None)])
    for day, (name, provenance) in enumerate([("dry", "DRY_RUN"), ("simulated", "SIMULATED"), ("demo", "DEMO_EXAMPLE"), ("unavailable", "UNAVAILABLE")], 7):
        run(name, day, provenance=provenance, steps=[step(provenance=provenance)])
    run("mixed", 11, provenance="MIXED", steps=[step("h18-mixed-real"), step("h18-mixed-dry", provenance="DRY_RUN")])
    run("manual", 12, mode="manual")
    run("current", 20, status="failed", steps=[step(status="failed", reason="Current fixture failure", evidence=["h18-current-evidence"])])
    run("other-target", 21, app="h18-other-app")
    run("other-pack", 21, pack="h18-other-pack")
    run("active", 22, status="running")
    run("pending", 23, status="pending")
    run("empty-current", 20, pack="h18-empty-pack")
    run("thin-current", 20, pack="h18-thin-pack")
    run("thin-pass", 1, pack="h18-thin-pack")
    run("nonreal-current", 20, pack="h18-nonreal-pack")
    run("nonreal-dry", 1, pack="h18-nonreal-pack", provenance="DRY_RUN", steps=[step(provenance="DRY_RUN")])
    run("nonreal-manual", 2, pack="h18-nonreal-pack", mode="manual")
    for evidence_id, run_id, step_id in [
        ("h18-owned", "h18-fail-1", "h18-check"),
        ("h18-wrong-step", "h18-fail-1", "h18-other-step"),
        ("h18-wrong-run", "h18-other-pack", "h18-check"),
        ("h18-current-evidence", "h18-current", "h18-check"),
    ]:
        body = b"Fixture console warning: expected status 200, received 500."
        name = f"{evidence_id}.txt"
        (path / name).write_bytes(body)
        storage.create_evidence(EvidenceFile(id=evidence_id, run_id=run_id, step_id=step_id, name=name, evidence_type="console", mime_type="text/plain", relative_path=name, size_bytes=len(body), provenance="REAL_EXECUTION").model_dump(mode="json"))
    storage.close()
    (path / "fixture.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def snapshot(path: Path) -> dict:
    # mode=ro prevents accidental migration/updates by snapshot verification.
    with sqlite3.connect(f"{(path / 'inspectra_product.db').as_uri()}?mode=ro", uri=True) as connection:
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        rows = {table: connection.execute('SELECT * FROM "' + table.replace('"', '""') + '" ORDER BY rowid').fetchall() for table in tables}
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file() and p.suffix not in {".db", ".json"} and not p.name.endswith(("-wal", "-shm", "-journal"))}
    # Snapshot existing kernel files too; history must never ingest into them.
    for candidate in [ROOT / "memory_kernel.db", ROOT / "artifacts/memory_kernel.db", ROOT / "data/memory_kernel.db"]:
        files[str(candidate)] = hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.exists() else None
    return {"tables": rows, "artifact_hashes": files}


def verify(path: Path, base: str) -> dict:
    before = snapshot(path)

    def get(run_id="h18-current", limit=20):
        with urlopen(f"{base}/api/runs/{run_id}/history?limit={limit}", timeout=10) as response:
            return json.load(response)

    data = get()
    assert data == get()
    assert data["scope"] == {"pack_id": "h18-pack", "app_target_id": "h18-app", "configuration_snapshot_available": False, "exact_match": True, "terminal_statuses": ["completed", "failed", "cancelled"]}
    assert (data["considered_runs"], data["excluded_runs"], data["insufficient_history"]) == (6, 6, False)
    assert data["exclusions_by_reason"] == dict(dry_run=1, simulated=1, demo_example=1, unavailable_provenance=1, mixed_run_level=1, manual_execution=1)
    rate = data["failure_rate"]
    assert (rate["failed"], rate["total"], rate["value"]) == (3, 6, 0.5)
    factual = {"h18-pass", "h18-fail-1", "h18-fail-2", "h18-similar", "h18-different-step", "h18-missing-step"}
    assert {c["run_id"] for c in rate["citations"]} == factual
    assert data["last_passed"]["run_id"] == "h18-pass"
    assert data["last_failed"]["run_id"] == "h18-fail-2"
    assert [r["run_id"] for r in data["manual_observations"]] == ["h18-manual"]
    assert [r["run_id"] for r in data["recent_runs"]] == ["h18-fail-2", "h18-pass", "h18-manual", "h18-mixed", "h18-unavailable", "h18-demo", "h18-simulated", "h18-dry", "h18-missing-step", "h18-different-step", "h18-similar", "h18-fail-1"]
    assert data["comparability_warnings"] == ["Historical execution configuration was not snapshotted; configuration and base URL continuity cannot be verified."]
    steps = {s["step_id"]: s for s in data["step_history"]}
    assert set(steps) == {"h18-check", "h18-other-step", "h18-new-check", "h18-mixed-real", None}
    assert (steps["h18-check"]["passed"], steps["h18-check"]["failed"], steps["h18-check"]["total"]) == (1, 3, 4)
    assert (steps["h18-other-step"]["passed"], steps["h18-other-step"]["total"]) == (2, 2)
    assert steps["h18-new-check"]["total"] == 1
    assert steps["h18-mixed-real"]["total"] == 1
    assert steps[None]["insufficient_identity"] is True and steps[None]["total"] == 1
    repeated = data["repeated_failure_signatures"]
    assert len(repeated) == 1
    assert repeated[0]["occurrences"] == 2 and repeated[0]["failure_reason"] == "timeout waiting"
    assert {c["run_id"] for c in repeated[0]["citations"]} == {"h18-fail-1", "h18-fail-2"}
    # Independently resolve every citation against persisted ownership, not UI labels.
    with sqlite3.connect(f"{(path / 'inspectra_product.db').as_uri()}?mode=ro", uri=True) as db:
        citations = rate["citations"] + [r["citation"] for r in data["recent_runs"]] + [r["citation"] for r in data["manual_observations"]]
        citations += [data["last_passed"]["citation"], data["last_failed"]["citation"]]
        citations += [c for s in data["step_history"] + repeated for c in s["citations"]]
        for c in citations:
            row = db.execute("SELECT step_results FROM live_runs WHERE id=?", (c["run_id"],)).fetchone()
            assert row is not None
            if c["step_id"] is not None:
                assert any(s.get("step_id") == c["step_id"] for s in json.loads(row[0]))
            for evidence_id in c["evidence_ids"]:
                assert db.execute("SELECT run_id, step_id FROM evidence_files WHERE id=?", (evidence_id,)).fetchone() == (c["run_id"], c["step_id"])
    evidence_ids = {e for c in citations for e in c["evidence_ids"]}
    assert evidence_ids == {"h18-owned"}
    assert len(get(limit=1)["recent_runs"]) == 1
    assert get(limit=1)["recent_runs"][0]["run_id"] == "h18-fail-2"
    assert get(limit=50) == data
    for limit in [0, 51]:
        try:
            get(limit=limit)
            raise AssertionError(f"limit {limit} unexpectedly accepted")
        except HTTPError as error:
            assert error.code == 422
    assert get("h18-empty-current")["recent_runs"] == []
    assert get("h18-thin-current")["insufficient_history"] is True
    assert get("h18-thin-current")["failure_rate"]["total"] == 1
    assert get("h18-nonreal-current")["failure_rate"]["total"] == 0
    assert len(get("h18-nonreal-current")["manual_observations"]) == 1
    assert snapshot(path) == before, "History GET mutated persisted state"
    return {"history": data, "unchanged_table_counts": {t: len(rows) for t, rows in before["tables"].items()}, "artifact_hashes_unchanged": True, "limits": {"1": 200, "50": 200, "0": 422, "51": 422}, "citation_count_checked": len(citations)}


if __name__ == "__main__":
    command, raw_path, *args = sys.argv[1:]
    directory = fixture_dir(raw_path)
    if command == "seed":
        result = seed(directory)
    elif command == "snapshot":
        result = snapshot(directory)
    elif command == "verify":
        result = verify(directory, args[0])
    else:
        raise ValueError("Expected seed, snapshot, or verify")
    print(json.dumps(result, sort_keys=True))
