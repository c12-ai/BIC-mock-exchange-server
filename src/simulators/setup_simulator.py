"""Simulator for setup-related tasks: setup_cartridges, setup_tube_rack, collapse_cartridges."""

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
from src.schemas.commands import EntityState, RobotState, TaskName
from src.schemas.results import RobotResult
from src.simulators.base import BaseSimulator

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.schemas.commands import CollapseCartridgesParams, SetupCartridgesParams, SetupTubeRackParams


class SetupSimulator(BaseSimulator):
    """Handles setup_cartridges, setup_tube_rack, and collapse_cartridges."""

    async def simulate(self, task_id: str, task_name: TaskName, params: BaseModel) -> RobotResult:
        """Route to the appropriate setup handler."""
        match task_name:
            case TaskName.SETUP_CARTRIDGES:
                return await self._simulate_setup_cartridges(task_id, params)  # type: ignore[arg-type]
            case TaskName.SETUP_TUBE_RACK:
                return await self._simulate_setup_tube_rack(task_id, params)  # type: ignore[arg-type]
            case TaskName.COLLAPSE_CARTRIDGES:
                return await self._simulate_collapse_cartridges(task_id, params)  # type: ignore[arg-type]
            case _:
                raise ValueError(f"SetupSimulator cannot handle task: {task_name}")

    async def _simulate_setup_cartridges(self, task_id: str, params: SetupCartridgesParams) -> RobotResult:
        """Simulate setup_tubes_to_column_machine: 15-30s delay."""
        logger.info("Simulating setup_cartridges for task {}", task_id)

        # Log: robot moving to work station
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "moving"),
            ],
            "robot moving to work station",
        )

        await self._apply_delay(15.0, 30.0)

        # Log: cartridges mounted
        cartridge_updates = [
            create_silica_cartridge_update(params.silica_cartridge_id, params.work_station_id, EntityState.MOUNTED),
            create_sample_cartridge_update(params.sample_cartridge_id, params.work_station_id, EntityState.MOUNTED),
            create_ccs_ext_module_update(params.work_station_id, EntityState.USING),
        ]
        await self._publish_log(task_id, cartridge_updates, "cartridges mounted")

        # Log: robot idle
        idle_update = [create_robot_update(self.robot_id, params.work_station_id, RobotState.IDLE)]
        await self._publish_log(task_id, idle_update, "robot idle")

        updates = [
            create_robot_update(self.robot_id, params.work_station_id, RobotState.IDLE),
            create_silica_cartridge_update(params.silica_cartridge_id, params.work_station_id, EntityState.MOUNTED),
            create_sample_cartridge_update(params.sample_cartridge_id, params.work_station_id, EntityState.MOUNTED),
            create_ccs_ext_module_update(params.work_station_id, EntityState.USING),
        ]
        return RobotResult(code=200, msg="setup_cartridges completed", task_id=task_id, updates=updates)

    async def _simulate_setup_tube_rack(self, task_id: str, params: SetupTubeRackParams) -> RobotResult:
        """Simulate setup_tube_rack: 10-20s delay."""
        logger.info("Simulating setup_tube_rack for task {}", task_id)

        # Log: robot moving to work station
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "moving"),
            ],
            "robot moving to work station",
        )

        await self._apply_delay(10.0, 20.0)

        # Log: tube rack mounted
        await self._publish_log(
            task_id,
            [
                create_tube_rack_update(params.tube_rack_location_id, params.work_station_id, EntityState.MOUNTED),
            ],
            "tube_rack mounted",
        )

        updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_tube_rack_update(params.tube_rack_location_id, params.work_station_id, EntityState.MOUNTED),
        ]
        return RobotResult(code=200, msg="setup_tube_rack completed", task_id=task_id, updates=updates)

    async def _simulate_collapse_cartridges(self, task_id: str, params: CollapseCartridgesParams) -> RobotResult:
        """Simulate collapse_cartridges: 10-15s delay."""
        logger.info("Simulating collapse_cartridges for task {}", task_id)
        await self._apply_delay(10.0, 15.0)

        updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_silica_cartridge_update(params.silica_cartridge_id, params.work_station_id, EntityState.USED),
            create_sample_cartridge_update(params.sample_cartridge_id, params.work_station_id, EntityState.USED),
            create_ccs_ext_module_update(params.work_station_id, EntityState.USED),
        ]
        return RobotResult(code=200, msg="collapse_cartridges completed", task_id=task_id, updates=updates)
