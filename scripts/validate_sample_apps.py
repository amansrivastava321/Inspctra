#!/usr/bin/env python
"""
validate_sample_apps.py - Run QA-AI against all bundled sample applications.

Audits every subdirectory under sample_apps/ using the most appropriate
profile for each app type, then writes a combined validation report.

Profile mapping (by folder name heuristics):
  *flutter*      -> flutter
  *react*        -> web
  *fastapi*      -> api
  *ecommerce*    -> full_stack
  *             -> api   (safe default)

Usage:
    python scripts/validate_sample_apps.py [--output OUTPUT_DIR] [--profile PROFILE]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qa_ai.validation.harness import ValidationHarness, ValidationTarget
from qa_ai.validation.report_builder import ValidationReportBuilder


_PROFILE_MAP = {
    "flutter": "flutter",
    "react": "web",
    "fastapi": "api",
    "ecommerce": "full_stack",
    "web": "web",
    "api": "api",
}


def _guess_profile(folder_name: str) -> str:
    lower = folder_name.lower()
    for keyword, profile in _PROFILE_MAP.items():
        if keyword in lower:
            return profile
    return "api"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate QA-AI against all sample apps")
    parser.add_argument("--output", default="validation_runs",
                        help="Root output directory (default: validation_runs/)")
    parser.add_argument("--profile", default=None,
                        help="Override profile for all targets (default: auto-detect)")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    sample_root = root / "sample_apps"

    if not sample_root.exists():
        print(f"[validate_sample_apps] ERROR: sample_apps/ not found at {sample_root}")
        sys.exit(1)

    app_dirs = sorted(d for d in sample_root.iterdir() if d.is_dir())
    if not app_dirs:
        print("[validate_sample_apps] No subdirectories found in sample_apps/")
        sys.exit(0)

    targets = [
        ValidationTarget(
            name=app_dir.name,
            path=str(app_dir),
            profile=args.profile or _guess_profile(app_dir.name),
            description=f"Sample application: {app_dir.name}",
        )
        for app_dir in app_dirs
    ]

    output_root = Path(args.output)
    harness = ValidationHarness(validation_root=output_root)

    print(f"[validate_sample_apps] Validating {len(targets)} sample apps...")
    for t in targets:
        print(f"  - {t.name} (profile: {t.profile})")

    runs = harness.run_all(targets)

    print(f"\n[validate_sample_apps] Results:")
    for run in runs:
        status_icon = "✓" if run.status == "completed" else "✗"
        print(f"  {status_icon} {run.target.name}: {run.status} "
              f"({run.finding_count} findings, {run.duration_seconds:.1f}s)")

    builder = ValidationReportBuilder(output_dir=output_root)
    session_dir = builder.build(runs, session_id="sample_apps")
    print(f"\n[validate_sample_apps] Reports written to: {session_dir}/")
    print(f"  - validation_summary.json")
    print(f"  - validation_findings_quality.json")
    print(f"  - validation_false_positive_review.json")
    print(f"  - validation_runtime_stability.json")
    print(f"  - validation_report.html")


if __name__ == "__main__":
    main()
