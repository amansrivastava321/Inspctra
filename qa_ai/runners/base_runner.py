"""
base_runner.py - Abstract base class for all test runners.
Defines the contract that every runner must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

from qa_ai.schemas.execution_result_schema import ExecutionResult

logger = logging.getLogger(__name__)


class BaseRunner(ABC):
    """
    Abstract base class for test runners.

    Every runner implements:
    - setup(): Prepare the test environment
    - execute(): Run the tests
    - teardown(): Clean up after tests
    - run(): Full lifecycle (setup → execute → teardown)

    Usage:
        class PlaywrightRunner(BaseRunner):
            ...

        runner = PlaywrightRunner(config={...})
        result = runner.run(test_plan)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: Runner-specific configuration (URLs, credentials, timeouts, etc.)
        """
        self.config = config or {}
        self.artifact_dir = Path(self.config.get("artifact_dir", "artifacts"))
        self.verbose = self.config.get("verbose", False)

    @property
    @abstractmethod
    def name(self) -> str:
        """Runner name (e.g., 'playwright_runner', 'api_runner')."""
        ...

    @property
    @abstractmethod
    def supported_platforms(self) -> List[str]:
        """Platforms this runner can handle (e.g., ['web'], ['android'])."""
        ...

    def run(self, test_plan: Dict[str, Any]) -> ExecutionResult:
        """
        Full lifecycle: setup → execute → teardown.

        Args:
            test_plan: Test plan dict (from test_plan.json)

        Returns:
            ExecutionResult with all test outcomes
        """
        logger.info(f"[{self.name}] Starting run")
        try:
            self.setup()
            result = self.execute(test_plan)
            logger.info(
                f"[{self.name}] Completed: "
                f"{result.passed}/{result.total_executed} passed"
            )
            return result
        except Exception as e:
            logger.error(f"[{self.name}] Run failed: {e}")
            return ExecutionResult(
                total_executed=0,
                passed=0,
                failed=0,
                errors=1,
                metadata_extra={"error": str(e)},
            )
        finally:
            try:
                self.teardown()
            except Exception as e:
                logger.warning(f"[{self.name}] Teardown error: {e}")

    @abstractmethod
    def execute(self, test_plan: Dict[str, Any]) -> ExecutionResult:
        """
        Execute the test plan and return results.

        Args:
            test_plan: Test plan dict containing test_suites

        Returns:
            ExecutionResult with suite-level and test-level outcomes
        """
        ...

    def setup(self) -> None:
        """Prepare the test environment. Override for custom setup."""
        logger.debug(f"[{self.name}] Setup (default: no-op)")

    def teardown(self) -> None:
        """Clean up after tests. Override for custom cleanup."""
        logger.debug(f"[{self.name}] Teardown (default: no-op)")

    def can_run(self, platform: str) -> bool:
        """Check if this runner supports the given platform."""
        return platform.lower() in self.supported_platforms
