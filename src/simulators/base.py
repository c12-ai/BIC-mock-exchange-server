"""Base simulator ABC for all task types."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING

from loguru import logger

from src.generators.timing import calculate_delay

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.config import MockSettings
    from src.mq.log_producer import LogProducer
    from src.mq.producer import ResultProducer
    from src.schemas.commands import TaskType
    from src.schemas.results import EntityUpdate, RobotResult
    from src.state.world_state import WorldState


class BaseSimulator(ABC):
    """Abstract base class for task simulators."""

    def __init__(
        self,
        producer: ResultProducer,
        settings: MockSettings,
        *,
        log_producer: LogProducer | None = None,
        world_state: WorldState | None = None,
    ) -> None:
        self._producer = producer
        self._settings = settings
        self._log_producer = log_producer
        self._world_state = world_state

    @property
    def robot_id(self) -> str:
        """The mock robot identifier from settings."""
        return self._settings.robot_id

    @property
    def multiplier(self) -> float:
        """The delay multiplier from settings."""
        return self._settings.base_delay_multiplier

    @property
    def min_delay(self) -> float:
        """The minimum delay from settings."""
        return self._settings.min_delay_seconds

    @property
    def image_base_url(self) -> str:
        """The image base URL from settings."""
        return self._settings.image_base_url

    @abstractmethod
    async def simulate(self, task_id: str, task_type: TaskType, params: BaseModel) -> RobotResult:
        """Simulate a robot task and return the result."""
        ...

    async def _publish_log(self, task_id: str, updates: Sequence[EntityUpdate], msg: str = "state_update") -> None:
        """Publish a real-time log entry via the log channel if a LogProducer is available."""
        if self._log_producer is not None:
            await self._log_producer.publish_log(task_id, updates, msg)

    async def _apply_delay(self, base_min: float, base_max: float) -> None:
        """Apply a randomized delay scaled by the multiplier."""
        delay = calculate_delay(base_min, base_max, self.multiplier, self.min_delay)
        logger.debug("Applying delay: {:.2f}s (base {}-{}, multiplier {})", delay, base_min, base_max, self.multiplier)
        await asyncio.sleep(delay)

    def _find_entity_at_location(self, entity_type: str, location: str) -> str | None:
        """Look up an entity ID by type and location from WorldState.

        Useful when a command doesn't include a material's UUID but the mock server
        previously tracked it via setup updates. Falls back to the location string
        if WorldState is unavailable or the entity is not found.
        """
        if self._world_state is None:
            return None
        entities = self._world_state.get_entities_by_type(entity_type)
        for entity_id, props in entities.items():
            if props.get("location") == location:
                return entity_id
        return None

    def _resolve_entity_id(self, entity_type: str, location: str) -> str:
        """Resolve an entity ID from WorldState, falling back to the location string.

        This allows simulators to produce correct entity IDs in result messages
        even when the command params don't include the material UUID.
        """
        found = self._find_entity_at_location(entity_type, location)
        if found is not None:
            return found
        logger.debug(
            "Cannot resolve {} at location {} from WorldState, using location as fallback",
            entity_type,
            location,
        )
        return location
