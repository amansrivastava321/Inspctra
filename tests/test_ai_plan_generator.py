"""
test_ai_plan_generator.py - Unit tests for AI test plan generation backend.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from qa_ai.ai.test_plan_generator import AITestPlanGenerator
from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.models import (
    AITestPlanPreview,
    AITestPlanAcceptRequest,
    AIProposedTestCase,
    AIProposedTestStep,
)


@pytest.fixture
def test_env(tmp_path: Path):
    db_path = str(tmp_path / "test_ai.db")
    artifacts_dir = str(tmp_path / "artifacts")
    app = create_product_app(artifacts_dir=artifacts_dir, db_path=db_path)
    storage = ProductStorage(db_path)
    
    with TestClient(app) as client:
        # Create project and pack via REST API to populate IDs and datetimes correctly
        proj = client.post("/api/projects", json={"name": "Test Project", "description": ""}).json()
        pack = client.post("/api/validation-packs", json={
            "project_id": proj["id"],
            "name": "Smoke Pack",
            "description": "Test pack containing sk-proj-12345678901234567890 (secret key).",
        }).json()
        yield client, storage, pack, proj


def test_no_artifact_store_import():
    """Verify that product_backend never imports ArtifactStore directly."""
    backend_dir = Path(__file__).parent.parent / "qa_ai" / "product_backend"
    for path in backend_dir.rglob("*.py"):
        content = path.read_text()
        # Search for actual import statement, not rule comments
        assert "import ArtifactStore" not in content, f"Banned import of ArtifactStore found in {path}"
        assert "from qa_ai.artifact_store" not in content, f"Banned import from artifact_store found in {path}"


def test_prompt_assembly_redacts_secrets(test_env):
    client, storage, pack, proj = test_env
    generator = AITestPlanGenerator(storage)
    
    with patch("qa_ai.ai.llm_router.LLMRouter.generate_test_plan", return_value='{"test_cases": []}') as mock_gen:
        generator.generate_preview(pack["id"])
        mock_gen.assert_called_once()
        prompt = mock_gen.call_args[0][0]
        # Banned/redacted patterns should not be present
        assert "sk-proj-12345678901234567890" not in prompt
        assert "[REDACTED_API_KEY]" in prompt or "REDACTED" in prompt


def test_fallback_generation_returns_preview(test_env):
    client, storage, pack, proj = test_env
    generator = AITestPlanGenerator(storage)
    
    # Force exception to trigger fallback
    with patch("qa_ai.ai.llm_router.LLMRouter.generate_test_plan", side_effect=RuntimeError("Ollama offline")):
        preview = generator.generate_preview(pack["id"])
        assert isinstance(preview, AITestPlanPreview)
        assert preview.generation_source == "local_fallback"
        assert len(preview.test_cases) > 0
        for tc in preview.test_cases:
            assert tc.confidence == 0.5
            assert "fallback" in tc.rationale.lower()


def test_generated_preview_does_not_persist_cases(test_env):
    client, storage, pack, proj = test_env
    
    # Verify no test cases initially
    initial_cases = storage.list_test_cases(pack["id"])
    assert len(initial_cases) == 0
    
    # Call generate-ai endpoint
    with patch("qa_ai.ai.llm_router.LLMRouter.generate_test_plan", side_effect=RuntimeError("Offline")):
        resp = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate-ai")
        assert resp.status_code == 200
        preview = resp.json()
        assert preview["generation_source"] == "local_fallback"
        assert len(preview["test_cases"]) > 0
        
        # Verify STILL no test cases persisted in database
        assert len(storage.list_test_cases(pack["id"])) == 0


def test_accept_ai_persists_selected_cases_only(test_env):
    client, storage, pack, proj = test_env
    
    # 1. Generate preview
    with patch("qa_ai.ai.llm_router.LLMRouter.generate_test_plan", side_effect=RuntimeError("Offline")):
        resp = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate-ai")
        preview = resp.json()
        
        # 2. Select only the first case
        selected_cases = preview["test_cases"][:1]
        assert len(selected_cases) == 1
        
        # 3. Post to accept endpoint
        accept_resp = client.post(
            f"/api/validation-packs/{pack['id']}/test-plan/accept-ai",
            json={"test_cases": selected_cases}
        )
        assert accept_resp.status_code == 200
        accepted_list = accept_resp.json()
        assert len(accepted_list) == 1
        assert accepted_list[0]["title"] == selected_cases[0]["title"]
        
        # 4. Verify DB persistence
        db_cases = storage.list_test_cases(pack["id"])
        assert len(db_cases) == 1
        assert db_cases[0]["title"] == selected_cases[0]["title"]
        assert db_cases[0]["confidence"] == 0.5
        assert db_cases[0]["rationale"] == selected_cases[0]["rationale"]


def test_unsupported_action_type_rejected(test_env):
    client, storage, pack, proj = test_env
    
    # Construct case with invalid/unsupported action type
    bad_step = AIProposedTestStep(
        action_type="destroy_server_infrastructure",  # Unsupported
        target="db",
        confidence=1.0,
        rationale="Harmful test",
    )
    bad_case = AIProposedTestCase(
        title="Bad AI Case",
        confidence=0.9,
        rationale="Testing validation rejection",
        test_steps=[bad_step],
    )
    
    resp = client.post(
        f"/api/validation-packs/{pack['id']}/test-plan/accept-ai",
        json={"test_cases": [bad_case.model_dump()]}
    )
    assert resp.status_code == 400
    assert "Unsupported action type" in resp.json()["detail"]


def test_confidence_clamped(test_env):
    client, storage, pack, proj = test_env
    
    with patch("qa_ai.ai.llm_router.LLMRouter.generate_test_plan") as mock_generate:
        # Return mock JSON with out-of-bounds confidence values
        mock_generate.return_value = """
        {
            "test_cases": [
                {
                    "title": "Out of bounds case",
                    "confidence": 5.5,
                    "rationale": "High confidence!",
                    "test_steps": [
                        {
                            "action_type": "click",
                            "target": "button",
                            "confidence": -2.0,
                            "rationale": "Low confidence step"
                        }
                    ]
                }
            ]
        }
        """
        
        resp = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate-ai")
        assert resp.status_code == 200
        preview = resp.json()
        
        case = preview["test_cases"][0]
        # Should be clamped to 1.0 and 0.0 respectively
        assert case["confidence"] == 1.0
        assert case["test_steps"][0]["confidence"] == 0.0


def test_existing_non_ai_test_plan_generation_still_works(test_env):
    client, storage, pack, proj = test_env
    
    # Call the traditional deterministic test-plan/generate route
    resp = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate")
    assert resp.status_code == 201
    plan = resp.json()
    assert plan["generated_from"] == "generic_app_type_template"
    assert len(plan["test_cases"]) > 0
