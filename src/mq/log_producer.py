"""Log producer — publishes real-time state updates to {robot_id}.log via the topic exchange."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import aio_pika
from loguru import logger

from src.generators.entity_updates import generate_robot_timestamp

if TYPE_CHECKING:
    from aio_pika.abc import AbstractExchange

    from src.config import MockSettings
    from src.mq.connection import MQConnection
    from src.schemas.results import EntityUpdate


class LogProducer:
    """Publishes real-time log messages to {robot_id}.log via the topic exchange."""

    def __init__(self, connection: MQConnection, settings: MockSettings) -> None:
        self._connection = connection
        self._settings = settings
        self._exchange: AbstractExchange | None = None

    async def initialize(self) -> None:
        """Declare the topic exchange (idempotent) and cache a reference."""
        channel = await self._connection.get_channel()
        self._exchange = await channel.declare_exchange(
            self._settings.mq_exchange,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("LogProducer initialized, exchange: {}", self._settings.mq_exchange)

    async def publish_log(self, task_id: str, updates: Sequence[EntityUpdate], msg: str = "state_update") -> None:
        """Publish a log message with entity state updates to {robot_id}.log."""
        from src.schemas.results import LogMessage

        if self._exchange is None:
            raise RuntimeError("LogProducer not initialized. Call initialize() first.")

        log_msg = LogMessage(
            task_id=task_id,
            updates=list(updates),
            msg=msg,
            timestamp=generate_robot_timestamp(),
        )

        routing_key = f"{self._settings.robot_id}.log"
        body = log_msg.model_dump_json().encode()

        await self._exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )

        logger.debug(
            "Published log for task {} via {}: {}",
            task_id,
            routing_key,
            log_msg.model_dump_json(indent=2),
        )
