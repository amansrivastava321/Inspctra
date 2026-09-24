"""
api_runner.py - HTTP API test runner.
Executes API test cases by making HTTP requests and validating responses.
All requests/responses are captured as evidence.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import time
import logging
import json

import requests

from qa_ai.config.settings import get_settings as _get_settings
from qa_ai.runners.base_runner import BaseRunner
from qa_ai.schemas.execution_result_schema import (
    ExecutionResult,
    ExecutionMetadata,
    SuiteResult,
    TestResult,
    TestOutcome,
)
from qa_ai.evidence.evidence_collector import EvidenceCollector
from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)

# Default timeout for API requests in seconds
DEFAULT_TIMEOUT = 30

# Expected status codes for different test types
SUCCESS_STATUSES = {200, 201, 202, 204, 301, 302, 304}


class APIRunner(BaseRunner):
    """
    Executes API test cases from a test plan.

    For each test case targeting an API endpoint:
    1. Constructs the HTTP request from test case metadata
    2. Sends the request using the `requests` library
    3. Validates the response status code
    4. Captures the full request/response as evidence
    5. Produces a TestResult

    Config:
        base_url: Base URL for API requests (required)
        timeout: Request timeout in seconds (default: 30)
        headers: Default headers for all requests
        auth: Authentication tuple or token
    """

    @property
    def name(self) -> str:
        return "api_runner"

    @property
    def supported_platforms(self) -> List[str]:
        return ["backend", "api", "cli", "web"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.base_url = self.config.get("base_url", _get_settings().api_base_url)
        self.timeout = self.config.get("timeout", DEFAULT_TIMEOUT)
        self.default_headers = self.config.get("headers", {})
        self.auth = self.config.get("auth")
        self._session = None
        self._evidence: Optional[EvidenceCollector] = None

    def setup(self) -> None:
        """Create HTTP session and evidence collector."""
        self._session = requests.Session()
        if self.default_headers:
            self._session.headers.update(self.default_headers)
        if self.auth:
            self._session.auth = self.auth

        store = ArtifactStore(base_dir=self.artifact_dir)
        run_id = self.config.get("run_id", f"api-{int(time.time())}")
        self._evidence = EvidenceCollector(artifact_store=store, run_id=run_id)

    def teardown(self) -> None:
        """Close session and save evidence index."""
        if self._session:
            self._session.close()
        if self._evidence:
            self._evidence.save_index()

    def execute(self, test_plan: Dict[str, Any]) -> ExecutionResult:
        """Execute all API-suitable test cases from the test plan."""
        started_at = datetime.now(timezone.utc)
        suites: List[SuiteResult] = []
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        total_errors = 0

        test_suites = test_plan.get("test_suites", {})

        for suite_name, tests in test_suites.items():
            if not tests:
                continue

            suite_result = self._run_suite(suite_name, tests)
            suites.append(suite_result)
            total_passed += suite_result.passed
            total_failed += suite_result.failed
            total_skipped += suite_result.skipped
            total_errors += suite_result.errors

        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()
        total_executed = total_passed + total_failed + total_skipped + total_errors

        return ExecutionResult(
            metadata=ExecutionMetadata(
                run_id=self.config.get("run_id", ""),
                app_name=self.config.get("app_name", ""),
                platform="backend",
                environment=self.config.get("environment", "local"),
                runner=self.name,
                started_at=started_at.isoformat(),
                completed_at=completed_at.isoformat(),
                duration_seconds=duration,
            ),
            total_executed=total_executed,
            passed=total_passed,
            failed=total_failed,
            skipped=total_skipped,
            errors=total_errors,
            duration_seconds=duration,
            suites=suites,
        )

    def _run_suite(self, suite_name: str, tests: List[Dict[str, Any]]) -> SuiteResult:
        """Run all tests in a single suite."""
        started_at = time.time()
        results: List[TestResult] = []
        passed = failed = skipped = errors = 0

        for test_case in tests:
            result = self._run_single_test(suite_name, test_case)
            results.append(result)

            if result.outcome == TestOutcome.PASSED:
                passed += 1
            elif result.outcome == TestOutcome.FAILED:
                failed += 1
            elif result.outcome == TestOutcome.SKIPPED:
                skipped += 1
            else:
                errors += 1

        duration = time.time() - started_at
        total = len(results)

        return SuiteResult(
            suite_name=suite_name,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration_seconds=duration,
            tests=results,
        )

    def _run_single_test(self, suite_name: str, test_case: Dict[str, Any]) -> TestResult:
        """Execute a single API test case."""
        test_id = test_case.get("id", "unknown")
        test_title = test_case.get("title", "")
        test_type = test_case.get("type", suite_name)
        target = test_case.get("target", {})
        steps = test_case.get("steps", [])
        expected_result = test_case.get("expected_result", "")

        # Determine if this test targets an API endpoint
        api_target = target.get("api", "")
        if not api_target:
            # Check if test title implies an API call
            if not self._is_api_test(test_title, steps):
                return TestResult(
                    test_id=test_id,
                    test_title=test_title,
                    test_type=test_type,
                    outcome=TestOutcome.SKIPPED,
                    metadata={"reason": "Not an API test"},
                )

        started_at = time.time()

        try:
            method, path = self._parse_api_target(api_target, test_title)
            url = f"{self.base_url.rstrip('/')}{path}"

            # Determine expected status from expected_result or test type
            expected_status = self._infer_expected_status(expected_result, test_type, method)

            # Make the request
            response = self._make_request(method, url, test_case)

            duration_ms = (time.time() - started_at) * 1000

            # Capture evidence
            if self._evidence:
                self._evidence.capture_api_response(
                    test_id=test_id,
                    test_title=test_title,
                    method=method,
                    url=url,
                    request_headers=dict(self._session.headers) if self._session else {},
                    response_status=response.status_code,
                    response_headers=dict(response.headers),
                    response_body=self._safe_body(response),
                    duration_ms=duration_ms,
                )

            # Evaluate result
            if expected_status and response.status_code == expected_status:
                outcome = TestOutcome.PASSED
                error_msg = None
            elif response.status_code in SUCCESS_STATUSES and test_type in ("functional", "smoke"):
                outcome = TestOutcome.PASSED
                error_msg = None
            elif response.status_code >= 400 and test_type in ("negative", "security"):
                # Negative tests expect error responses
                outcome = TestOutcome.PASSED
                error_msg = None
            else:
                outcome = TestOutcome.FAILED
                error_msg = f"Expected status {expected_status}, got {response.status_code}"

            return TestResult(
                test_id=test_id,
                test_title=test_title,
                test_type=test_type,
                outcome=outcome,
                duration_seconds=(time.time() - started_at),
                error_message=error_msg,
                evidence_paths=[f"evidence/api_responses/{test_id}_*.json"],
                metadata={
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                },
            )

        except Exception as e:
            duration = time.time() - started_at
            if self._evidence:
                self._evidence.capture_error(test_id, test_title, e, context=suite_name)

            return TestResult(
                test_id=test_id,
                test_title=test_title,
                test_type=test_type,
                outcome=TestOutcome.ERROR,
                duration_seconds=duration,
                error_message=str(e),
                metadata={"error_type": type(e).__name__},
            )

    def _make_request(self, method: str, url: str, test_case: Dict[str, Any]):
        """Send an HTTP request."""
        if not self._session:
            raise RuntimeError("HTTP session not initialized. Call setup() first.")

        kwargs: Dict[str, Any] = {"timeout": self.timeout}

        # Add body for mutation methods
        if method in ("POST", "PUT", "PATCH"):
            body = test_case.get("request_body")
            if body:
                kwargs["json"] = body
            else:
                kwargs["json"] = {}

        return self._session.request(method, url, **kwargs)

    def _parse_api_target(self, api_target: str, title: str) -> tuple:
        """Parse 'GET /users' into ('GET', '/users')."""
        if api_target and " " in api_target:
            parts = api_target.split(" ", 1)
            return parts[0].upper(), parts[1]

        # Try to extract from title
        title_upper = title.upper()
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            if method in title_upper:
                # Find the path after the method
                idx = title_upper.index(method) + len(method)
                rest = title[idx:].strip()
                if rest.startswith("/"):
                    path = rest.split(" ")[0]
                    return method, path

        return "GET", "/"

    def _infer_expected_status(self, expected_result: str, test_type: str, method: str) -> Optional[int]:
        """Infer expected HTTP status from the expected_result text."""
        expected_lower = expected_result.lower()

        if "200" in expected_result:
            return 200
        if "201" in expected_result:
            return 201
        if "204" in expected_result:
            return 204
        if "400" in expected_result:
            return 400
        if "401" in expected_result:
            return 401
        if "403" in expected_result:
            return 403
        if "404" in expected_result:
            return 404
        if "422" in expected_result:
            return 422

        # Default by test type
        if test_type in ("negative", "security"):
            if "no pii" in expected_lower or "no data" in expected_lower:
                return None  # Accept any non-leaking response
            return 400  # Expect client error for negative tests

        return None  # No specific expectation

    def _is_api_test(self, title: str, steps: List[str]) -> bool:
        """Heuristic: does this test case target an API?"""
        import re
        indicators = [r"\bapi\b", r"\bendpoint\b", r"\bget\s", r"\bpost\s", r"\bput\s",
                      r"\bdelete\s", r"\bpatch\s", r"\bcall\s", r"\brequest\b"]
        combined = (title.lower() + " " + " ".join(steps).lower())
        return any(re.search(ind, combined) for ind in indicators)

    def _safe_body(self, response) -> Any:
        """Safely extract response body."""
        try:
            return response.json()
        except Exception as e:
            logger.debug("_safe_body: failed to parse response as JSON: %s", e)
            try:
                text = response.text
                return text[:2000] if len(text) > 2000 else text
            except Exception as e:
                logger.debug("_safe_body: failed to read response text: %s", e)
                return None
