"""Heartbeat publisher — sends periodic heartbeat via {robot_id}.hb."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import aio_pika
from loguru import logger

from src.generators.entity_updates import generate_robot_timestamp
from src.schemas.protocol import RobotState

if TYPE_CHECKING:
    from aio_pika.abc import AbstractExchange

    from src.config import MockSettings
    from src.mq.connection import MQConnection
    from src.state.world_state import WorldState


class HeartbeatPublisher:
    """Publishes periodic heartbeat messages to {robot_id}.hb via the topic exchange."""

    def __init__(self, connection: MQConnection, settings: MockSettings, world_state: WorldState | None = None) -> None:
        self._connection = connection
        self._settings = settings
        self._world_state = world_state
        self._exchange: AbstractExchange | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    async def initialize(self) -> None:
        """Declare the exchange (idempotent) and cache reference."""
        channel = await self._connection.get_channel()
        self._exchange = await channel.declare_exchange(
            self._settings.mq_exchange,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

    async def start(self) -> None:
        """Start the heartbeat background task."""
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat started (interval={}s)", self._settings.heartbeat_interval)

    async def stop(self) -> None:
        """Stop the heartbeat background task gracefully."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Heartbeat stopped")

    async def _heartbeat_loop(self) -> None:
        """Background loop: publish heartbeat at configured interval."""
        while self._running:
            try:
                await self._publish_heartbeat()
            except Exception:
                logger.exception("Failed to publish heartbeat")
            await asyncio.sleep(self._settings.heartbeat_interval)

    async def _publish_heartbeat(self) -> None:
        """Publish a single heartbeat message."""
        from src.schemas.results import HeartbeatMessage

        if self._exchange is None:
            raise RuntimeError("HeartbeatPublisher not initialized. Call initialize() first.")

        # Read current robot state from world state if available
        current_state = RobotState.IDLE
        work_station: str | None = None
        if self._world_state is not None:
            robot_state = self._world_state.get_robot_state(self._settings.robot_id)
            if robot_state:
                state_str = robot_state.get("state", "idle")
                # Map to RobotState enum, default to IDLE for unknown values
                try:
                    current_state = RobotState(state_str)
                except ValueError:
                    current_state = RobotState.IDLE
                work_station = robot_state.get("location")

        msg = HeartbeatMessage(
            robot_id=self._settings.robot_id,
            timestamp=generate_robot_timestamp(),
            state=current_state,
            Work_station=work_station,
        )
        routing_key = f"{self._settings.robot_id}.hb"
        body = msg.model_dump_json().encode()

        await self._exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT,
            ),
            routing_key=routing_key,
        )
        logger.debug("Heartbeat published via {} (state={})", routing_key, current_state)
