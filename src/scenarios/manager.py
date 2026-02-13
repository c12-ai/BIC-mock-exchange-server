"""Scenario management for success, failure, and timeout injection."""

from __future__ import annotations

import random

from loguru import logger

from src.config import MockSettings
from src.scenarios.failures import get_random_failure
from src.schemas.commands import TaskType
from src.schemas.results import RobotResult


class ScenarioManager:
    """Manages scenario selection: success, failure, or timeout."""

    def __init__(self, settings: MockSettings) -> None:
        self._default_scenario = settings.default_scenario
        self._failure_rate = settings.failure_rate
        self._timeout_rate = settings.timeout_rate

    def should_timeout(self, task_type: TaskType | str) -> bool:
        """Check if this task should simulate a timeout (no response).

        Timeout takes priority over failure.
        """
        if self._timeout_rate > 0 and random.random() < self._timeout_rate:  # noqa: S311
            logger.info("Scenario: TIMEOUT injected for task {}", task_type)
            return True
        return False

    def should_fail(self, task_type: TaskType | str) -> bool:
        """Check if this task should simulate a failure."""
        # Check explicit failure rate
        if self._failure_rate > 0 and random.random() < self._failure_rate:  # noqa: S311
            logger.info("Scenario: FAILURE injected for task {}", task_type)
            return True
        # Check default scenario
        if self._default_scenario == "failure":
            logger.info("Scenario: FAILURE (default) for task {}", task_type)
            return True
        return False

    def get_failure_result(self, task_id: str, task_type: TaskType | str) -> RobotResult:
        """Generate a failure RobotResult with task-specific error."""
        code, msg = get_random_failure(TaskType(task_type))
        logger.warning(
            "Generated failure result for task {} ({}): code={}, msg={}",
            task_id,
            task_type,
            code,
            msg,
        )
        return RobotResult(code=code, msg=msg, task_id=task_id, updates=[])
