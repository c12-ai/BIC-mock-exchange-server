"""Simulator for setup-related tasks: setup_cartridges, setup_tube_rack."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.generators.entity_updates import (
    create_ccs_ext_module_update,
    create_robot_update,
    create_sample_cartridge_update,
    create_silica_cartridge_update,
    create_tube_rack_update,
)
from src.schemas.commands import ConsumableState, DeviceState, RobotState, TaskType, ToolState
from src.schemas.results import RobotResult
from src.simulators.base import BaseSimulator

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.schemas.commands import SetupCartridgesParams, SetupTubeRackParams


class SetupSimulator(BaseSimulator):
    """Handles setup_cartridges and setup_tube_rack."""

    async def simulate(self, task_id: str, task_type: TaskType, params: BaseModel) -> RobotResult:
        """Route to the appropriate setup handler."""
        match task_type:
            case TaskType.SETUP_CARTRIDGES:
                return await self._simulate_setup_cartridges(task_id, params)  # type: ignore[arg-type]
            case TaskType.SETUP_TUBE_RACK:
                return await self._simulate_setup_tube_rack(task_id, params)  # type: ignore[arg-type]
            case _:
                raise ValueError(f"SetupSimulator cannot handle task: {task_type}")

    async def _simulate_setup_cartridges(self, task_id: str, params: SetupCartridgesParams) -> RobotResult:
        """Simulate setup_tubes_to_column_machine: 15-30s delay."""
        logger.info("Simulating setup_cartridges for task {}", task_id)

        # Log: robot moving to work station
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station, RobotState.WORKING),
            ],
            "robot moving to work station",
        )

        await self._apply_delay(15.0, 30.0)

        # Generate silica cartridge ID (auto-generated since not in command params)
        silica_id = f"{params.silica_cartridge_type}_001"

        # Resolve CCS ext module ID from WorldState or use default
        ext_module_id = self._resolve_entity_id("ccs_ext_module", params.work_station)

        # Log: cartridges mounted
        cartridge_updates = [
            create_silica_cartridge_update(silica_id, params.work_station, ConsumableState.INUSE),
            create_sample_cartridge_update(params.sample_cartridge_id, params.work_station, ConsumableState.INUSE),
            create_ccs_ext_module_update(ext_module_id, DeviceState.USING),
        ]
        await self._publish_log(task_id, cartridge_updates, "cartridges mounted")

        # Log: robot idle
        idle_update = [create_robot_update(self.robot_id, params.work_station, RobotState.IDLE)]
        await self._publish_log(task_id, idle_update, "robot idle")

        updates = [
            create_robot_update(self.robot_id, params.work_station, RobotState.IDLE),
            create_silica_cartridge_update(silica_id, params.work_station, ConsumableState.INUSE),
            create_sample_cartridge_update(params.sample_cartridge_id, params.work_station, ConsumableState.INUSE),
            create_ccs_ext_module_update(ext_module_id, DeviceState.USING),
        ]
        return RobotResult(code=200, msg="success", task_id=task_id, updates=updates)

    async def _simulate_setup_tube_rack(self, task_id: str, params: SetupTubeRackParams) -> RobotResult:
        """Simulate setup_tube_rack: 10-20s delay."""
        logger.info("Simulating setup_tube_rack for task {}", task_id)

        # Log: robot moving to work station
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station, RobotState.WORKING),
            ],
            "robot moving to work station",
        )

        await self._apply_delay(10.0, 20.0)

        # Generate tube rack ID (case study format: tube_rack_001)
        tube_rack_id = "tube_rack_001"

        # Log: tube rack mounted
        await self._publish_log(
            task_id,
            [
                create_tube_rack_update(tube_rack_id, params.work_station, ToolState.INUSE, description="mounted"),
            ],
            "tube_rack mounted",
        )

        updates = [
            create_robot_update(self.robot_id, params.work_station, RobotState.IDLE),
            create_tube_rack_update(tube_rack_id, params.work_station, ToolState.INUSE, description="mounted"),
        ]
        return RobotResult(code=200, msg="success", task_id=task_id, updates=updates)
