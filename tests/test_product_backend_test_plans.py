"""
test_product_backend_test_plans.py — Tests for test plan + test case backend.

Coverage:
1.  Generate generic web plan — creates plan + cases.
2.  Generate generic API plan.
3.  Generate generic AI app plan.
4.  Edge cases present in web plan.
5.  Negative cases present in web plan.
6.  Destructive cases NOT enabled by default.
7.  GET test-plan returns existing plan (no overwrite).
8.  Create / update / delete test case.
9.  No hardcoded FlowBook/Videomation strings in generated cases.
10. No secrets stored — titles/descriptions have no credentials.

All tests use in-process TestClient with tmp SQLite. No real network.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.server import create_product_app
from qa_ai.product_backend.test_plan_service import generate_generic_test_plan


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_path = str(tmp_path / "test_plans.db")
    artifacts_dir = str(tmp_path / "artifacts")
    app = create_product_app(artifacts_dir=artifacts_dir, db_path=db_path)
    with TestClient(app) as c:
        yield c


def _make_pack(client: TestClient) -> dict:
    """Helper: create project + pack, return pack dict."""
    proj = client.post("/api/projects", json={"name": "Test Project"}).json()
    pack = client.post("/api/validation-packs", json={
        "project_id": proj["id"],
        "name": "Smoke Pack",
    }).json()
    return pack


# ── Part 1: generic web plan ──────────────────────────────────────────────────

class TestGenerateWebPlan:
    def test_generate_creates_plan_and_cases(self, client):
        pack = _make_pack(client)
        resp = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate")
        assert resp.status_code == 201
        data = resp.json()
        assert data["pack_id"] == pack["id"]
        assert data["generated_from"] == "generic_app_type_template"
        assert len(data["test_cases"]) > 0

    def test_generate_coverage_summary_populated(self, client):
        pack = _make_pack(client)
        data = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate").json()
        assert data["coverage_summary"]  # non-empty dict
        assert isinstance(data["coverage_summary"], dict)

    def test_get_plan_returns_same_plan(self, client):
        pack = _make_pack(client)
        created = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate").json()
        fetched = client.get(f"/api/validation-packs/{pack['id']}/test-plan").json()
        assert fetched["plan_id"] == created["plan_id"]

    def test_get_plan_returns_null_when_none(self, client):
        pack = _make_pack(client)
        resp = client.get(f"/api/validation-packs/{pack['id']}/test-plan")
        assert resp.status_code == 200
        assert resp.json() is None


# ── Part 2: API app plan ──────────────────────────────────────────────────────

class TestGenerateApiPlan:
    def test_api_plan_has_health_check(self):
        plan = generate_generic_test_plan("pack-1", app_type="api")
        titles = [c["title"].lower() for c in plan["test_cases"]]
        assert any("health" in t for t in titles)

    def test_api_plan_has_auth_test(self):
        plan = generate_generic_test_plan("pack-1", app_type="api")
        types = [c["test_type"] for c in plan["test_cases"]]
        assert "security" in types

    def test_api_plan_has_validation_test(self):
        plan = generate_generic_test_plan("pack-1", app_type="api")
        types = [c["test_type"] for c in plan["test_cases"]]
        assert "negative" in types


# ── Part 3: AI app plan ───────────────────────────────────────────────────────

class TestGenerateAiAppPlan:
    def test_ai_plan_generated(self):
        plan = generate_generic_test_plan("pack-2", app_type="ai_app")
        assert len(plan["test_cases"]) > 0

    def test_ai_plan_has_ai_behavior_type(self):
        plan = generate_generic_test_plan("pack-2", app_type="ai_app")
        types = {c["test_type"] for c in plan["test_cases"]}
        assert "ai_behavior" in types

    def test_ai_plan_has_edge_case(self):
        plan = generate_generic_test_plan("pack-2", app_type="ai_app")
        types = {c["test_type"] for c in plan["test_cases"]}
        assert "edge_case" in types


# ── Part 4 + 5: edge and negative cases ──────────────────────────────────────

class TestEdgeAndNegativeCases:
    def test_web_plan_has_edge_case(self):
        plan = generate_generic_test_plan("pack-3", app_type="web")
        types = {c["test_type"] for c in plan["test_cases"]}
        assert "edge_case" in types

    def test_web_plan_has_negative(self):
        plan = generate_generic_test_plan("pack-3", app_type="web")
        types = {c["test_type"] for c in plan["test_cases"]}
        assert "negative" in types

    def test_web_plan_has_security(self):
        plan = generate_generic_test_plan("pack-3", app_type="web")
        types = {c["test_type"] for c in plan["test_cases"]}
        assert "security" in types


# ── Part 6: destructive cases disabled by default ────────────────────────────

class TestDestructiveCasesDisabledByDefault:
    def test_destructive_cases_not_enabled(self):
        plan = generate_generic_test_plan("pack-4", app_type="web")
        destructive = [c for c in plan["test_cases"] if c["safety_level"] == "destructive"]
        # All destructive cases must have enabled=False by default
        for c in destructive:
            assert c["enabled"] is False, (
                f"Destructive case '{c['title']}' must not be enabled by default"
            )

    def test_destructive_cases_not_enabled_api(self):
        plan = generate_generic_test_plan("pack-4", app_type="api")
        destructive = [c for c in plan["test_cases"] if c["safety_level"] == "destructive"]
        for c in destructive:
            assert c["enabled"] is False

    def test_safe_cases_are_enabled(self):
        plan = generate_generic_test_plan("pack-5", app_type="web")
        safe = [c for c in plan["test_cases"] if c["safety_level"] == "safe"]
        assert len(safe) > 0
        for c in safe:
            assert c["enabled"] is True


# ── Part 7: no overwrite without force ───────────────────────────────────────

class TestNoOverwriteWithoutForce:
    def test_second_generate_returns_existing(self, client):
        pack = _make_pack(client)
        first = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate").json()
        second = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate").json()
        assert first["plan_id"] == second["plan_id"]

    def test_force_true_overwrites_plan(self, client):
        pack = _make_pack(client)
        first = client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate").json()
        second = client.post(
            f"/api/validation-packs/{pack['id']}/test-plan/generate",
            json={"force": True},
        ).json()
        assert first["plan_id"] != second["plan_id"]


# ── Part 8: CRUD test cases ───────────────────────────────────────────────────

class TestTestCaseCRUD:
    def test_create_test_case_manually(self, client):
        pack = _make_pack(client)
        # Generate plan first
        client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate")
        resp = client.post(f"/api/validation-packs/{pack['id']}/test-cases", json={
            "title": "Custom login test",
            "test_type": "positive",
            "priority": "P0",
            "risk_level": "high",
            "steps": ["Open login form", "Enter credentials", "Click submit"],
            "expected_result": "User logged in, dashboard visible",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Custom login test"
        assert data["test_case_id"]

    def test_update_test_case(self, client):
        pack = _make_pack(client)
        client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate")
        cases = client.get(f"/api/validation-packs/{pack['id']}/test-cases").json()
        tc_id = cases[0]["test_case_id"]
        resp = client.patch(
            f"/api/validation-packs/{pack['id']}/test-cases/{tc_id}",
            json={"priority": "P0"},
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == "P0"

    def test_delete_test_case(self, client):
        pack = _make_pack(client)
        client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate")
        cases = client.get(f"/api/validation-packs/{pack['id']}/test-cases").json()
        tc_id = cases[0]["test_case_id"]
        del_resp = client.delete(f"/api/validation-packs/{pack['id']}/test-cases/{tc_id}")
        assert del_resp.status_code == 204
        remaining = client.get(f"/api/validation-packs/{pack['id']}/test-cases").json()
        ids = [c["test_case_id"] for c in remaining]
        assert tc_id not in ids

    def test_list_test_cases_by_type(self, client):
        pack = _make_pack(client)
        client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate")
        resp = client.get(f"/api/validation-packs/{pack['id']}/test-cases?test_type=security")
        assert resp.status_code == 200
        for tc in resp.json():
            assert tc["test_type"] == "security"

    def test_delete_nonexistent_case_returns_404(self, client):
        pack = _make_pack(client)
        resp = client.delete(f"/api/validation-packs/{pack['id']}/test-cases/nonexistent")
        assert resp.status_code == 404

    def test_create_api_test_step_persists_api_fields(self, client):
        pack = _make_pack(client)
        client.post(f"/api/validation-packs/{pack['id']}/test-plan/generate")
        case_id = client.get(f"/api/validation-packs/{pack['id']}/test-cases").json()[0]["test_case_id"]

        resp = client.post(
            f"/api/test-cases/{case_id}/steps",
            json={
                "action_type": "api_request",
                "method": "POST",
                "url": "https://example.com/api/items",
                "headers": {"Authorization": "Bearer secret"},
                "query_params": {"expand": "full"},
                "body_json": {"name": "Widget"},
                "timeout_ms": 5000,
                "notes": "Create item",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["action_type"] == "api_request"
        assert data["method"] == "POST"
        assert data["url"] == "https://example.com/api/items"
        assert data["body_json"] == {"name": "Widget"}


# ── Part 9: no hardcoded app names ───────────────────────────────────────────

_BANNED_NAMES = {"flowbook", "videomation", "inspectra_app", "myapp"}


class TestNoHardcodedAppNames:
    def _all_text(self, plan: dict) -> str:
        parts = []
        for c in plan["test_cases"]:
            parts.extend([c.get("title", ""), c.get("description", ""),
                          c.get("expected_result", ""), c.get("flow_name", "")])
        return " ".join(parts).lower()

    def test_web_plan_no_app_names(self):
        plan = generate_generic_test_plan("x", app_type="web")
        text = self._all_text(plan)
        for name in _BANNED_NAMES:
            assert name not in text, f"Hardcoded app name '{name}' found in web plan"

    def test_api_plan_no_app_names(self):
        plan = generate_generic_test_plan("x", app_type="api")
        text = self._all_text(plan)
        for name in _BANNED_NAMES:
            assert name not in text, f"Hardcoded app name '{name}' found in api plan"


# ── Part 10: no secrets stored ───────────────────────────────────────────────

_SECRET_PATTERNS = ["password=", "api_key=", "token=", "secret=", "bearer "]


class TestNoSecretsStored:
    def _all_text(self, plan: dict) -> str:
        import json
        return json.dumps(plan).lower()

    def test_web_plan_no_secrets(self):
        plan = generate_generic_test_plan("x", app_type="web")
        text = self._all_text(plan)
        for pat in _SECRET_PATTERNS:
            assert pat not in text, f"Possible secret pattern '{pat}' in generated plan"

    def test_api_plan_no_secrets(self):
        plan = generate_generic_test_plan("x", app_type="api")
        text = self._all_text(plan)
        for pat in _SECRET_PATTERNS:
            assert pat not in text, f"Possible secret pattern '{pat}' in api plan"


class TestTestCaseStepsAndDuplication:
    def test_step_crud_lifecycle(self, client):
        pack = _make_pack(client)
        # Create case manually
        case = client.post(f"/api/validation-packs/{pack['id']}/test-cases", json={
            "title": "Custom login test",
            "test_type": "positive",
            "priority": "P0",
            "risk_level": "high",
        }).json()
        case_id = case["test_case_id"]

        # Create step
        resp = client.post(f"/api/test-cases/{case_id}/steps", json={
            "action_type": "navigate",
            "target": "/home",
            "timeout_ms": 15000,
        })
        assert resp.status_code == 201
        step = resp.json()
        assert step["step_id"]
        assert step["action_type"] == "navigate"
        assert step["target"] == "/home"
        assert step["timeout_ms"] == 15000

        # Update step
        patch_resp = client.patch(f"/api/test-steps/{step['step_id']}", json={
            "target": "/dashboard",
            "optional": True,
        })
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["target"] == "/dashboard"
        assert updated["optional"] is True

        # Delete step
        del_resp = client.delete(f"/api/test-steps/{step['step_id']}")
        assert del_resp.status_code == 204

    def test_step_validations(self, client):
        pack = _make_pack(client)
        case = client.post(f"/api/validation-packs/{pack['id']}/test-cases", json={
            "title": "Custom login test",
            "test_type": "positive",
            "priority": "P0",
            "risk_level": "high",
        }).json()
        case_id = case["test_case_id"]

        # Invalid action_type
        resp = client.post(f"/api/test-cases/{case_id}/steps", json={
            "action_type": "invalid_action",
            "target": "/home",
        })
        assert resp.status_code == 422

        # Too long target
        resp = client.post(f"/api/test-cases/{case_id}/steps", json={
            "action_type": "click",
            "target": "a" * 501,
        })
        assert resp.status_code == 422

        # Too long value
        resp = client.post(f"/api/test-cases/{case_id}/steps", json={
            "action_type": "type",
            "target": "#input",
            "value": "b" * 1001,
        })
        assert resp.status_code == 422

    def test_step_reordering(self, client):
        pack = _make_pack(client)
        case = client.post(f"/api/validation-packs/{pack['id']}/test-cases", json={
            "title": "Custom login test",
            "test_type": "positive",
            "priority": "P0",
            "risk_level": "high",
        }).json()
        case_id = case["test_case_id"]

        # Add two steps
        s1 = client.post(f"/api/test-cases/{case_id}/steps", json={"action_type": "navigate", "target": "/1"}).json()
        s2 = client.post(f"/api/test-cases/{case_id}/steps", json={"action_type": "navigate", "target": "/2"}).json()

        # Reorder
        reorder_resp = client.post(f"/api/test-cases/{case_id}/steps/reorder", json={
            "step_ids": [s2["step_id"], s1["step_id"]]
        })
        assert reorder_resp.status_code == 200

        # Fetch case steps and check ordering
        updated_case = client.get(f"/api/validation-packs/{pack['id']}/test-cases").json()[0]
        step_ids = [s["step_id"] for s in sorted(updated_case["test_steps"], key=lambda x: x["step_order"])]
        assert step_ids == [s2["step_id"], s1["step_id"]]

    def test_duplicate_test_case(self, client):
        pack = _make_pack(client)
        case = client.post(f"/api/validation-packs/{pack['id']}/test-cases", json={
            "title": "Custom login test",
            "test_type": "positive",
            "priority": "P0",
            "risk_level": "high",
        }).json()
        case_id = case["test_case_id"]

        # Add a step first
        s1 = client.post(f"/api/test-cases/{case_id}/steps", json={"action_type": "navigate", "target": "/dup"}).json()

        # Duplicate
        dup_resp = client.post(f"/api/test-cases/{case_id}/duplicate")
        assert dup_resp.status_code == 201
        dup_case = dup_resp.json()
        assert dup_case["test_case_id"] != case_id
        assert dup_case["title"] == "Custom login test (Copy)"
        assert len(dup_case["test_steps"]) == 1
        assert dup_case["test_steps"][0]["target"] == "/dup"
