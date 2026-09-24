"""
test_evidence_evaluator.py - Unit tests for AI Evidence Evaluation.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from qa_ai.ai.evidence_evaluator import AIEvidenceEvaluator
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.models import LiveRunRecord, EvidenceFile


@pytest.fixture
def storage(tmp_path: Path) -> ProductStorage:
    db_path = str(tmp_path / "test.db")
    return ProductStorage(db_path=db_path)


def test_prompt_assembly_excludes_binary_content_and_redacts(storage):
    # Setup database with a run and some step results/evidence
    run = LiveRunRecord(
        pack_id="p1",
        app_target_id="a1",
        status="completed"
    )
    storage.create_run(run.model_dump())
    storage.append_run_step_result(run.id, 1, {
        "description": "Load authorization token sk-proj-12345678901234567890",
        "status": "passed",
        "notes": "Bearer secret_token_abc1234"
    })

    # Add evidence files
    ev = EvidenceFile(
        run_id=run.id,
        name="screenshot.png",
        relative_path="r1/screenshot.png",
        mime_type="image/png",
        size_bytes=4096,
        metadata_json={"caption": "some caption"}
    )
    storage.create_evidence(ev.model_dump())

    evaluator = AIEvidenceEvaluator(storage)

    with patch("qa_ai.ai.model_router.ModelRouter.route") as mock_route:
        # We mock a return result so the routing step goes through
        mock_route_result = MagicMock()
        mock_route_result.success = True
        mock_route_result.content = json.dumps({
            "verdict_assessment": "supports_verdict",
            "suggested_verdict": "pass",
            "confidence": 0.95,
            "summary": "Successful verification",
            "evidence_used": ["screenshot.png"],
            "missing_evidence": [],
            "risk_flags": [],
            "rationale": "Everything passed"
        })
        mock_route.return_value = mock_route_result

        note = evaluator.evaluate_run(run.id)
        
        assert note["generation_source"] == "ollama"
        assert note["verdict_assessment"] == "supports_verdict"
        assert note["suggested_verdict"] == "pass"
        assert note["confidence"] == 0.95

        # Check prompt assembly and redaction on mock_route call
        mock_route.assert_called_once()
        prompt_arg = mock_route.call_args[1]["prompt"]
        print("\n=== PROMPT ARG ===")
        print(prompt_arg)
        print("==================\n")

        # No binary or secret content
        assert "sk-proj-12345678901234567890" not in prompt_arg
        assert "secret_token_abc1234" not in prompt_arg
        assert "[REDACTED" in prompt_arg or "REDACTED" in prompt_arg
        # Verify it lists the evidence metadata instead of binary content
        assert "screenshot.png" in prompt_arg
        assert "image/png" in prompt_arg


def test_evidence_evaluator_confidence_clamping(storage):
    run = LiveRunRecord(pack_id="p1", app_target_id="a1", status="failed")
    storage.create_run(run.model_dump())

    evaluator = AIEvidenceEvaluator(storage)

    with patch("qa_ai.ai.model_router.ModelRouter.route") as mock_route:
        # Mock confidence greater than 1.0 or less than 0.0 or malformed
        for bad_conf, expected_conf in [(1.5, 1.0), (-0.5, 0.0), ("invalid", 0.5)]:
            mock_route_result = MagicMock()
            mock_route_result.success = True
            mock_route_result.content = json.dumps({
                "verdict_assessment": "supports_verdict",
                "suggested_verdict": "fail",
                "confidence": bad_conf,
                "summary": "Failure verified",
                "evidence_used": [],
                "missing_evidence": [],
                "risk_flags": [],
                "rationale": "Steps failed"
            })
            mock_route.return_value = mock_route_result

            note = evaluator.evaluate_run(run.id)
            assert note["confidence"] == expected_conf


def test_evidence_evaluator_fallback_verdict_and_confidence(storage):
    # Trigger local fallback logic by making routing throw/fail
    run = LiveRunRecord(pack_id="p1", app_target_id="a1", status="completed")
    storage.create_run(run.model_dump())
    storage.append_run_step_result(run.id, 1, {"status": "passed", "notes": "ok"})

    evaluator = AIEvidenceEvaluator(storage)

    # Force router call to fail
    with patch("qa_ai.ai.model_router.ModelRouter.route", side_effect=RuntimeError("Routing failed")):
        note = evaluator.evaluate_run(run.id)
        assert note["generation_source"] == "local_fallback"
        assert note["verdict_assessment"] == "supports_verdict"
        assert note["suggested_verdict"] == "pass"
        assert note["confidence"] == 0.55
        assert "local_fallback_active" in note["risk_flags"]


def test_evidence_evaluator_fallback_inconclusive(storage):
    # Test inconclusive fallback with empty results
    run = LiveRunRecord(pack_id="p1", app_target_id="a1", status="running")
    storage.create_run(run.model_dump())

    evaluator = AIEvidenceEvaluator(storage)

    # Force router call to fail
    with patch("qa_ai.ai.model_router.ModelRouter.route", side_effect=RuntimeError("Routing failed")):
        note = evaluator.evaluate_run(run.id)
        assert note["generation_source"] == "local_fallback"
        assert note["verdict_assessment"] == "inconclusive"
        assert note["suggested_verdict"] is None
        assert note["confidence"] == 0.50
        assert "local_fallback_active" in note["risk_flags"]
