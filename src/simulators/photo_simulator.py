"""Simulator for take_photo task."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.generators.entity_updates import (
    create_cc_system_update,
    create_evaporator_update,
    create_robot_update,
)
from src.generators.images import generate_captured_images
from src.schemas.commands import RobotState, TaskType
from src.schemas.results import EntityUpdate, RobotResult
from src.simulators.base import BaseSimulator

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.schemas.commands import TakePhotoParams


class PhotoSimulator(BaseSimulator):
    """Handles take_photo task."""

    async def simulate(self, task_id: str, task_type: TaskType, params: BaseModel) -> RobotResult:
        if task_type != TaskType.TAKE_PHOTO:
            raise ValueError(f"PhotoSimulator cannot handle task: {task_type}")
        return await self._simulate_take_photo(task_id, params)  # type: ignore[arg-type]

    async def _simulate_take_photo(self, task_id: str, params: TakePhotoParams) -> RobotResult:
        """Simulate take_photo: 2-5s per component."""
        components = params.components if isinstance(params.components, list) else [params.components]
        logger.info("Simulating take_photo for task {} ({} components)", task_id, len(components))

        # Determine current robot state from WorldState, default to IDLE
        current_state = RobotState.IDLE
        current_description = ""
        if self._world_state is not None:
            robot_state = self._world_state.get_robot_state(self.robot_id)
            if robot_state:
                state_str = robot_state.get("state", "idle")
                try:
                    current_state = RobotState(state_str)
                except ValueError:
                    current_state = RobotState.IDLE
                current_description = robot_state.get("description", "")

        # Log: robot arrived at station
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station, current_state, current_description),
            ],
            "robot arrived at station",
        )

        # Delay scales with number of components
        await self._apply_delay(2.0 * len(components), 5.0 * len(components))

        # Log: per-component photo taken
        for component in components:
            await self._publish_log(
                task_id,
                [
                    create_robot_update(self.robot_id, params.work_station, current_state, current_description),
                ],
                f"photo taken for {component}",
            )

        # Build updates list — final result always returns idle
        updates: list[EntityUpdate] = [
            create_robot_update(self.robot_id, params.work_station, RobotState.IDLE),
        ]

        # Add device state update if available in world_state
        device_update = self._get_device_update(params.device_id, params.device_type)
        if device_update is not None:
            updates.append(device_update)
            logger.debug("Added device state update for {} ({})", params.device_id, params.device_type)
        else:
            logger.debug(
                "No device state found in world_state for {} ({})",
                params.device_id,
                params.device_type,
            )

        images = generate_captured_images(
            self.image_base_url, params.work_station, params.device_id, params.device_type, components
        )

        return RobotResult(code=200, msg="success", task_id=task_id, updates=updates, images=images)

    def _get_device_update(self, device_id: str, device_type: str) -> EntityUpdate | None:
        """Retrieve device state from world_state and create appropriate update."""
        if self._world_state is None:
            return None

        # Map device_type to entity_type in world_state
        entity_type_map = {
            "combiflash": "column_chromatography_machine",
            "column_chromatography": "column_chromatography_machine",
            "column_chromatography_machine": "column_chromatography_machine",
            "column_chromatography_system": "column_chromatography_machine",
            "isco_combiflash_nextgen_300": "column_chromatography_machine",
            "cc-isco-300p": "column_chromatography_machine",
            "evaporator": "evaporator",
            "rotary_evaporator": "evaporator",
            "re-buchi-r180": "evaporator",
        }

        entity_type = entity_type_map.get(device_type)
        if entity_type is None:
            logger.warning("Unknown device_type for photo: {}", device_type)
            return None

        # Retrieve device state from world_state
        device_state = self._world_state.get_entity(entity_type, device_id)
        if device_state is None:
            return None

        # Create appropriate update based on entity type
        if entity_type == "column_chromatography_machine":
            return create_cc_system_update(
                system_id=device_id,
                state=device_state.get("state", "idle"),
                experiment_params=device_state.get("experiment_params"),
                start_timestamp=device_state.get("start_timestamp"),
            )
        elif entity_type == "evaporator":
            return create_evaporator_update(
                evaporator_id=device_id,
                state=device_state.get("state", "idle"),
                lower_height=device_state.get("lower_height", 0.0),
                rpm=device_state.get("rpm", 0),
                target_temperature=device_state.get("target_temperature", 0.0),
                current_temperature=device_state.get("current_temperature", 0.0),
                target_pressure=device_state.get("target_pressure", 0.0),
                current_pressure=device_state.get("current_pressure", 0.0),
            )

        return None
