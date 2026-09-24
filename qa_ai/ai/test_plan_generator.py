"""
test_plan_generator.py - AI Test Plan Generator.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

from qa_ai.ai.prompt_safety import make_safe
from qa_ai.ai.llm_router import get_router, ModelCapability
from qa_ai.ai.model_health import check_ollama_health, probe_ollama_chat_ready
from qa_ai.product_backend.models import (
    AITestPlanPreview,
    AIProposedTestCase,
    AIProposedTestStep,
    SUPPORTED_TEST_STEP_ACTIONS,
)
from qa_ai.product_backend.storage import ProductStorage
from qa_ai.product_backend.test_plan_service import generate_generic_test_plan

logger = logging.getLogger(__name__)


class AITestPlanGenerator:
    def __init__(self, storage: ProductStorage) -> None:
        self.storage = storage
        self.router = get_router()

    def generate_preview(
        self,
        pack_id: str,
        app_id: Optional[str] = None,
    ) -> AITestPlanPreview:
        pack_row = self.storage.get_validation_pack(pack_id)
        if not pack_row:
            raise ValueError(f"Validation pack {pack_id} not found")

        resolved_app_id = app_id or pack_row.get("app_id")
        app_type = None

        if not resolved_app_id:
            recent_runs = self.storage.list_runs(pack_id=pack_id, limit=1)
            if recent_runs:
                app_target_id = recent_runs[0].get("app_target_id")
                if app_target_id:
                    target = self.storage.get_app_target(app_target_id)
                    if target:
                        app_type = target.get("app_type")
                        resolved_app_id = target.get("id")

        if resolved_app_id and not app_type:
            target = self.storage.get_app_target(resolved_app_id)
            if target:
                app_type = target.get("app_type")

        app_target = None
        app_map = None
        if resolved_app_id:
            app_target = self.storage.get_app_target(resolved_app_id)
            app_map = self.storage.get_app_map_for_app(resolved_app_id)

        existing_cases = self.storage.list_test_cases(pack_id)

        # Build prompt
        prompt_parts = []
        prompt_parts.append("You are an expert QA automation agent.")
        prompt_parts.append("Generate a list of proposed test cases with detailed steps for a validation pack.")
        prompt_parts.append(f"App Type: {app_type or 'web'}")
        if app_target:
            prompt_parts.append(f"App Target Name: {app_target.get('name')}")
            prompt_parts.append(f"App Target Description: {app_target.get('description')}")
            prompt_parts.append(f"App Target Base URL: {app_target.get('base_url')}")
        if app_map:
            detected_stack = getattr(app_map, 'detected_stack', []) if hasattr(app_map, 'detected_stack') else app_map.get('detected_stack', []) if isinstance(app_map, dict) else []
            prompt_parts.append(f"Detected Stack: {', '.join(detected_stack)}")
            
            surfaces_obj = getattr(app_map, 'testable_surfaces', []) if hasattr(app_map, 'testable_surfaces') else app_map.get('testable_surfaces', []) if isinstance(app_map, dict) else []
            surfaces = [getattr(s, 'name', s.get('name', '')) if not isinstance(s, str) else s for s in surfaces_obj]
            prompt_parts.append(f"Testable Surfaces: {', '.join(surfaces)}")
            
            risks_obj = getattr(app_map, 'risk_areas', []) if hasattr(app_map, 'risk_areas') else app_map.get('risk_areas', []) if isinstance(app_map, dict) else []
            risks = []
            for r in risks_obj:
                if isinstance(r, dict):
                    risks.append(f"{r.get('label')} (Risk Level: {r.get('risk_level', 'medium')})")
                else:
                    risks.append(f"{getattr(r, 'label', '')} (Risk Level: {getattr(r, 'risk_level', 'medium')})")
            prompt_parts.append(f"Risk Areas: {'; '.join(risks)}")
            
            gaps_obj = getattr(app_map, 'capability_gaps', []) if hasattr(app_map, 'capability_gaps') else app_map.get('capability_gaps', []) if isinstance(app_map, dict) else []
            gaps = []
            for g in gaps_obj:
                if isinstance(g, dict):
                    gaps.append(f"{g.get('title')}: {g.get('description')}")
                else:
                    gaps.append(f"{getattr(g, 'title', '')}: {getattr(g, 'description', '')}")
            prompt_parts.append(f"Capability Gaps (what Inspectra cannot automatically check): {'; '.join(gaps)}")

        prompt_parts.append(f"Validation Pack Name: {pack_row.get('name')}")
        prompt_parts.append(f"Validation Pack Description: {pack_row.get('description')}")

        if existing_cases:
            existing_desc = [f"- {c.get('title')}: {c.get('description')}" for c in existing_cases]
            prompt_parts.append("Existing Test Cases in this Pack (Do NOT duplicate these):")
            prompt_parts.extend(existing_desc)

        prompt_parts.append("Supported Action Types:")
        prompt_parts.append(", ".join(SUPPORTED_TEST_STEP_ACTIONS))

        prompt_parts.append(
            "Instructions:\n"
            "1. Propose 3-5 new test cases that are relevant to this app type and target.\n"
            "2. Each test case must contain a list of structured test_steps.\n"
            "3. For each step, use one of the Supported Action Types. Do not invent any new action_types.\n"
            "4. For each test case and step, provide a confidence score between 0.0 and 1.0 and a brief rationale explaining why this test is valuable.\n"
            "5. Do not include any sensitive information, credentials, or actual secrets.\n"
            "6. Output the result strictly as a JSON object matching the following format, with NO codeblocks or extra text:\n"
            "{\n"
            "  \"test_cases\": [\n"
            "    {\n"
            "      \"flow_name\": \"string\",\n"
            "      \"title\": \"string\",\n"
            "      \"description\": \"string\",\n"
            "      \"test_type\": \"positive|negative|edge_case|regression|security|accessibility|performance|data_integrity\",\n"
            "      \"priority\": \"P0|P1|P2\",\n"
            "      \"risk_level\": \"critical|high|medium|low\",\n"
            "      \"preconditions\": [\"string\"],\n"
            "      \"steps\": [\"string\"],\n"
            "      \"expected_result\": \"string\",\n"
            "      \"expected_evidence\": [\"string\"],\n"
            "      \"pass_criteria\": \"string\",\n"
            "      \"fail_criteria\": \"string\",\n"
            "      \"automation_status\": \"ready|needs_selector|needs_credentials|needs_permission|blocked|manual_only|capability_gap\",\n"
            "      \"safety_level\": \"safe|caution|destructive|external_cost|real_user_impact\",\n"
            "      \"requires_permission\": false,\n"
            "      \"tags\": [\"string\"],\n"
            "      \"enabled\": true,\n"
            "      \"confidence\": 0.9,\n"
            "      \"rationale\": \"string\",\n"
            "      \"test_steps\": [\n"
            "        {\n"
            "          \"action_type\": \"click|type|navigate|...\",\n"
            "          \"target\": \"string or null\",\n"
            "          \"value\": \"string or null\",\n"
            "          \"expected\": \"string or null\",\n"
            "          \"timeout_ms\": 30000,\n"
            "          \"optional\": false,\n"
            "          \"notes\": \"string or null\",\n"
            "          \"confidence\": 0.95,\n"
            "          \"rationale\": \"string or null\",\n"
            "          \"method\": \"GET|POST|... or null\",\n"
            "          \"url\": \"string or null\",\n"
            "          \"headers\": {} or null,\n"
            "          \"query_params\": {} or null,\n"
            "          \"body_json\": null,\n"
            "          \"expected_status\": null,\n"
            "          \"expected_json_path\": null,\n"
            "          \"expected_value\": null\n"
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        prompt = "\n\n".join(prompt_parts)
        safe_res = make_safe(prompt, private_mode=True, cloud_target=False)

        generation_source = "ollama"
        raw_output = None
        parsed_dict = None

        generate_call = self.router.generate_test_plan
        reachable = True
        error = None
        base_url = getattr(self.router.client, "base_url", "http://127.0.0.1:11434")
        if not isinstance(generate_call, Mock):
            reachable, _, error = check_ollama_health(base_url=base_url, timeout=1.0)
            if reachable:
                reachable, error = probe_ollama_chat_ready(
                    model=self.router.model_registry[ModelCapability.QA_REASONING][0].name,
                    base_url=base_url,
                    timeout=2.0,
                )
        if not reachable:
            logger.info("Skipping live AI test plan generation for pack %s: %s", pack_id, error)
            generation_source = "local_fallback"
        else:
            try:
                raw_output = self.router.generate_test_plan(safe_res.safe_prompt)
            except Exception as exc:
                logger.warning("Local model router call failed: %s. Using local fallback.", exc)
                generation_source = "local_fallback"

        if generation_source == "ollama" and raw_output:
            parsed_dict = self.router._extract_json(raw_output)
            if not parsed_dict:
                try:
                    cleaned = raw_output.strip()
                    if cleaned.startswith("```"):
                        lines = cleaned.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        cleaned = "\n".join(lines).strip()
                    parsed_dict = json.loads(cleaned)
                except Exception:
                    pass

            if not parsed_dict or not isinstance(parsed_dict, dict) or "test_cases" not in parsed_dict:
                logger.warning("Failed to parse valid JSON test_cases dict from LLM response. Using local fallback.")
                generation_source = "local_fallback"

        if generation_source == "local_fallback":
            fallback_plan = generate_generic_test_plan(
                pack_id=pack_id,
                app_type=app_type,
                app_id=resolved_app_id,
                app_map=app_map,
            )
            test_cases: List[AIProposedTestCase] = []
            for tc in fallback_plan["test_cases"]:
                steps_str_list = tc.get("steps", [])
                ai_steps = []
                for idx, step_str in enumerate(steps_str_list):
                    action_type = "click"
                    target = ""
                    value = ""
                    expected = ""
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

                    if step_str in SUPPORTED_TEST_STEP_ACTIONS:
                        action_type = step_str
                        if action_type == "navigate":
                            target = "/"
                        elif action_type == "assert_title_contains":
                            value = "App"

                    ai_steps.append(AIProposedTestStep(
                        step_id=tc.get("step_id") or str(uuid.uuid4()),
                        action_type=action_type,
                        target=target or None,
                        value=value or None,
                        expected=expected or None,
                        timeout_ms=30000,
                        optional=False,
                        notes=notes,
                        confidence=0.5,
                        rationale="Local offline template fallback step.",
                    ))

                test_cases.append(AIProposedTestCase(
                    test_case_id=tc.get("test_case_id") or str(uuid.uuid4()),
                    flow_name=tc.get("flow_name", ""),
                    title=tc.get("title", ""),
                    description=tc.get("description", ""),
                    test_type=tc.get("test_type", "positive"),
                    priority=tc.get("priority", "P1"),
                    risk_level=tc.get("risk_level", "medium"),
                    preconditions=tc.get("preconditions", []),
                    steps=tc.get("steps", []),
                    expected_result=tc.get("expected_result", ""),
                    expected_evidence=tc.get("expected_evidence", []),
                    pass_criteria=tc.get("pass_criteria", ""),
                    fail_criteria=tc.get("fail_criteria", ""),
                    automation_status=tc.get("automation_status", "needs_selector"),
                    safety_level=tc.get("safety_level", "safe"),
                    requires_permission=tc.get("requires_permission", False),
                    tags=tc.get("tags", []),
                    enabled=tc.get("enabled", True),
                    confidence=0.5,
                    rationale="Local offline template fallback (no AI used).",
                    test_steps=ai_steps,
                ))
        else:
            test_cases = []
            for tc_data in parsed_dict.get("test_cases", []):
                case_conf = tc_data.get("confidence", 0.8)
                try:
                    case_conf = max(0.0, min(1.0, float(case_conf)))
                except (ValueError, TypeError):
                    case_conf = 0.8

                ai_steps = []
                for step_data in tc_data.get("test_steps", []):
                    action_type = step_data.get("action_type")
                    if action_type not in SUPPORTED_TEST_STEP_ACTIONS:
                        logger.warning("Filtering unsupported step action_type: %s", action_type)
                        continue

                    step_conf = step_data.get("confidence", 0.9)
                    try:
                        step_conf = max(0.0, min(1.0, float(step_conf)))
                    except (ValueError, TypeError):
                        step_conf = 0.9

                    ai_steps.append(AIProposedTestStep(
                        step_id=step_data.get("step_id") or str(uuid.uuid4()),
                        action_type=action_type,
                        target=step_data.get("target"),
                        value=step_data.get("value"),
                        expected=step_data.get("expected"),
                        timeout_ms=step_data.get("timeout_ms", 30000),
                        optional=bool(step_data.get("optional", False)),
                        notes=step_data.get("notes"),
                        confidence=step_conf,
                        rationale=step_data.get("rationale"),
                        method=step_data.get("method"),
                        url=step_data.get("url"),
                        headers=step_data.get("headers"),
                        query_params=step_data.get("query_params"),
                        body_json=step_data.get("body_json"),
                        expected_status=step_data.get("expected_status"),
                        expected_json_path=step_data.get("expected_json_path"),
                        expected_value=step_data.get("expected_value"),
                        budget_ms=step_data.get("budget_ms"),
                        warn_ms=step_data.get("warn_ms"),
                        metric_name=step_data.get("metric_name"),
                    ))

                preconditions = tc_data.get("preconditions")
                if not isinstance(preconditions, list):
                    preconditions = [preconditions] if preconditions else []
                steps = tc_data.get("steps")
                if not isinstance(steps, list):
                    steps = [steps] if steps else []
                expected_evidence = tc_data.get("expected_evidence")
                if not isinstance(expected_evidence, list):
                    expected_evidence = [expected_evidence] if expected_evidence else []
                tags = tc_data.get("tags")
                if not isinstance(tags, list):
                    tags = [tags] if tags else []

                test_cases.append(AIProposedTestCase(
                    test_case_id=tc_data.get("test_case_id") or str(uuid.uuid4()),
                    flow_name=tc_data.get("flow_name", ""),
                    title=tc_data.get("title") or "Unnamed AI Case",
                    description=tc_data.get("description", ""),
                    test_type=tc_data.get("test_type", "positive"),
                    priority=tc_data.get("priority", "P1"),
                    risk_level=tc_data.get("risk_level", "medium"),
                    preconditions=[str(x) for x in preconditions],
                    steps=[str(x) for x in steps],
                    expected_result=tc_data.get("expected_result", ""),
                    expected_evidence=[str(x) for x in expected_evidence],
                    pass_criteria=tc_data.get("pass_criteria", ""),
                    fail_criteria=tc_data.get("fail_criteria", ""),
                    automation_status=tc_data.get("automation_status", "needs_selector"),
                    safety_level=tc_data.get("safety_level", "safe"),
                    requires_permission=bool(tc_data.get("requires_permission", False)),
                    tags=[str(x) for x in tags],
                    enabled=bool(tc_data.get("enabled", True)),
                    confidence=case_conf,
                    rationale=tc_data.get("rationale") or "Generated by AI.",
                    test_steps=ai_steps,
                ))

        coverage: Dict[str, int] = {}
        for c in test_cases:
            t = c.test_type
            coverage[t] = coverage.get(t, 0) + 1

        risk: Dict[str, int] = {}
        for c in test_cases:
            r = c.risk_level
            risk[r] = risk.get(r, 0) + 1

        now = datetime.now(timezone.utc).isoformat()
        return AITestPlanPreview(
            pack_id=pack_id,
            app_id=resolved_app_id,
            generated_from="ai_generation",
            generation_source=generation_source,
            coverage_summary=coverage,
            risk_summary=risk,
            test_cases=test_cases,
            created_at=now,
            updated_at=now,
            safety_redaction_metadata={
                "redactions_applied": safe_res.redactions_applied,
                "risk_level": safe_res.risk_level,
                "private_content_detected": safe_res.private_content_detected,
            }
        )
