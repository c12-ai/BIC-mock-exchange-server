"""Tests for heartbeat publisher."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, Mock, patch

import aio_pika
import pytest

from src.mq.heartbeat import HeartbeatPublisher
from src.schemas.results import HeartbeatMessage


class TestHeartbeatMessage:
    """Tests for HeartbeatMessage model."""

    def test_construction(self) -> None:
        """Test basic construction with required fields."""
        msg = HeartbeatMessage(
            robot_id="robot-001",
            timestamp="2025-01-15T10:30:00+00:00",
        )
        assert msg.robot_id == "robot-001"
        assert msg.timestamp == "2025-01-15T10:30:00+00:00"
        assert msg.state == "idle"

    def test_custom_state(self) -> None:
        """Test construction with custom state."""
        msg = HeartbeatMessage(
            robot_id="robot-002",
            timestamp="2025-01-15T10:30:00+00:00",
            state="working",
        )
        assert msg.state == "working"

    def test_serialization(self) -> None:
        """Test JSON serialization."""
        msg = HeartbeatMessage(
            robot_id="robot-001",
            timestamp="2025-01-15T10:30:00+00:00",
        )
        data = msg.model_dump()
        assert data["robot_id"] == "robot-001"
        assert data["timestamp"] == "2025-01-15T10:30:00+00:00"
        assert data["state"] == "idle"

        json_str = msg.model_dump_json()
        assert "robot-001" in json_str
        assert "idle" in json_str


class TestHeartbeatPublisher:
    """Tests for HeartbeatPublisher lifecycle and publishing."""

    def test_construction(self, mock_settings) -> None:
        """Test HeartbeatPublisher can be constructed."""
        mock_connection = Mock()
        heartbeat = HeartbeatPublisher(mock_connection, mock_settings)
        assert heartbeat._connection is mock_connection
        assert heartbeat._settings is mock_settings
        assert heartbeat._exchange is None
        assert heartbeat._task is None
        assert heartbeat._running is False

    @pytest.mark.asyncio
    async def test_initialize(self, mock_settings) -> None:
        """Test initialize declares exchange and caches reference."""
        mock_exchange = Mock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)

        mock_connection = Mock()
        mock_connection.get_channel = AsyncMock(return_value=mock_channel)

        heartbeat = HeartbeatPublisher(mock_connection, mock_settings)
        await heartbeat.initialize()

        mock_channel.declare_exchange.assert_awaited_once_with(
            mock_settings.mq_exchange,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        assert heartbeat._exchange is mock_exchange

    @pytest.mark.asyncio
    async def test_publish_heartbeat_raises_if_not_initialized(self, mock_settings) -> None:
        """Test _publish_heartbeat raises RuntimeError if exchange not initialized."""
        mock_connection = Mock()
        heartbeat = HeartbeatPublisher(mock_connection, mock_settings)

        with pytest.raises(RuntimeError, match="HeartbeatPublisher not initialized"):
            await heartbeat._publish_heartbeat()

    @pytest.mark.asyncio
    async def test_publish_heartbeat_publishes_correct_message(self, mock_settings) -> None:
        """Test _publish_heartbeat publishes with correct routing key and payload."""
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)

        mock_connection = Mock()
        mock_connection.get_channel = AsyncMock(return_value=mock_channel)

        heartbeat = HeartbeatPublisher(mock_connection, mock_settings)
        await heartbeat.initialize()

        # Mock generate_robot_timestamp to get predictable timestamp in spec format
        fixed_timestamp = "2025-01-15_10-30-00.000"
        with patch("src.mq.heartbeat.generate_robot_timestamp") as mock_timestamp:
            mock_timestamp.return_value = fixed_timestamp

            await heartbeat._publish_heartbeat()

        # Verify exchange.publish was called
        mock_exchange.publish.assert_awaited_once()
        call_args = mock_exchange.publish.call_args

        # Check routing key
        routing_key = call_args.kwargs["routing_key"]
        assert routing_key == f"{mock_settings.robot_id}.hb"

        # Check message properties
        message = call_args.args[0]
        assert isinstance(message, aio_pika.Message)
        assert message.content_type == "application/json"
        assert message.delivery_mode == aio_pika.DeliveryMode.NOT_PERSISTENT

        # Check message body
        body_dict = HeartbeatMessage.model_validate_json(message.body)
        assert body_dict.robot_id == mock_settings.robot_id
        assert body_dict.timestamp == fixed_timestamp
        assert body_dict.state == "idle"

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self, mock_settings) -> None:
        """Test start() creates a background task and sets running flag."""
        mock_connection = Mock()
        heartbeat = HeartbeatPublisher(mock_connection, mock_settings)

        # Mock _heartbeat_loop to prevent actual execution
        heartbeat._heartbeat_loop = AsyncMock()

        await heartbeat.start()

        assert heartbeat._running is True
        assert heartbeat._task is not None
        assert isinstance(heartbeat._task, asyncio.Task)

        # Clean up
        heartbeat._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat._task

    @pytest.mark.asyncio
    async def test_stop_cancels_task_gracefully(self, mock_settings) -> None:
        """Test stop() cancels task and clears state."""
        mock_connection = Mock()
        heartbeat = HeartbeatPublisher(mock_connection, mock_settings)

        # Create a task that will run indefinitely
        async def mock_loop() -> None:
            while True:
                await asyncio.sleep(0.1)

        heartbeat._running = True
        heartbeat._task = asyncio.create_task(mock_loop())

        # Stop should cancel the task
        await heartbeat.stop()

        assert heartbeat._running is False
        assert heartbeat._task is None

    @pytest.mark.asyncio
    async def test_heartbeat_loop_handles_exceptions(self, mock_settings) -> None:
        """Test _heartbeat_loop continues after publish exceptions."""
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)

        mock_connection = Mock()
        mock_connection.get_channel = AsyncMock(return_value=mock_channel)

        heartbeat = HeartbeatPublisher(mock_connection, mock_settings)
        await heartbeat.initialize()

        # Make _publish_heartbeat fail first time, succeed second time
        call_count = 0

        async def publish_side_effect() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated failure")

        heartbeat._publish_heartbeat = AsyncMock(side_effect=publish_side_effect)

        # Start the heartbeat loop
        heartbeat._running = True
        task = asyncio.create_task(heartbeat._heartbeat_loop())

        # Wait for at least 2 publish attempts
        await asyncio.sleep(2.2)  # > 2 * heartbeat_interval (1.0s)

        # Stop the loop
        heartbeat._running = False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Should have attempted to publish at least twice despite first failure
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_stop_when_no_task_running(self, mock_settings) -> None:
        """Test stop() is safe to call when no task is running."""
        mock_connection = Mock()
        heartbeat = HeartbeatPublisher(mock_connection, mock_settings)

        # Should not raise
        await heartbeat.stop()

        assert heartbeat._running is False
        assert heartbeat._task is None
