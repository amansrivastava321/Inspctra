"""
test_plans.py - Test plan and test case routes for validation packs.

Routes:
  GET    /validation-packs/{pack_id}/test-plan
  POST   /validation-packs/{pack_id}/test-plan/generate
  GET    /validation-packs/{pack_id}/test-cases
  POST   /validation-packs/{pack_id}/test-cases
  PATCH  /validation-packs/{pack_id}/test-cases/{test_case_id}
  DELETE /validation-packs/{pack_id}/test-cases/{test_case_id}
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from qa_ai.product_backend.dependencies import get_storage
from qa_ai.product_backend.models import (
    TestCase,
    TestCaseCreate,
    TestCaseUpdate,
    TestPlan,
    TestPlanGenerateRequest,
    TestCaseStep,
    TestCaseStepCreate,
    TestCaseStepUpdate,
    StepReorderRequest,
    SUPPORTED_API_ACTIONS,
    SUPPORTED_TEST_STEP_ACTIONS,
    AITestPlanPreview,
    AITestPlanAcceptRequest,
)
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.test_plan_service import generate_generic_test_plan

router = APIRouter(tags=["test-plans"])


def _get_pack_or_404(pack_id: str, storage: ProductStorage) -> dict:
    pack = storage.get_validation_pack(pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation pack not found.")
    return pack


def _get_test_case_or_404(test_case_id: str, pack_id: str, storage: ProductStorage) -> dict:
    row = storage.get_test_case(test_case_id)
    if row is None or row.get("pack_id") != pack_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    return row


def _build_test_plan_response(plan_row: dict, storage: ProductStorage) -> dict:
    """Attach test_cases to a plan row for the response."""
    cases = storage.list_test_cases(plan_row["pack_id"])
    plan_row["test_cases"] = cases
    return plan_row


# ── GET /validation-packs/{pack_id}/test-plan ─────────────────────────────────

@router.get("/validation-packs/{pack_id}/test-plan", response_model=Optional[TestPlan])
def get_test_plan(
    pack_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> Optional[TestPlan]:
    """Return the test plan for a pack, or null if none exists."""
    _get_pack_or_404(pack_id, storage)
    plan_row = storage.get_test_plan_for_pack(pack_id)
    if plan_row is None:
        return None
    plan_row = _build_test_plan_response(plan_row, storage)
    return TestPlan(**plan_row)


# ── POST /validation-packs/{pack_id}/test-plan/generate ───────────────────────

@router.post("/validation-packs/{pack_id}/test-plan/generate", response_model=TestPlan,
             status_code=status.HTTP_201_CREATED)
def generate_test_plan(
    pack_id: str,
    body: TestPlanGenerateRequest = TestPlanGenerateRequest(),
    storage: ProductStorage = Depends(get_storage),
) -> TestPlan:
    """
    Generate a generic test plan for this pack.

    - Uses app_type from the pack's linked app target if available.
    - If no app target, falls back to generic web template.
    - Does NOT overwrite an existing plan unless force=True.
    - Does NOT auto-enable destructive test cases.
    - Does NOT make any external calls.
    """
    pack_row = _get_pack_or_404(pack_id, storage)

    existing = storage.get_test_plan_for_pack(pack_id)
    if existing and not body.force:
        existing = _build_test_plan_response(existing, storage)
        return TestPlan(**existing)

    # Delete existing plan + cases if force=True
    if existing and body.force:
        storage.delete_test_plan_for_pack(pack_id)

    # Resolve app_id and app_type.
    # Priority: 1) body.app_id, 2) pack.app_id, 3) most recent run's app_target_id.
    app_id: Optional[str] = body.app_id
    app_type: Optional[str] = None

    if not app_id:
        app_id = pack_row.get("app_id")  # use pack-linked app if set

    if not app_id:
        recent_runs = storage.list_runs(pack_id=pack_id, limit=1)
        if recent_runs:
            app_target_id = recent_runs[0].get("app_target_id")
            if app_target_id:
                target = storage.get_app_target(app_target_id)
                if target:
                    app_type = target.get("app_type")
                    app_id = target.get("id")

    if app_id and not app_type:
        target = storage.get_app_target(app_id)
        if target:
            app_type = target.get("app_type")

    # Load app_map if one exists for this app
    app_map = None
    if app_id:
        app_map = storage.get_app_map_for_app(app_id)

    # Generate plan dict
    plan_data = generate_generic_test_plan(
        pack_id=pack_id,
        app_type=app_type,
        app_id=app_id,
        app_map=app_map,
    )

    # Persist plan
    plan_for_storage = {k: v for k, v in plan_data.items() if k != "test_cases"}
    storage.create_test_plan(plan_for_storage)

    # Persist test cases
    for tc in plan_data["test_cases"]:
        # Normalize — ensure all required fields present
        tc.setdefault("description", "")
        tc.setdefault("flow_name", "")
        tc.setdefault("preconditions", [])
        tc.setdefault("expected_evidence", [])
        tc.setdefault("pass_criteria", "")
        tc.setdefault("fail_criteria", "")
        tc.setdefault("tags", [])
        tc.setdefault("requires_permission", False)
        tc.setdefault("enabled", True)
        storage.create_test_case(tc)
        populate_default_steps_for_test_case(storage, tc["test_case_id"], tc.get("steps", []))

    plan_data = _build_test_plan_response(
        storage.get_test_plan_for_pack(pack_id) or plan_for_storage,
        storage,
    )
    return TestPlan(**plan_data)


# ── GET /validation-packs/{pack_id}/test-cases ────────────────────────────────

@router.get("/validation-packs/{pack_id}/test-cases", response_model=List[TestCase])
def list_test_cases(
    pack_id: str,
    test_type: Optional[str] = Query(default=None),
    storage: ProductStorage = Depends(get_storage),
) -> List[TestCase]:
    _get_pack_or_404(pack_id, storage)
    rows = storage.list_test_cases(pack_id)
    if test_type:
        rows = [r for r in rows if r.get("test_type") == test_type]
    return [TestCase(**r) for r in rows]


# ── POST /validation-packs/{pack_id}/test-cases ───────────────────────────────

@router.post("/validation-packs/{pack_id}/test-cases", response_model=TestCase,
             status_code=status.HTTP_201_CREATED)
def create_test_case(
    pack_id: str,
    body: TestCaseCreate,
    storage: ProductStorage = Depends(get_storage),
) -> TestCase:
    pack_row = _get_pack_or_404(pack_id, storage)

    # Require a plan to exist (create one if missing)
    plan_row = storage.get_test_plan_for_pack(pack_id)
    if plan_row is None:
        from qa_ai.product_backend.models import _new_id, _now_iso
        now = _now_iso()
        plan_row = {
            "plan_id": _new_id(),
            "pack_id": pack_id,
            "app_id": None,
            "generated_from": "manual",
            "coverage_summary": {},
            "risk_summary": {},
            "created_at": now,
            "updated_at": now,
        }
        storage.create_test_plan(plan_row)

    from qa_ai.product_backend.models import TestCase as TC
    tc = TC(plan_id=plan_row["plan_id"], pack_id=pack_id, **body.model_dump())
    storage.create_test_case(tc.model_dump())
    populate_default_steps_for_test_case(storage, tc.test_case_id, tc.steps)
    return tc


# ── PATCH /validation-packs/{pack_id}/test-cases/{test_case_id} ──────────────

@router.patch("/validation-packs/{pack_id}/test-cases/{test_case_id}", response_model=TestCase)
def update_test_case(
    pack_id: str,
    test_case_id: str,
    body: TestCaseUpdate,
    storage: ProductStorage = Depends(get_storage),
) -> TestCase:
    _get_pack_or_404(pack_id, storage)
    _get_test_case_or_404(test_case_id, pack_id, storage)
    fields = body.model_dump(exclude_none=True)
    updated = storage.update_test_case(test_case_id, fields)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    return TestCase(**updated)


# ── DELETE /validation-packs/{pack_id}/test-cases/{test_case_id} ─────────────

@router.delete("/validation-packs/{pack_id}/test-cases/{test_case_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case(
    pack_id: str,
    test_case_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> None:
    _get_pack_or_404(pack_id, storage)
    row = storage.get_test_case(test_case_id)
    if row is None or row.get("pack_id") != pack_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    storage.delete_test_case(test_case_id)


# ── Helper for default step generation ────────────────────────────────────────

def populate_default_steps_for_test_case(storage: ProductStorage, test_case_id: str, steps: List[str]) -> None:
    import uuid
    from qa_ai.product_backend.models import _now_iso
    for index, step_str in enumerate(steps):
        action_type = "click"
        target = ""
        value = ""
        expected = ""
        optional = False
        notes = step_str
        
        lower_str = step_str.lower()
        if "navigate" in lower_str or "goto" in lower_str or "load" in lower_str:
            action_type = "navigate"
            target = "/"
        elif "screenshot" in lower_str:
            action_type = "screenshot"
        elif "click" in lower_str or "submit" in lower_str or "press" in lower_str:
            action_type = "click"
            if "submit" in lower_str:
                target = "button[type=submit]"
            else:
                target = "button"
        elif "type" in lower_str or "fill" in lower_str or "enter" in lower_str:
            action_type = "type"
            target = "input"
            value = "test"
        elif "select" in lower_str:
            action_type = "select"
            target = "select"
            value = "option"
        elif "wait" in lower_str:
            action_type = "wait_for_selector"
            target = "body"
        elif "visible" in lower_str or "show" in lower_str:
            action_type = "assert_visible"
            target = "body"
        elif "text" in lower_str or "contain" in lower_str:
            action_type = "assert_text_contains"
            target = "body"
            value = "expected"
        elif "url" in lower_str:
            action_type = "assert_url_contains"
            value = "/"
        elif "title" in lower_str:
            action_type = "assert_title_contains"
            value = "App"
        
        if step_str in ("navigate", "screenshot", "click", "type", "select", "press", "wait_for_selector", "assert_visible", "assert_text_contains", "assert_url_contains", "assert_title_contains"):
            action_type = step_str
            if action_type == "navigate":
                target = "/"
            elif action_type == "assert_title_contains":
                value = "App"
        elif step_str in SUPPORTED_API_ACTIONS:
            action_type = step_str
            if action_type == "api_request":
                target = "/api/health"
                
        storage.create_test_step({
            "step_id": str(uuid.uuid4()),
            "case_id": test_case_id,
            "step_order": index,
            "action_type": action_type,
            "target": target or None,
            "value": value or None,
            "expected": expected or None,
            "method": "GET" if action_type == "api_request" else None,
            "url": (target or None) if action_type == "api_request" else None,
            "timeout_ms": 30000,
            "optional": optional,
            "notes": notes,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        })


# ── PATCH /test-cases/{case_id} ──────────────────────────────────────────────

@router.patch("/test-cases/{case_id}", response_model=TestCase)
def patch_test_case(
    case_id: str,
    body: TestCaseUpdate,
    storage: ProductStorage = Depends(get_storage),
) -> TestCase:
    row = storage.get_test_case(case_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    fields = body.model_dump(exclude_none=True)
    updated = storage.update_test_case(case_id, fields)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    return TestCase(**updated)


# ── DELETE /test-cases/{case_id} ─────────────────────────────────────────────

@router.delete("/test-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case_direct(
    case_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> None:
    row = storage.get_test_case(case_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    storage.delete_test_case(case_id)


# ── POST /test-cases/{case_id}/duplicate ─────────────────────────────────────

@router.post("/test-cases/{case_id}/duplicate", response_model=TestCase, status_code=status.HTTP_201_CREATED)
def duplicate_test_case(
    case_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> TestCase:
    new_case_id = storage.duplicate_test_case_with_steps(case_id)
    if new_case_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    row = storage.get_test_case(new_case_id)
    return TestCase(**row)


# ── POST /test-cases/{case_id}/steps ─────────────────────────────────────────

@router.post("/test-cases/{case_id}/steps", response_model=TestCaseStep, status_code=status.HTTP_201_CREATED)
def create_test_step(
    case_id: str,
    body: TestCaseStepCreate,
    storage: ProductStorage = Depends(get_storage),
) -> TestCaseStep:
    case = storage.get_test_case(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    
    import uuid
    from qa_ai.product_backend.models import _now_iso
    steps = storage.list_test_steps(case_id)
    step_order = len(steps)
    
    rec = {
        "step_id": str(uuid.uuid4()),
        "case_id": case_id,
        "step_order": step_order,
        "action_type": body.action_type,
        "target": body.target,
        "value": body.value,
        "expected": body.expected,
        "method": body.method,
        "url": body.url,
        "headers": body.headers,
        "query_params": body.query_params,
        "body_json": body.body_json,
        "expected_status": body.expected_status,
        "expected_json_path": body.expected_json_path,
        "expected_value": body.expected_value,
        "timeout_ms": body.timeout_ms,
        "optional": body.optional,
        "notes": body.notes,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    storage.create_test_step(rec)
    return TestCaseStep(**rec)


# ── PATCH /test-steps/{step_id} ──────────────────────────────────────────────

@router.patch("/test-steps/{step_id}", response_model=TestCaseStep)
def patch_test_step(
    step_id: str,
    body: TestCaseStepUpdate,
    storage: ProductStorage = Depends(get_storage),
) -> TestCaseStep:
    step = storage.get_test_step(step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test step not found.")
    
    fields = body.model_dump(exclude_none=True)
    updated = storage.update_test_step(step_id, fields)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test step not found.")
    return TestCaseStep(**updated)


# ── DELETE /test-steps/{step_id} ─────────────────────────────────────────────

@router.delete("/test-steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_step(
    step_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> None:
    step = storage.get_test_step(step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test step not found.")
    storage.delete_test_step(step_id)


# ── POST /test-cases/{case_id}/steps/reorder ─────────────────────────────────

@router.post("/test-cases/{case_id}/steps/reorder", status_code=status.HTTP_200_OK)
def reorder_test_steps(
    case_id: str,
    body: StepReorderRequest,
    storage: ProductStorage = Depends(get_storage),
) -> dict:
    case = storage.get_test_case(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found.")
    storage.reorder_test_steps(case_id, body.step_ids)
    return {"status": "ok"}


# ── POST /validation-packs/{pack_id}/test-plan/generate-ai ───────────────────

@router.post("/validation-packs/{pack_id}/test-plan/generate-ai", response_model=AITestPlanPreview)
def generate_ai_test_plan(
    pack_id: str,
    body: TestPlanGenerateRequest = TestPlanGenerateRequest(),
    storage: ProductStorage = Depends(get_storage),
) -> AITestPlanPreview:
    """
    Generate proposed test cases using AI (ollama) or fallback.
    Returns preview only. Does not persist.
    """
    _get_pack_or_404(pack_id, storage)
    from qa_ai.ai.test_plan_generator import AITestPlanGenerator
    generator = AITestPlanGenerator(storage)
    return generator.generate_preview(pack_id, app_id=body.app_id)


# ── POST /validation-packs/{pack_id}/test-plan/accept-ai ─────────────────────

@router.post("/validation-packs/{pack_id}/test-plan/accept-ai", response_model=List[TestCase])
def accept_ai_test_plan(
    pack_id: str,
    body: AITestPlanAcceptRequest,
    storage: ProductStorage = Depends(get_storage),
) -> List[TestCase]:
    """
    Accept and persist selected AI-generated test cases and steps.
    Preserves confidence and rationale.
    Validates actions and handles duplicate/idempotent requests.
    """
    pack_row = _get_pack_or_404(pack_id, storage)
    plan_row = storage.get_test_plan_for_pack(pack_id)

    # Force delete existing plan if requested
    if body.force and plan_row:
        storage.delete_test_plan_for_pack(pack_id)
        plan_row = None

    if plan_row is None:
        from qa_ai.product_backend.models import _new_id, _now_iso
        now = _now_iso()
        plan_row = {
            "plan_id": _new_id(),
            "pack_id": pack_id,
            "app_id": pack_row.get("app_id"),
            "generated_from": "ai_generation",
            "coverage_summary": {},
            "risk_summary": {},
            "created_at": now,
            "updated_at": now,
        }
        storage.create_test_plan(plan_row)

    from qa_ai.product_backend.models import _new_id, _now_iso
    now = _now_iso()
    persisted_cases = []

    for tc in body.test_cases:
        # 1. Validate action types
        for step in tc.test_steps:
            if step.action_type not in SUPPORTED_TEST_STEP_ACTIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported action type: {step.action_type}"
                )

        # 2. Check duplicate / idempotency
        tc_id = tc.test_case_id or _new_id()
        existing_tc = storage.get_test_case(tc_id)
        if existing_tc:
            # Idempotency: skip if already exists, but retrieve and return
            persisted_cases.append(TestCase(**existing_tc))
            continue

        # 3. Create Case
        case_data = {
            "test_case_id": tc_id,
            "plan_id": plan_row["plan_id"],
            "pack_id": pack_id,
            "app_id": pack_row.get("app_id"),
            "flow_name": tc.flow_name,
            "title": tc.title,
            "description": tc.description,
            "test_type": tc.test_type,
            "priority": tc.priority,
            "risk_level": tc.risk_level,
            "preconditions": tc.preconditions,
            "steps": tc.steps,
            "expected_result": tc.expected_result,
            "expected_evidence": tc.expected_evidence,
            "pass_criteria": tc.pass_criteria,
            "fail_criteria": tc.fail_criteria,
            "automation_status": tc.automation_status,
            "safety_level": tc.safety_level,
            "requires_permission": tc.requires_permission,
            "tags": tc.tags,
            "enabled": tc.enabled,
            "confidence": tc.confidence,
            "rationale": tc.rationale,
            "generated_by": "ai",
            "generation_source": "ollama",
            "generation_metadata": {},
            "created_at": now,
            "updated_at": now,
        }

        storage.create_test_case(case_data)

        # 4. Create Steps
        for idx, step in enumerate(tc.test_steps):
            step_id = step.step_id or _new_id()
            step_data = {
                "step_id": step_id,
                "case_id": tc_id,
                "step_order": idx,
                "action_type": step.action_type,
                "target": step.target,
                "value": step.value,
                "expected": step.expected,
                "timeout_ms": step.timeout_ms,
                "optional": step.optional,
                "notes": step.notes,
                "method": step.method,
                "url": step.url,
                "headers": step.headers,
                "query_params": step.query_params,
                "body_json": step.body_json,
                "expected_status": step.expected_status,
                "expected_json_path": step.expected_json_path,
                "expected_value": step.expected_value,
                "budget_ms": step.budget_ms,
                "warn_ms": step.warn_ms,
                "metric_name": step.metric_name,
                "confidence": step.confidence,
                "rationale": step.rationale,
                "generated_by": "ai",
                "generation_source": "ollama",
                "generation_metadata": {},
                "created_at": now,
                "updated_at": now,
            }
            storage.create_test_step(step_data)

        # Retrieve fully populated TestCase model
        full_tc = storage.get_test_case(tc_id)
        if full_tc:
            persisted_cases.append(TestCase(**full_tc))

    return persisted_cases
