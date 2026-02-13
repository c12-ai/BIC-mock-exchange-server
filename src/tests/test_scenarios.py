"""Tests for scenario management: ScenarioManager and failure message tables."""

from __future__ import annotations

from src.config import MockSettings
from src.scenarios.failures import FAILURE_MESSAGES, get_random_failure
from src.scenarios.manager import ScenarioManager
from src.schemas.commands import TaskType


class TestScenarioManager:
    """Tests for ScenarioManager scenario selection logic."""

    def test_scenario_manager_success_mode(self, mock_settings: MockSettings) -> None:
        """With rate=0.0, should_timeout and should_fail both return False."""
        manager = ScenarioManager(mock_settings)

        assert manager.should_timeout(TaskType.START_CC) is False
        assert manager.should_fail(TaskType.START_CC) is False

    def test_scenario_manager_timeout_injection(self) -> None:
        """With timeout_rate=1.0, should_timeout returns True."""
        settings = MockSettings(
            mq_host="localhost",
            timeout_rate=1.0,
            failure_rate=0.0,
            default_scenario="success",
        )
        manager = ScenarioManager(settings)

        assert manager.should_timeout(TaskType.TAKE_PHOTO) is True

    def test_scenario_manager_failure_injection(self) -> None:
        """With failure_rate=1.0, should_fail returns True."""
        settings = MockSettings(
            mq_host="localhost",
            failure_rate=1.0,
            timeout_rate=0.0,
            default_scenario="success",
        )
        manager = ScenarioManager(settings)

        assert manager.should_fail(TaskType.SETUP_CARTRIDGES) is True

    def test_scenario_manager_default_failure(self) -> None:
        """With default_scenario='failure', should_fail returns True even with failure_rate=0."""
        settings = MockSettings(
            mq_host="localhost",
            default_scenario="failure",
            failure_rate=0.0,
            timeout_rate=0.0,
        )
        manager = ScenarioManager(settings)

        assert manager.should_fail(TaskType.START_EVAPORATION) is True

    def test_get_failure_result(self, mock_settings: MockSettings) -> None:
        """ScenarioManager.get_failure_result returns RobotResult with code > 0."""
        manager = ScenarioManager(mock_settings)
        result = manager.get_failure_result("task-123", TaskType.START_CC)

        assert result.code != 200
        assert result.msg != ""
        assert result.task_id == "task-123"
        assert result.updates == []


class TestFailureMessages:
    """Tests for failure message tables and random selection."""

    def test_failure_messages_all_tasks(self) -> None:
        """Every TaskType has entries in FAILURE_MESSAGES."""
        for task_type in TaskType:
            assert task_type in FAILURE_MESSAGES, f"Missing FAILURE_MESSAGES entry for {task_type}"
            assert len(FAILURE_MESSAGES[task_type]) > 0, f"Empty messages for {task_type}"

    def test_get_random_failure_returns_valid(self) -> None:
        """For each TaskType, get_random_failure returns (int, str)."""
        for task_type in TaskType:
            code, msg = get_random_failure(task_type)

            assert isinstance(code, int)
            assert code > 0
            assert isinstance(msg, str)
            assert len(msg) > 0
