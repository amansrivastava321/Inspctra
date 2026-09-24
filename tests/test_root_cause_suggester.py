from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.models import EvidenceFile, LiveRunRecord, Provenance
from qa_ai.product_backend.storage import ProductStorage


def _suggester_class():
    return importlib.import_module("qa_ai.ai.root_cause_suggester").AIRootCauseSuggester


@pytest.fixture
def rca_env(tmp_path: Path):
    storage = ProductStorage(str(tmp_path / "inspectra.db"))
    index = ArtifactIndex(tmp_path / "artifacts")
    run = LiveRunRecord(
        id="run-failed",
        pack_id="pack-1",
        app_target_id="app-1",
        status="failed",
        error="AssertionError",
        execution_mode="automated",
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_run(run.model_dump())
    storage.append_run_step_result(
        run.id,
        1,
        {
            "step_id": "step-1",
            "action_type": "assert_text",
            "status": "failed",
            "failure_reason": "Expected Welcome but was Login",
            "error": "AssertionError",
            "notes": "Selector #title returned Login",
            "expected": "Welcome",
            "actual": "Login",
            "duration_ms": 420,
            "provenance": Provenance.REAL_EXECUTION.value,
            "evidence_ids": [],
        },
    )
    storage.create_run_event(
        {
            "run_id": run.id,
            "step_index": 1,
            "step_id": "step-1",
            "event_type": "error",
            "message": "Assertion failed after navigation",
            "payload": {"status": "failed"},
        }
    )
    yield storage, index, run.id
    storage.close()


def _add_evidence(
    storage: ProductStorage,
    index: ArtifactIndex,
    *,
    evidence_id: str,
    evidence_type: str,
    content: bytes,
    suffix: str = "json",
    mime_type: str = "application/json",
    metadata: dict[str, Any] | None = None,
    provenance: Provenance = Provenance.REAL_EXECUTION,
) -> None:
    relative_path = f"runs/run-failed/{evidence_id}.{suffix}"
    index.write_file(relative_path, content)
    storage.create_evidence(
        EvidenceFile(
            id=evidence_id,
            run_id="run-failed",
            step_id="step-1",
            evidence_type=evidence_type,
            name=evidence_id,
            relative_path=relative_path,
            mime_type=mime_type,
            size_bytes=len(content),
            metadata_json=metadata or {},
            provenance=provenance,
        ).model_dump()
    )


def test_context_contains_run_step_evidence_and_durable_events(rca_env):
    storage, index, run_id = rca_env
    _add_evidence(
        storage,
        index,
        evidence_id="ev-console",
        evidence_type="console",
        content=json.dumps([{"type": "error", "message": "title mismatch"}]).encode(),
    )

    context = _suggester_class()(storage, index).build_context(run_id)

    assert context["run"]["status"] == "failed"
    assert context["steps"][0]["step_id"] == "step-1"
    assert context["evidence"][0]["id"] == "ev-console"
    assert "title mismatch" in context["evidence"][0]["content"]
    assert context["events"][0]["event_type"] == "error"
    assert context["deterministic_signals"][0]["category"] == "Assertion failed"


def test_context_recursively_redacts_sensitive_values(rca_env):
    storage, index, run_id = rca_env
    payload = {
        "headers": {
            "Authorization": "Bearer top-secret",
            "Cookie": "sid=hidden",
            "X-API-Key": "key-hidden",
        },
        "nested": [{"client_secret": "client-hidden", "password": "pw-hidden"}],
        "message": "token=plain-hidden",
    }
    _add_evidence(
        storage,
        index,
        evidence_id="ev-secret",
        evidence_type="api_response",
        content=json.dumps(payload).encode(),
        metadata=payload,
    )

    serialized = json.dumps(_suggester_class()(storage, index).build_context(run_id))

    for secret in ("top-secret", "sid=hidden", "key-hidden", "client-hidden", "pw-hidden", "plain-hidden"):
        assert secret not in serialized
    assert "[REDACTED]" in serialized


def test_context_excludes_binary_and_source_files(rca_env):
    storage, index, run_id = rca_env
    _add_evidence(
        storage,
        index,
        evidence_id="ev-image",
        evidence_type="screenshot",
        content=b"\x89PNG\r\nsecret-image-bytes",
        suffix="png",
        mime_type="image/png",
    )
    _add_evidence(
        storage,
        index,
        evidence_id="ev-source",
        evidence_type="console",
        content=b"print('source-secret')",
        suffix="py",
        mime_type="text/plain",
    )

    context = _suggester_class()(storage, index).build_context(run_id)
    evidence = {item["id"]: item for item in context["evidence"]}

    assert evidence["ev-image"]["content"] is None
    assert evidence["ev-source"]["content"] is None
    assert "secret-image-bytes" not in json.dumps(context)
    assert "source-secret" not in json.dumps(context)


def test_context_enforces_evidence_count_and_text_limits(rca_env):
    storage, index, run_id = rca_env
    for number in range(25):
        _add_evidence(
            storage,
            index,
            evidence_id=f"ev-{number:02d}",
            evidence_type="console",
            content=(f"marker-{number}-" + "x" * 20_000).encode(),
            suffix="log",
            mime_type="text/plain",
        )

    context = _suggester_class()(storage, index).build_context(run_id)
    contents = [item["content"] for item in context["evidence"] if item["content"]]

    assert len(context["evidence"]) == 20
    assert all(len(value.encode()) <= 16 * 1024 for value in contents)
    assert sum(len(value.encode()) for value in contents) <= 64 * 1024


def test_local_fallback_is_advisory_cited_and_conservative(rca_env, monkeypatch):
    storage, index, run_id = rca_env
    suggester = _suggester_class()(storage, index)
    monkeypatch.setattr(suggester, "_try_model", lambda _context: None)

    batch = suggester.suggest(run_id)

    assert batch["status"] == "suggested"
    assert batch["authoritative"] is False
    assert batch["generation_source"] == "local_fallback"
    assert batch["suggestions"]
    suggestion = batch["suggestions"][0]
    assert suggestion["possible_cause"].lower().startswith("possible cause")
    assert suggestion["evidence_refs"]
    assert suggestion["confidence"] <= 0.65
    assert suggestion["authoritative"] is False


def test_insufficient_evidence_returns_empty_inconclusive(tmp_path: Path, monkeypatch):
    storage = ProductStorage(str(tmp_path / "empty.db"))
    index = ArtifactIndex(tmp_path / "artifacts")
    run = LiveRunRecord(
        id="run-empty",
        pack_id="pack",
        app_target_id="app",
        status="cancelled",
        provenance=Provenance.UNAVAILABLE,
    )
    storage.create_run(run.model_dump())
    suggester = _suggester_class()(storage, index)
    monkeypatch.setattr(suggester, "_try_model", lambda _context: None)

    batch = suggester.suggest(run.id)

    assert batch["status"] == "inconclusive"
    assert batch["source_provenance"] == "UNAVAILABLE"
    assert batch["suggestions"] == []
    assert batch["missing_evidence"]
    storage.close()


def test_model_output_is_clamped_reworded_and_unknown_citations_rejected(rca_env, monkeypatch):
    storage, index, run_id = rca_env
    suggester = _suggester_class()(storage, index)
    model_output = {
        "suggestions": [
            {
                "step_id": "step-1",
                "title": "Assertion mismatch",
                "possible_cause": "Root cause is broken application code",
                "category": "Assertion failed",
                "confidence": 5,
                "evidence_refs": [{"type": "step_field", "id": "step-1", "field": "failure_reason"}],
                "supporting_signals": ["Expected and actual differ"],
                "contradicting_signals": [],
                "missing_evidence": [],
                "recommended_verification": ["Inspect captured page state"],
                "suggested_owner_area": "test_automation",
                "authoritative": False,
            },
            {
                "step_id": "invented-step",
                "title": "Invented",
                "possible_cause": "Definitely caused by a database bug",
                "category": "Unknown",
                "confidence": 0.9,
                "evidence_refs": [{"type": "evidence", "id": "invented-evidence", "field": "body"}],
            },
        ]
    }
    monkeypatch.setattr(suggester, "_try_model", lambda _context: model_output)

    batch = suggester.suggest(run_id)

    assert len(batch["suggestions"]) == 1
    suggestion = batch["suggestions"][0]
    assert suggestion["confidence"] <= 0.55
    assert suggestion["possible_cause"].startswith("Possible cause:")
    assert "root cause is" not in suggestion["possible_cause"].lower()
    assert suggestion["authoritative"] is False


@pytest.mark.parametrize("model_value", [None, "malformed", {"suggestions": "bad"}])
def test_invalid_model_output_uses_fallback(rca_env, monkeypatch, model_value):
    storage, index, run_id = rca_env
    suggester = _suggester_class()(storage, index)
    monkeypatch.setattr(suggester, "_try_model", lambda _context: model_value)

    batch = suggester.suggest(run_id)

    assert batch["generation_source"] == "local_fallback"
    assert batch["authoritative"] is False
