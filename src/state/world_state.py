"""World state tracker for entity updates.

Maintains an in-memory snapshot of all tracked entities (robots, equipment, materials)
based on entity updates from skill execution results. Thread-safe for concurrent access.
"""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from src.schemas.results import EntityUpdate


class WorldState:
    """Thread-safe in-memory state tracker for all entities in the robot's world.

    Entities are keyed by (entity_type, entity_id) tuples. Each entity stores
    its latest properties as a dictionary.
    """

    def __init__(self) -> None:
        """Initialize empty world state."""
        self._entities: dict[tuple[str, str], dict[str, Any]] = {}
        self._lock = RLock()

    def apply_updates(self, updates: list[EntityUpdate]) -> None:
        """Apply a batch of entity updates to the world state.

        Each update either creates a new entity or overwrites an existing one
        with the latest properties.

        Args:
            updates: List of entity updates from a RobotResult
        """
        with self._lock:
            for update in updates:
                entity_key = (update.type, update.id)
                # Store properties as a dict for flexible access
                properties_dict = update.properties.model_dump()
                self._entities[entity_key] = properties_dict
                logger.debug("World state updated: {} {} -> {}", update.type, update.id, properties_dict)

    def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        """Retrieve an entity's current properties.

        Args:
            entity_type: Entity type (e.g., "robot", "silica_cartridge")
            entity_id: Entity ID

        Returns:
            Dictionary of entity properties, or None if not tracked
        """
        with self._lock:
            return self._entities.get((entity_type, entity_id))

    def has_entity(self, entity_type: str, entity_id: str) -> bool:
        """Check if an entity is currently tracked.

        Args:
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            True if entity exists in world state
        """
        with self._lock:
            return (entity_type, entity_id) in self._entities

    def get_entities_by_type(self, entity_type: str) -> dict[str, dict[str, Any]]:
        """Retrieve all entities of a given type.

        Args:
            entity_type: Entity type to filter by

        Returns:
            Dictionary mapping entity_id -> properties for all matching entities
        """
        with self._lock:
            return {
                entity_id: props.copy() for (etype, entity_id), props in self._entities.items() if etype == entity_type
            }

    def get_robot_state(self, robot_id: str) -> dict[str, Any] | None:
        """Convenience method to get robot entity state.

        Args:
            robot_id: Robot ID to look up

        Returns:
            Robot properties dict, or None if not tracked
        """
        return self.get_entity("robot", robot_id)

    def reset(self) -> None:
        """Clear all tracked entities back to empty state."""
        with self._lock:
            self._entities.clear()
            logger.info("World state reset - all entities cleared")
