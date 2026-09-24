"""
execution_orchestrator.py - Coordinates test execution across runners.
Selects the appropriate runner for the platform, executes tests,
collects evidence, and produces aggregated results.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import os
import time
import logging

_DEFAULT_APP_URL = os.environ.get("QA_AI_APP_BASE_URL", "http://localhost:3000")
_DEFAULT_API_URL = os.environ.get("QA_AI_API_BASE_URL", "http://localhost:8000")

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime.execution_context import Platform
from qa_ai.runners.base_runner import BaseRunner
from qa_ai.runners.api_runner import APIRunner
from qa_ai.schemas.execution_result_schema import ExecutionResult
from qa_ai.schemas.finding_schema import (
    Finding,
    FindingSet,
    FindingSeverity,
    FindingCategory,
    FindingStatus,
    EvidenceRef,
)
from qa_ai.evidence.evidence_collector import EvidenceCollector
from qa_ai.evidence.evidence_registry import EvidenceRegistry

logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """
    Coordinates test execution across multiple runners.

    Responsibilities:
    1. Select the right runner(s) for the target platform
    2. Configure runners with base_url, credentials, etc.
    3. Execute test plan through the runner(s)
    4. Collect and index evidence
    5. Generate findings from failures
    6. Persist all results to the artifact store
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._runners: Dict[str, BaseRunner] = {}
        self._register_default_runners()

    def _register_default_runners(self) -> None:
        """Register built-in runners."""
        self._runners["api_runner"] = APIRunner
        try:
            from qa_ai.runners.playwright_runner import PlaywrightRunner
            self._runners["playwright_runner"] = PlaywrightRunner
        except ImportError:
            logger.debug("PlaywrightRunner not available (playwright not installed)")

    def register_runner(self, name: str, runner_class: type) -> None:
        """Register a custom runner."""
        self._runners[name] = runner_class

    def execute(
        self,
        test_plan: Dict[str, Any],
        platform: Platform,
        config: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute a test plan against the target platform.

        Args:
            test_plan: Test plan dict from test_plan.json
            platform: Target platform
            config: Runner configuration (base_url, headless, etc.)

        Returns:
            Aggregated ExecutionResult
        """
        config = config or {}
        started_at = time.time()

        logger.info(f"Execution orchestrator starting for platform: {platform.value}")

        # Select runner(s) based on platform
        runners = self._select_runners(platform, config)

        if not runners:
            logger.warning(f"No runners available for platform: {platform.value}")
            return ExecutionResult(
                metadata={"platform": platform.value, "error": "no_runners"},
                metadata_extra={"error": f"No runners available for {platform.value}"},
            )

        # Execute with each runner
        all_results: List[ExecutionResult] = []
        for runner_name, runner_instance in runners:
            logger.info(f"Running with {runner_name}")
            try:
                result = runner_instance.run(test_plan)
                all_results.append(result)

                # Save runner-specific results
                self.store.save_artifact(
                    f"execution_results_{runner_name}",
                    result.model_dump(),
                    agent=runner_name,
                )
            except Exception as e:
                logger.error(f"Runner {runner_name} failed: {e}")
                all_results.append(ExecutionResult(
                    errors=1,
                    metadata_extra={"runner": runner_name, "error": str(e)},
                ))

        # Aggregate results
        aggregated = self._aggregate(all_results)
        aggregated.metadata.runner = ",".join(rn for rn, _ in runners)

        # Generate findings from failures
        findings = self._generate_findings(aggregated, test_plan)
        if findings.findings:
            self.store.save_findings(
                findings.model_dump(),
                agent="ExecutionOrchestrator",
            )

        # Save aggregated results
        duration = time.time() - started_at
        aggregated.duration_seconds = duration
        aggregated.metadata.duration_seconds = duration
        aggregated.metadata.started_at = datetime.fromtimestamp(
            started_at, tz=timezone.utc
        ).isoformat()
        aggregated.metadata.completed_at = datetime.now(timezone.utc).isoformat()

        self.store.save_artifact(
            "execution_results",
            aggregated.model_dump(),
            agent="ExecutionOrchestrator",
        )

        logger.info(
            f"Execution complete: {aggregated.passed}/{aggregated.total_executed} passed, "
            f"{len(findings.findings)} findings, {duration:.1f}s"
        )

        return aggregated

    def _select_runners(
        self,
        platform: Platform,
        config: Dict[str, Any],
    ) -> List[tuple]:
        """Select appropriate runner(s) for the platform."""
        selected: List[tuple] = []

        if platform == Platform.WEB:
            if "playwright_runner" in self._runners:
                runner_cls = self._runners["playwright_runner"]
                runner_config = {
                    **config,
                    "base_url": config.get("base_url", config.get("app_url", _DEFAULT_APP_URL)),
                    "headless": config.get("headless", True),
                    "run_id": config.get("run_id", "pw-run"),
                }
                selected.append(("playwright_runner", runner_cls(runner_config)))

        if platform in (Platform.BACKEND, Platform.CLI, Platform.UNKNOWN):
            if "api_runner" in self._runners:
                runner_cls = self._runners["api_runner"]
                runner_config = {
                    **config,
                    "base_url": config.get("base_url", _DEFAULT_API_URL),
                    "run_id": config.get("run_id", "api-run"),
                }
                selected.append(("api_runner", runner_cls(runner_config)))

        # For web, also run API tests against the backend
        if platform == Platform.WEB and "api_runner" in self._runners:
            if not any(name == "api_runner" for name, _ in selected):
                runner_cls = self._runners["api_runner"]
                runner_config = {
                    **config,
                    "base_url": config.get("api_base_url", config.get("base_url", _DEFAULT_API_URL)),
                    "run_id": config.get("run_id", "api-run"),
                }
                selected.append(("api_runner", runner_cls(runner_config)))

        return selected

    def _aggregate(self, results: List[ExecutionResult]) -> ExecutionResult:
        """Aggregate results from multiple runners."""
        from qa_ai.schemas.execution_result_schema import ExecutionMetadata, SuiteResult

        if not results:
            return ExecutionResult()

        if len(results) == 1:
            return results[0]

        total_executed = sum(r.total_executed for r in results)
        total_passed = sum(r.passed for r in results)
        total_failed = sum(r.failed for r in results)
        total_skipped = sum(r.skipped for r in results)
        total_errors = sum(r.errors for r in results)

        all_suites: List[SuiteResult] = []
        for r in results:
            all_suites.extend(r.suites)

        all_env_issues: List[str] = []
        for r in results:
            all_env_issues.extend(r.environment_issues)

        return ExecutionResult(
            metadata=ExecutionMetadata(
                runner="orchestrated",
                started_at=results[0].metadata.started_at,
                completed_at=results[-1].metadata.completed_at,
            ),
            total_executed=total_executed,
            passed=total_passed,
            failed=total_failed,
            skipped=total_skipped,
            errors=total_errors,
            suites=all_suites,
            environment_issues=all_env_issues,
        )

    def _generate_findings(
        self,
        result: ExecutionResult,
        test_plan: Dict[str, Any],
    ) -> FindingSet:
        """Generate findings from test failures."""
        findings: List[Finding] = []

        # Build a lookup of test cases by id
        test_lookup: Dict[str, Dict[str, Any]] = {}
        for suite_tests in test_plan.get("test_suites", {}).values():
            for tc in suite_tests:
                test_lookup[tc.get("id", "")] = tc

        counter = 0
        for suite in result.suites:
            for test_result in suite.tests:
                if test_result.outcome in (TestOutcome.FAILED, TestOutcome.ERROR):
                    counter += 1
                    test_case = test_lookup.get(test_result.test_id, {})

                    severity = self._infer_severity(test_case, test_result)

                    findings.append(Finding(
                        id=f"F-{counter:04d}",
                        title=f"Test failed: {test_result.test_title}",
                        description=self._build_finding_description(test_result, test_case),
                        severity=severity,
                        category=self._infer_category(test_case),
                        status=FindingStatus.OPEN,
                        api_endpoint=test_case.get("target", {}).get("api"),
                        steps_to_reproduce=test_case.get("steps", []),
                        expected_behavior=test_case.get("expected_result", ""),
                        actual_behavior=test_result.error_message or str(test_result.outcome),
                        found_by_agent="ExecutionOrchestrator",
                        found_at=datetime.now(timezone.utc).isoformat(),
                        test_case_id=test_result.test_id,
                        evidence=[
                            EvidenceRef(
                                evidence_type="test_result",
                                filename=f"{test_result.test_id}",
                                description="Test execution result",
                            )
                        ],
                        tags=test_case.get("tags", []),
                        metadata=test_result.metadata,
                    ))

        return FindingSet(findings=findings)

    def _infer_severity(
        self,
        test_case: Dict[str, Any],
        test_result: Any,
    ) -> FindingSeverity:
        """Infer finding severity from test case priority and risk."""
        priority = test_case.get("priority", "P1")
        risk = test_case.get("risk", "medium")

        if priority == "P0" or risk in ("critical", "high"):
            return FindingSeverity.CRITICAL
        if priority == "P1" or risk == "medium":
            return FindingSeverity.HIGH
        return FindingSeverity.MEDIUM

    def _infer_category(self, test_case: Dict[str, Any]) -> FindingCategory:
        """Infer finding category from test type."""
        test_type = test_case.get("type", "functional")
        mapping = {
            "security": FindingCategory.SECURITY,
            "performance": FindingCategory.PERFORMANCE,
            "accessibility": FindingCategory.ACCESSIBILITY,
            "smoke": FindingCategory.BUG,
            "functional": FindingCategory.BUG,
            "negative": FindingCategory.BUG,
            "edge_case": FindingCategory.BUG,
            "regression": FindingCategory.REGRESSION,
        }
        return mapping.get(test_type, FindingCategory.BUG)

    def _build_finding_description(
        self,
        test_result: Any,
        test_case: Dict[str, Any],
    ) -> str:
        """Build a human-readable finding description."""
        parts = [
            f"Test '{test_result.test_title}' ({test_result.test_id}) failed.",
            f"Type: {test_result.test_type}",
            f"Error: {test_result.error_message or 'No error message'}",
        ]
        if test_case.get("expected_result"):
            parts.append(f"Expected: {test_case['expected_result']}")
        return "\n".join(parts)


# Avoid circular import
from qa_ai.schemas.execution_result_schema import TestOutcome  # noqa: E402


def get_execution_orchestrator(
    artifact_store: Optional[ArtifactStore] = None,
) -> ExecutionOrchestrator:
    """Factory function for creating an execution orchestrator."""
    if artifact_store is None:
        from qa_ai.runtime.artifact_store import get_artifact_store
        artifact_store = get_artifact_store()
    return ExecutionOrchestrator(artifact_store)
