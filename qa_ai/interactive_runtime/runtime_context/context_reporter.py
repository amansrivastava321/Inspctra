"""
context_reporter.py - Write runtime context JSON report artifacts.

Artifacts:
  runtime_test_context.json      — RuntimeTestContext (secret-free)
  runtime_capability_plan.json   — RuntimeCapabilityPlan
  context_verification_plan.json — last ContextVerificationPlan (or list)
  context_evidence.json          — list of ContextEvidenceBundle
  context_safety_policy.json     — safety decisions summary

Security:
- Never writes credential values (env var names are safe).
- Redacts any field containing 'password', 'token', 'secret', 'key' in value.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.runtime_context.context_models import (
    ContextEvidenceBundle,
    ContextVerificationPlan,
    RuntimeCapabilityPlan,
    RuntimeTestContext,
)

logger = logging.getLogger(__name__)

# Patterns to detect secret-like values in key=value strings
_SECRET_VALUE_RE = re.compile(
    r"(?i)(password|token|secret|api_key|bearer|auth_key)[=:]\S+"
)
# Dict keys that likely hold credential values
_SECRET_KEY_RE = re.compile(
    r"(?i)^(password|token|secret|api_key|bearer|auth_key|credential|access_key|private_key)$"
)


def _sanitize(data: Any) -> Any:
    """
    Recursively redact secret-like values from a dict before JSON dump.

    Two layers:
    1. Dict keys matching credential patterns → redact the value.
    2. String values containing 'key=value' credential patterns → redact inline.
    """
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if isinstance(k, str) and _SECRET_KEY_RE.match(k):
                result[k] = "[REDACTED]"
            else:
                result[k] = _sanitize(v)
        return result
    if isinstance(data, list):
        return [_sanitize(item) for item in data]
    if isinstance(data, str):
        return _SECRET_VALUE_RE.sub(r"\1=[REDACTED]", data)
    return data


class ContextReporter:
    """Write runtime context artifacts to the output directory."""

    def __init__(self, output_dir: str = "artifacts"):
        self._out = Path(output_dir)
        self._out.mkdir(parents=True, exist_ok=True)

    def write_context(self, ctx: RuntimeTestContext) -> None:
        """Write runtime_test_context.json."""
        self._write("runtime_test_context.json", _sanitize(ctx.model_dump()))

    def write_capability_plan(self, plan: RuntimeCapabilityPlan) -> None:
        """Write runtime_capability_plan.json."""
        self._write("runtime_capability_plan.json", plan.model_dump())

    def write_verification_plan(self, vplan: ContextVerificationPlan) -> None:
        """Write context_verification_plan.json (last plan or a single plan)."""
        self._write("context_verification_plan.json", vplan.model_dump())

    def write_evidence_bundles(self, bundles: List[ContextEvidenceBundle]) -> None:
        """Write context_evidence.json with all step bundles (sanitized)."""
        # Sanitize each bundle: backend_health / database_snapshot may contain
        # API response bodies with credential values if the backend leaks them.
        self._write("context_evidence.json", [_sanitize(b.model_dump()) for b in bundles])

    def write_safety_summary(self, decisions: List[Dict[str, Any]]) -> None:
        """Write context_safety_policy.json with all safety decisions."""
        self._write("context_safety_policy.json", {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_decisions": len(decisions),
            "blocked_count": sum(1 for d in decisions if not d.get("allowed", True)),
            "decisions": decisions,
        })

    def _write(self, filename: str, data: Any) -> None:
        path = self._out / filename
        try:
            path.write_text(json.dumps(data, indent=2, default=str))
            logger.debug("ContextReporter: wrote %s", path)
        except Exception as exc:
            logger.warning("ContextReporter: failed to write %s: %s", filename, exc)
