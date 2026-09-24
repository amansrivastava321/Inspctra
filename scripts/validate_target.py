#!/usr/bin/env python
"""
validate_target.py - Run QA-AI against any external target path.

Usage:
    python scripts/validate_target.py PATH [--profile PROFILE] [--name NAME]
                                           [--output OUTPUT_DIR]

Examples:
    python scripts/validate_target.py /path/to/my-project
    python scripts/validate_target.py /path/to/my-api --profile api --name my_api_v2
    python scripts/validate_target.py . --profile full_stack --output /tmp/qa_reports
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qa_ai.validation.harness import ValidationHarness, ValidationTarget
from qa_ai.validation.report_builder import ValidationReportBuilder


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run QA-AI validation against any target directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("path", help="Path to the target project/directory to audit")
    parser.add_argument("--profile", default="api",
                        choices=["api", "web", "flutter", "full_stack"],
                        help="Audit profile to use (default: api)")
    parser.add_argument("--name", default=None,
                        help="Display name for the target (default: folder name)")
    parser.add_argument("--output", default="validation_runs",
                        help="Root directory for validation output (default: validation_runs/)")
    args = parser.parse_args()

    target_path = Path(args.path).expanduser().resolve()
    if not target_path.exists():
        print(f"[validate_target] ERROR: Target path does not exist: {target_path}")
        sys.exit(1)

    name = args.name or target_path.name or "target"
    target = ValidationTarget(
        name=name,
        path=str(target_path),
        profile=args.profile,
        description=f"External target: {target_path}",
    )

    output_root = Path(args.output)
    harness = ValidationHarness(validation_root=output_root)

    print(f"[validate_target] Auditing: {target_path}")
    print(f"[validate_target] Profile:  {target.profile}")
    print(f"[validate_target] Name:     {target.name}")

    run = harness.run(target)

    status_icon = "✓" if run.status == "completed" else "✗"
    print(f"\n[validate_target] {status_icon} Status:   {run.status}")
    print(f"[validate_target]   Findings: {run.finding_count}")
    print(f"[validate_target]   Evidence: {run.evidence_count} items")
    print(f"[validate_target]   Duration: {run.duration_seconds:.1f}s")
    if run.errors:
        print(f"[validate_target]   Errors:   {run.errors}")

    builder = ValidationReportBuilder(output_dir=output_root)
    session_id = f"target_{name}"
    session_dir = builder.build([run], session_id=session_id)

    print(f"\n[validate_target] Reports written to: {session_dir}/")
    print(f"  Open in browser: {session_dir / 'validation_report.html'}")
    print(f"\nFiles:")
    for fname in sorted(session_dir.iterdir()):
        print(f"  {fname.name}")


if __name__ == "__main__":
    main()
