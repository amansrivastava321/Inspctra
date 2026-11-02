"""
pack_steps.py - turn a validation pack into the step list a run executes.

Shared by the manual "start run" endpoint and the scheduler so a scheduled run executes exactly the
same steps (and carries the same fields) as one started by hand.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


def build_pack_steps(
    pack_row: Dict[str, Any],
    cases: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Optional[str]]]:
    """
    Return (steps, case_ids) for a pack.

    `case_ids[i]` is the test case that step i belongs to (None when the pack has no enabled cases and
    its stored steps are used), so continuous runs can keep one browser session per test case.
    """
    enabled_cases = [c for c in cases if c.get("enabled")]
    if not enabled_cases:
        return list(pack_row.get("steps") or []), []

    steps: List[Dict[str, Any]] = []
    case_ids: List[Optional[str]] = []
    for case in enabled_cases:
        test_steps = sorted(case.get("test_steps") or [], key=lambda s: s.get("step_order", 0))
        for t_step in test_steps:
            target_label = t_step.get("url") or t_step.get("target") or ""
            method = t_step.get("method")
            action_type = t_step.get("action_type")
            steps.append({
                "step_id": t_step.get("step_id", ""),
                "action_type": action_type,
                "target": t_step.get("target"),
                "value": t_step.get("value"),
                "expected": t_step.get("expected"),
                "input_value": t_step.get("value") or t_step.get("expected") or "",
                "timeout_seconds": (t_step.get("timeout_ms") or 30000) / 1000,
                "optional": bool(t_step.get("optional")),
                "method": method,
                "url": t_step.get("url"),
                "headers": t_step.get("headers") or {},
                "query_params": t_step.get("query_params") or {},
                "body_json": t_step.get("body_json"),
                "expected_status": t_step.get("expected_status"),
                "expected_json_path": t_step.get("expected_json_path"),
                "expected_value": t_step.get("expected_value"),
                "budget_ms": t_step.get("budget_ms"),
                "warn_ms": t_step.get("warn_ms"),
                "metric_name": t_step.get("metric_name"),
                "description": f"[{case.get('title') or 'Case'}] {method + ' ' if method else ''}{action_type} {target_label}".strip(),
            })
            case_ids.append(case.get("test_case_id"))
    return steps, case_ids
