"""
qa_ai.validation - Real-world validation harness for the QA-AI platform.

Measures finding quality, false-positive rate, evidence completeness,
runtime stability, and report usefulness across real targets.
"""
from qa_ai.validation.harness import ValidationHarness, ValidationTarget, ValidationRun
from qa_ai.validation.report_builder import ValidationReportBuilder

__all__ = [
    "ValidationHarness",
    "ValidationTarget",
    "ValidationRun",
    "ValidationReportBuilder",
]
