"""Tests for LogMessage schema and LogProducer construction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.schemas.results import (
    LogMessage,
    RobotProperties,
    RobotUpdate,
)


class TestLogMessage:
    """Tests for the LogMessage Pydantic model."""

    def test_log_message_defaults(self) -> None:
        """Default code=200 and msg='state_update' are set."""
        msg = LogMessage(task_id="task-001", timestamp="2025-01-13T01:17:25.312Z")

        assert msg.code == 200
        assert msg.msg == "state_update"
        assert msg.task_id == "task-001"
        assert msg.updates == []
        assert msg.timestamp == "2025-01-13T01:17:25.312Z"

    def test_log_message_with_updates(self) -> None:
        """LogMessage with entity updates serializes correctly."""
        robot_update = RobotUpdate(
            id="robot-001",
            properties=RobotProperties(location="ws-1", state="idle"),
        )
        msg = LogMessage(
            task_id="task-002",
            updates=[robot_update],
            msg="robot moving to station",
            timestamp="2025-01-13T02:00:00.000Z",
        )

        assert len(msg.updates) == 1
        assert msg.msg == "robot moving to station"

    def test_log_message_serialization_roundtrip(self) -> None:
        """model_dump_json roundtrip preserves all fields."""
        robot_update = RobotUpdate(
            id="robot-001",
            properties=RobotProperties(location="ws-1", state="idle"),
        )
        msg = LogMessage(
            task_id="task-003",
            updates=[robot_update],
            timestamp="2025-01-13T03:00:00.000Z",
        )

        json_str = msg.model_dump_json()
        restored = LogMessage.model_validate_json(json_str)

        assert restored.code == 200
        assert restored.msg == "state_update"
        assert restored.task_id == "task-003"
        assert restored.timestamp == "2025-01-13T03:00:00.000Z"
        assert len(restored.updates) == 1
        assert isinstance(restored.updates[0], RobotUpdate)
        assert restored.updates[0].id == "robot-001"

    def test_log_message_json_structure(self) -> None:
        """Serialized JSON has the expected top-level keys."""
        msg = LogMessage(
            task_id="task-004",
            timestamp="2025-01-13T04:00:00.000Z",
        )

        parsed = json.loads(msg.model_dump_json())

        assert set(parsed.keys()) == {"code", "msg", "task_id", "updates", "timestamp"}
        assert parsed["code"] == 200
        assert parsed["msg"] == "state_update"

    def test_log_message_custom_code(self) -> None:
        """Code can be overridden from default 200."""
        msg = LogMessage(code=500, task_id="task-005", timestamp="2025-01-13T05:00:00.000Z")

        assert msg.code == 500


class TestLogProducerConstruction:
    """Tests for LogProducer object construction (no real MQ needed)."""

    def test_log_producer_can_be_constructed(self) -> None:
        """LogProducer can be instantiated with mock dependencies."""
        from src.mq.log_producer import LogProducer

        mock_connection = MagicMock()
        mock_settings = MagicMock()
        mock_settings.mq_exchange = "test_exchange"
        mock_settings.robot_id = "test-robot-001"

        producer = LogProducer(mock_connection, mock_settings)

        assert producer._connection is mock_connection
        assert producer._settings is mock_settings
        assert producer._exchange is None

    async def test_log_producer_publish_raises_without_init(self) -> None:
        """publish_log raises RuntimeError if initialize() was not called."""
        from src.mq.log_producer import LogProducer

        mock_connection = MagicMock()
        mock_settings = MagicMock()

        producer = LogProducer(mock_connection, mock_settings)

        with pytest.raises(RuntimeError, match="LogProducer not initialized"):
            await producer.publish_log("task-001", [])


class TestBaseSimulatorLogIntegration:
    """Tests for BaseSimulator._publish_log helper."""

    async def test_publish_log_skips_when_no_log_producer(self) -> None:
        """_publish_log is a no-op when log_producer is None."""
        from src.simulators.base import BaseSimulator

        class _StubSimulator(BaseSimulator):
            async def simulate(self, task_id, task_name, params):
                return None

        mock_producer = MagicMock()
        mock_settings = MagicMock()
        mock_settings.robot_id = "test-robot"
        mock_settings.base_delay_multiplier = 0.01
        mock_settings.min_delay_seconds = 0.0

        sim = _StubSimulator(mock_producer, mock_settings)
        assert sim._log_producer is None

        # Should not raise
        await sim._publish_log("task-001", [])

    async def test_publish_log_delegates_to_log_producer(self) -> None:
        """_publish_log calls log_producer.publish_log when available."""
        from src.simulators.base import BaseSimulator

        class _StubSimulator(BaseSimulator):
            async def simulate(self, task_id, task_name, params):
                return None

        mock_producer = MagicMock()
        mock_log_producer = MagicMock()
        mock_log_producer.publish_log = AsyncMock()
        mock_settings = MagicMock()
        mock_settings.robot_id = "test-robot"
        mock_settings.base_delay_multiplier = 0.01
        mock_settings.min_delay_seconds = 0.0

        sim = _StubSimulator(mock_producer, mock_settings, log_producer=mock_log_producer)

        robot_update = RobotUpdate(
            id="test-robot",
            properties=RobotProperties(location="ws-1", state="idle"),
        )

        await sim._publish_log("task-001", [robot_update], "test message")

        mock_log_producer.publish_log.assert_called_once_with("task-001", [robot_update], "test message")
