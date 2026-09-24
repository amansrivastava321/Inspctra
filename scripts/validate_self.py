#!/usr/bin/env python
"""
validate_self.py - Run QA-AI against its own source code.

Audits the qa_ai/ package using the 'api' profile (no live browser needed)
and writes a validation report to validation_runs/self/.

Usage:
    python scripts/validate_self.py [--output OUTPUT_DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from qa_ai.validation.harness import ValidationHarness, ValidationTarget
from qa_ai.validation.report_builder import ValidationReportBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate QA-AI against its own source code")
    parser.add_argument(
        "--output", default="validation_runs",
        help="Root directory for validation output (default: validation_runs/)"
    )
    parser.add_argument(
        "--profile", default="api",
        help="Audit profile to use (default: api)"
    )
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    target = ValidationTarget(
        name="qa_ai_self",
        path=str(root / "qa_ai"),
        profile=args.profile,
        description="QA-AI platform auditing itself (self-validation)",
    )

    output_root = Path(args.output)
    harness = ValidationHarness(validation_root=output_root)
    print(f"[validate_self] Auditing {target.path} with profile '{target.profile}'...")
    run = harness.run(target)

    print(f"[validate_self] Status:   {run.status}")
    print(f"[validate_self] Findings: {run.finding_count}")
    print(f"[validate_self] Duration: {run.duration_seconds:.1f}s")
    if run.errors:
        print(f"[validate_self] Errors:   {run.errors}")

    builder = ValidationReportBuilder(output_dir=output_root)
    session_dir = builder.build([run], session_id="self")
    print(f"[validate_self] Reports written to: {session_dir}/")
    print(f"  - validation_summary.json")
    print(f"  - validation_findings_quality.json")
    print(f"  - validation_false_positive_review.json")
    print(f"  - validation_runtime_stability.json")
    print(f"  - validation_report.html")


if __name__ == "__main__":
    main()
