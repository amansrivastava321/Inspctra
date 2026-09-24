"""
runtime_doctor.py - GET /api/runtime-doctor

Wraps EnvironmentDoctor to expose environment readiness via API.
Read-only: no installs, no changes.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runtime-doctor"])


@router.get("/runtime-doctor")
def runtime_doctor(
    app_types: Optional[List[str]] = Query(
        default=None,
        description="Limit check to specific app types (e.g. web, android, ios)",
    ),
) -> Dict[str, Any]:
    """
    Run environment readiness check and return a full EnvironmentDoctorReport.

    This is a read-only diagnostic. No installs, no side effects.
    app_types: optional filter (e.g. ?app_types=web&app_types=android).
    """
    try:
        from qa_ai.interactive_runtime.setup.environment_doctor import EnvironmentDoctor
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=app_types or None)
        return report.model_dump()
    except ImportError as exc:
        logger.warning("runtime_doctor: EnvironmentDoctor not available: %s", exc)
        return {
            "error": "EnvironmentDoctor not available in this installation.",
            "readiness_score": 0,
            "readiness_label": "blocked",
            "missing_items": ["EnvironmentDoctor module not importable"],
            "recommended_actions": ["Check qa_ai.interactive_runtime.setup installation"],
        }
    except Exception as exc:
        logger.error("runtime_doctor: diagnosis failed: %s", exc)
        return {
            "error": f"Diagnosis failed: {exc}",
            "readiness_score": 0,
            "readiness_label": "error",
        }
