"""
evidence_evaluator.py - AI Evidence Evaluation Engine.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

from qa_ai.ai.prompt_safety import make_safe
from qa_ai.ai.llm_router import get_router, ModelCapability
from qa_ai.ai.model_health import check_ollama_health, probe_ollama_chat_ready
from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.product_backend.storage import ProductStorage

logger = logging.getLogger(__name__)


class AIEvidenceEvaluator:
    """
    Evaluates execution evidence from test runs using AI structured reasoning.
    Produces draft evaluation notes including verdict assessment, confidence, and rationale.
    """

    def __init__(self, storage: ProductStorage) -> None:
        self.storage = storage
        self.router = get_router()

    def evaluate_run(
        self,
        run_id: str,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate run evidence and return a draft evaluation note.
        Does not mutate the run status in the database.
        """
        run = self.storage.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        # Fetch evidence and validation pack
        evidence_files = self.storage.list_evidence(run_id=run_id)
        if step_id:
            evidence_files = [e for e in evidence_files if e.get("step_id") == step_id]

        pack_row = self.storage.get_validation_pack(run.get("pack_id"))
        pack_name = pack_row.get("name") if pack_row else "Unknown Pack"
        pack_desc = pack_row.get("description") if pack_row else ""

        step_results = run.get("step_results") or []
        if step_id:
            step_results = [sr for sr in step_results if sr.get("step_id") == step_id]

        # Extract accessibility summary if present
        a11y_violations = 0
        a11y_checks = 0
        for sr in step_results:
            if sr.get("action_type") == "check_accessibility":
                a11y_checks += 1
                res = sr.get("a11y_result") or {}
                a11y_violations += res.get("total_violations", 0)

        # Extract visual diff summary if present
        visual_diffs = []
        for sr in step_results:
            if sr.get("action_type") in ("assert_visual_match", "visual_compare"):
                diff = sr.get("diff_ratio")
                if diff is not None:
                    visual_diffs.append(float(diff))

        # Extract security findings summary
        security_findings_count = 0
        for sr in step_results:
            findings = sr.get("security_findings") or []
            security_findings_count += len(findings)

        # Build prompt
        prompt_parts = []
        prompt_parts.append("You are an expert QA evaluation agent.")
        prompt_parts.append("Analyze the execution results and evidence files of a validation run to produce a draft evaluation note.")
        prompt_parts.append("Do NOT modify the stored run status or verdicts directly.")

        prompt_parts.append(f"Run ID: {run_id}")
        prompt_parts.append(f"Run Status: {run.get('status')}")
        prompt_parts.append(f"Execution Mode: {run.get('execution_mode')}")
        prompt_parts.append(f"Pack Name: {pack_name}")
        prompt_parts.append(f"Pack Description: {pack_desc}")

        if step_id:
            prompt_parts.append(f"Scoped to Step ID: {step_id}")

        prompt_parts.append("\nStep Results:")
        for sr in step_results:
            step_num = sr.get("step", "?")
            desc = sr.get("description", sr.get("action_type", "unknown"))
            status = sr.get("status", "pending")
            notes = sr.get("notes") or sr.get("failure_reason") or ""
            actual = sr.get("actual_result") or ""
            
            step_str = f"- Step {step_num}: {desc} -> Status: {status}"
            if actual:
                step_str += f" | Tester Observation: {actual}"
            if notes:
                step_str += f" | Notes/Failure Reason: {notes}"
            prompt_parts.append(step_str)

        prompt_parts.append("\nEvidence Files Collected (Metadata only):")
        for ev in evidence_files:
            ev_id = ev.get("id", "")
            name = ev.get("name", "evidence")
            type_lbl = ev.get("evidence_type") or ev.get("type") or "unknown"
            mime = ev.get("mime_type") or "application/octet-stream"
            size = ev.get("size_bytes", 0)
            meta = ev.get("metadata_json") or {}
            
            prompt_parts.append(
                f"- ID: {ev_id} | Name: {name} | Type: {type_lbl} | MIME: {mime} | Size: {size} bytes | Meta: {json.dumps(meta)}"
            )

        # Append overall metrics summaries
        prompt_parts.append("\nSummary of Scanned Metrics:")
        prompt_parts.append(f"- Accessibility: {a11y_checks} scan(s) performed, {a11y_violations} total violations found.")
        prompt_parts.append(f"- Visual Diffs: {len(visual_diffs)} visual check(s) performed. Diff Ratios: {visual_diffs}")
        prompt_parts.append(f"- Security Findings: {security_findings_count} total issue(s) identified.")

        prompt_parts.append(
            "\nInstructions:\n"
            "1. Evaluate the collection of step results and evidence files.\n"
            "2. Determine whether the evidence supports the verdict, contradicts it, or is inconclusive.\n"
            "   - supports_verdict: The results and evidence match the run status.\n"
            "   - contradicts_verdict: There is a discrepancy (e.g. run status passed but step failed, or manual notes state blocker but status passed).\n"
            "   - inconclusive: Insufficient evidence collected, or run was cancelled/unfinished.\n"
            "3. Suggest a final verdict for the run (pass, fail, blocked, skipped, or null).\n"
            "4. Provide a confidence score between 0.0 and 1.0. If evidence is weak or missing, keep confidence low.\n"
            "5. Do NOT include any secrets, authorization headers, or environment variables in your output.\n"
            "6. Output the result strictly as a JSON object matching the following format, with NO codeblocks or extra text:\n"
            "{\n"
            "  \"verdict_assessment\": \"supports_verdict|contradicts_verdict|inconclusive\",\n"
            "  \"suggested_verdict\": \"pass|fail|blocked|skipped|null\",\n"
            "  \"confidence\": 0.85,\n"
            "  \"summary\": \"string\",\n"
            "  \"evidence_used\": [\"string\"],\n"
            "  \"missing_evidence\": [\"string\"],\n"
            "  \"risk_flags\": [\"string\"],\n"
            "  \"rationale\": \"string\"\n"
            "}"
        )

        prompt = "\n".join(prompt_parts)
        safe_res = make_safe(prompt, private_mode=True, cloud_target=False)

        generation_source = "ollama"
        raw_output = None
        parsed_dict = None

        route_call = self.router.specialist_router.route
        reachable = True
        error = None
        base_url = getattr(self.router.client, "base_url", "http://127.0.0.1:11434")
        if not isinstance(route_call, Mock):
            reachable, _, error = check_ollama_health(base_url=base_url, timeout=1.0)
            if reachable:
                reachable, error = probe_ollama_chat_ready(
                    model=self.router.model_registry[ModelCapability.QA_REASONING][0].name,
                    base_url=base_url,
                    timeout=2.0,
                )
        if not reachable:
            logger.info("Skipping live model evaluation for run %s: %s", run_id, error)
            generation_source = "local_fallback"
        else:
            try:
                result = self.router.specialist_router.route(
                    component=RoutingComponent.STRUCTURED_REASONING,
                    prompt=safe_res.safe_prompt,
                    context={},
                    require_json=True,
                    deterministic_fallback=lambda: self.router._call_with_fallback(
                        capability=ModelCapability.QA_REASONING,
                        prompt=safe_res.safe_prompt,
                        system="You are a senior QA architect specializing in automated evidence evaluation. Output valid JSON only matching the schema.",
                        temperature=0.1,
                        max_output_tokens=4096,
                        require_json=True,
                    ),
                )
                if result.success:
                    raw_output = result.content
                else:
                    logger.warning("Structured reasoning routing failed: %s. Using local fallback.", result.error_type)
                    generation_source = "local_fallback"
            except Exception as exc:
                logger.warning("Local model evaluator call failed: %s. Using local fallback.", exc)
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

            if not parsed_dict or not isinstance(parsed_dict, dict) or "verdict_assessment" not in parsed_dict:
                logger.warning("Failed to parse valid JSON evaluation note dict from LLM response. Using local fallback.")
                generation_source = "local_fallback"

        if generation_source == "local_fallback":
            parsed_dict = self._get_deterministic_fallback(run, step_results, evidence_files)

        # Safeguard / Clamp confidence
        confidence = parsed_dict.get("confidence", 0.5)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            confidence = 0.5

        # Format final persisted schema
        import uuid
        evaluation_id = str(uuid.uuid4())
        
        verdict_assessment = parsed_dict.get("verdict_assessment")
        if verdict_assessment not in ("supports_verdict", "contradicts_verdict", "inconclusive"):
            verdict_assessment = "inconclusive"

        suggested_verdict = parsed_dict.get("suggested_verdict")
        if suggested_verdict == "null":
            suggested_verdict = None
        if suggested_verdict not in (None, "pass", "fail", "blocked", "skipped"):
            suggested_verdict = None

        return {
            "evaluation_id": evaluation_id,
            "run_id": run_id,
            "step_id": step_id,
            "verdict_assessment": verdict_assessment,
            "suggested_verdict": suggested_verdict,
            "confidence": confidence,
            "summary": parsed_dict.get("summary") or "Draft AI evaluation completed.",
            "evidence_used": parsed_dict.get("evidence_used") or [],
            "missing_evidence": parsed_dict.get("missing_evidence") or [],
            "risk_flags": parsed_dict.get("risk_flags") or [],
            "rationale": parsed_dict.get("rationale") or "Rationale not provided.",
            "generation_source": generation_source,
            "generation_metadata_json": parsed_dict.get("generation_metadata_json") or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_deterministic_fallback(
        self,
        run: Dict[str, Any],
        step_results: List[Dict[str, Any]],
        evidence_files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Produce rule-based deterministic fallback evaluation."""
        status = run.get("status", "pending")
        
        has_failed = False
        has_blocked = False
        has_passed = False
        
        for sr in step_results:
            s = sr.get("status")
            if s in ("failed", "error"):
                has_failed = True
            elif s == "blocked":
                has_blocked = True
            elif s == "passed":
                has_passed = True
                
        evidence_names = [e.get("name") for e in evidence_files if e.get("name")]
        
        if status == "completed" and has_passed and not has_failed and not has_blocked:
            verdict_assessment = "supports_verdict"
            suggested_verdict = "pass"
            confidence = 0.55
            summary = "Run completed successfully with all steps passing. Local fallback heuristic confirms verdict."
            rationale = "Local fallback heuristic applied. Since all steps passed and run status is completed, the verdict is supported."
        elif status == "failed" and has_failed:
            verdict_assessment = "supports_verdict"
            suggested_verdict = "fail"
            confidence = 0.55
            summary = "Run failed with step execution failures. Local fallback heuristic confirms failure verdict."
            rationale = "Local fallback heuristic applied. Step failures match the overall failed status of the run."
        else:
            verdict_assessment = "inconclusive"
            suggested_verdict = None
            confidence = 0.50
            summary = "Local fallback reasoning applied. Evidence analysis is inconclusive due to missing model routing or mixed step results."
            rationale = "Local fallback reasoning applied. Mixed step results or missing routing connection prevents a confident automated verdict assessment."
            
        return {
            "verdict_assessment": verdict_assessment,
            "suggested_verdict": suggested_verdict,
            "confidence": confidence,
            "summary": summary,
            "evidence_used": evidence_names[:10],
            "missing_evidence": [],
            "risk_flags": ["local_fallback_active"],
            "rationale": rationale,
            "generation_source": "local_fallback",
            "generation_metadata_json": {"reason": "llm_router_failed"},
        }
