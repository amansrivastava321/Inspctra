"""
harness.py - Drives AuditCommand against a target and captures structured results.

ValidationHarness is the entry point for all validation runs. It:
1. Creates an isolated output directory under validation_runs/<run_id>/
2. Invokes AuditCommand.run() with dry_run=True (no mutations)
3. Records timing, phase outcomes, and artifact inventory
4. Returns a ValidationRun dataclass for downstream analysis
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Root for all validation outputs
_DEFAULT_VALIDATION_ROOT = Path("validation_runs")


@dataclass
class ValidationTarget:
    """Describes a single target to validate against."""
    name: str
    path: str
    profile: str
    description: str = ""


@dataclass
class ValidationRun:
    """Captures everything produced by one validation run."""
    run_id: str
    target: ValidationTarget
    started_at: str
    completed_at: str
    duration_seconds: float
    output_dir: str
    status: str                          # "completed" | "failed" | "error"
    phases_executed: List[str] = field(default_factory=list)
    phases_attempted: int = 0
    phases_completed: int = 0
    finding_count: int = 0
    evidence_count: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    raw_summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "target": {
                "name": self.target.name,
                "path": self.target.path,
                "profile": self.target.profile,
                "description": self.target.description,
            },
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "output_dir": self.output_dir,
            "status": self.status,
            "phases_executed": self.phases_executed,
            "phases_attempted": self.phases_attempted,
            "phases_completed": self.phases_completed,
            "finding_count": self.finding_count,
            "evidence_count": self.evidence_count,
            "errors": self.errors,
            "warnings": self.warnings,
            "artifacts": self.artifacts,
        }


class ValidationHarness:
    """
    Runs AuditCommand against a target and returns a ValidationRun.

    Always runs with dry_run=True so no files are modified on the target.
    Each run gets its own subdirectory: validation_runs/<run_id>/
    """

    def __init__(
        self,
        validation_root: Optional[Path] = None,
        config_dir: Optional[Path] = None,
    ):
        self.validation_root = Path(validation_root or _DEFAULT_VALIDATION_ROOT)
        self.config_dir = Path(config_dir or "qa_ai/config")

    def run(self, target: ValidationTarget) -> ValidationRun:
        """Execute a validation run against a single target."""
        run_id = f"val_{uuid.uuid4().hex[:12]}"
        output_dir = self.validation_root / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()

        logger.info("Validation run %s starting: target=%s profile=%s",
                    run_id, target.name, target.profile)

        try:
            from qa_ai.cli.audit_command import AuditCommand
            from qa_ai.cli.profile_manager import ProfileManager

            pm = ProfileManager(self.config_dir)
            cmd = AuditCommand(profile_manager=pm)

            summary = cmd.run(
                target_path=target.path,
                profile=target.profile,
                output_dir=str(output_dir),
                dry_run=True,
            )

            duration = time.perf_counter() - t0
            completed_at = datetime.now(timezone.utc).isoformat()

            phases_executed = summary.get("phases_executed", [])
            errors = summary.get("errors", [])
            warnings = summary.get("warnings", [])
            status = summary.get("status", "completed")

            finding_count, evidence_count = self._count_findings_evidence(output_dir)
            artifacts = self._list_artifacts(output_dir)
            phases_completed = self._count_completed_phases(output_dir, phases_executed)

            run = ValidationRun(
                run_id=run_id,
                target=target,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=round(duration, 2),
                output_dir=str(output_dir),
                status=status if not errors else "failed",
                phases_executed=phases_executed,
                phases_attempted=len(phases_executed),
                phases_completed=phases_completed,
                finding_count=finding_count,
                evidence_count=evidence_count,
                errors=errors,
                warnings=warnings,
                raw_summary=summary,
                artifacts=artifacts,
            )

        except Exception as exc:
            duration = time.perf_counter() - t0
            completed_at = datetime.now(timezone.utc).isoformat()
            logger.error("Validation run %s failed: %s", run_id, exc)
            run = ValidationRun(
                run_id=run_id,
                target=target,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=round(duration, 2),
                output_dir=str(output_dir),
                status="error",
                errors=[str(exc)],
            )

        # Save run manifest
        manifest_path = output_dir / "validation_run.json"
        manifest_path.write_text(
            json.dumps(run.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

        logger.info(
            "Validation run %s done: status=%s findings=%d duration=%.1fs",
            run_id, run.status, run.finding_count, run.duration_seconds,
        )
        return run

    def run_all(self, targets: List[ValidationTarget]) -> List[ValidationRun]:
        """Run validation against multiple targets sequentially."""
        runs: List[ValidationRun] = []
        for target in targets:
            runs.append(self.run(target))
        return runs

    # ------------------------------------------------------------------ helpers

    def _count_findings_evidence(self, output_dir: Path) -> tuple[int, int]:
        """Count findings and evidence items from artifact files."""
        findings_count = 0
        evidence_count = 0
        for json_file in output_dir.rglob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    # findings artifact
                    if "findings" in data and isinstance(data["findings"], list):
                        findings_count += len(data["findings"])
                        for f in data["findings"]:
                            if isinstance(f, dict):
                                evidence_count += len(f.get("evidence", []))
                    # evidence artifact
                    if "evidence_items" in data and isinstance(data["evidence_items"], list):
                        evidence_count += len(data["evidence_items"])
            except Exception as e:
                logger.debug("Could not parse %s: %s", json_file, e)
        return findings_count, evidence_count

    def _list_artifacts(self, output_dir: Path) -> List[str]:
        """Return relative paths of all artifact files."""
        return [
            str(p.relative_to(output_dir))
            for p in output_dir.rglob("*")
            if p.is_file() and p.name != "validation_run.json"
        ]

    def _count_completed_phases(
        self, output_dir: Path, phases_executed: List[str]
    ) -> int:
        """Estimate completed phases by counting phase-specific artifacts."""
        if not phases_executed:
            return 0
        artifact_names = {p.stem.lower() for p in output_dir.rglob("*.json")}
        completed = 0
        for phase in phases_executed:
            phase_key = phase.lower().replace("workflowphase.", "")
            if any(phase_key in name for name in artifact_names):
                completed += 1
        return max(completed, min(1, len(phases_executed)))
