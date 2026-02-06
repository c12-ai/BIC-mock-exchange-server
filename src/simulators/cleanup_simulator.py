"""Simulator for cleanup/teardown tasks: stop_evaporation, setup_ccs_bins, return_ccs_bins, return_cartridges, return_tube_rack."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.generators.entity_updates import (
    create_ccs_ext_module_update,
    create_evaporator_update,
    create_pcc_left_chute_update,
    create_pcc_right_chute_update,
    create_robot_update,
    create_round_bottom_flask_update,
    create_sample_cartridge_update,
    create_silica_cartridge_update,
    create_tube_rack_update,
)
from src.schemas.commands import EntityState, TaskName
from src.schemas.results import RobotResult
from src.simulators.base import BaseSimulator

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.schemas.commands import (
        ReturnCartridgesParams,
        ReturnCCSBinsParams,
        ReturnTubeRackParams,
        SetupCCSBinsParams,
        StopEvaporationParams,
    )


class CleanupSimulator(BaseSimulator):
    """Handles stop_evaporation, setup_ccs_bins, return_ccs_bins, return_cartridges, return_tube_rack."""

    async def simulate(self, task_id: str, task_name: TaskName, params: BaseModel) -> RobotResult:
        """Route to the appropriate cleanup handler."""
        match task_name:
            case TaskName.STOP_EVAPORATION:
                return await self._simulate_stop_evaporation(task_id, params)  # type: ignore[arg-type]
            case TaskName.SETUP_CCS_BINS:
                return await self._simulate_setup_ccs_bins(task_id, params)  # type: ignore[arg-type]
            case TaskName.RETURN_CCS_BINS:
                return await self._simulate_return_ccs_bins(task_id, params)  # type: ignore[arg-type]
            case TaskName.RETURN_CARTRIDGES:
                return await self._simulate_return_cartridges(task_id, params)  # type: ignore[arg-type]
            case TaskName.RETURN_TUBE_RACK:
                return await self._simulate_return_tube_rack(task_id, params)  # type: ignore[arg-type]
            case _:
                raise ValueError(f"CleanupSimulator cannot handle task: {task_name}")

    async def _simulate_stop_evaporation(self, task_id: str, params: StopEvaporationParams) -> RobotResult:
        """Simulate stop_evaporation: 15-30s delay."""
        logger.info("Simulating stop_evaporation for task {}", task_id)

        # Log: robot moving to evaporation station
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "moving"),
            ],
            "robot moving to evaporation station",
        )

        await self._apply_delay(15.0, 30.0)

        # Log: evaporator stopped, flask ready
        updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_evaporator_update(
                params.device_id,
                running=False,
                lower_height=0.0,
                rpm=0,
                target_temperature=25.0,
                current_temperature=25.0,
                target_pressure=1013.0,
                current_pressure=1013.0,
            ),
            create_round_bottom_flask_update(
                params.work_station_id, params.work_station_id, "used,evaporation_complete"
            ),
        ]
        await self._publish_log(task_id, updates, "evaporation stopped")

        return RobotResult(code=0, msg="stop_evaporation completed", task_id=task_id, updates=updates)

    async def _simulate_setup_ccs_bins(self, task_id: str, params: SetupCCSBinsParams) -> RobotResult:
        """Simulate setup_ccs_bins: 10-20s delay."""
        logger.info("Simulating setup_ccs_bins for task {}", task_id)

        # Log: robot moving to bin storage
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "moving"),
            ],
            "robot moving to bin storage",
        )

        await self._apply_delay(10.0, 20.0)

        # Log: bins placed in chutes
        updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_pcc_left_chute_update(
                params.work_station_id,
                front_waste_bin="open",
                back_waste_bin=None,
            ),
            create_pcc_right_chute_update(
                params.work_station_id,
                front_waste_bin=None,
                back_waste_bin="open",
            ),
        ]
        await self._publish_log(task_id, updates, "bins placed in chutes")

        return RobotResult(code=0, msg="setup_ccs_bins completed", task_id=task_id, updates=updates)

    async def _simulate_return_ccs_bins(self, task_id: str, params: ReturnCCSBinsParams) -> RobotResult:
        """Simulate return_ccs_bins: 10-20s delay."""
        logger.info("Simulating return_ccs_bins for task {}", task_id)

        # Log: robot removing bins from chutes
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "moving"),
            ],
            "robot removing bins from chutes",
        )

        await self._apply_delay(10.0, 20.0)

        # Log: bins cleared from chutes
        updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_pcc_left_chute_update(
                params.work_station_id,
                pulled_out_mm=0.0,
                pulled_out_rate=0.0,
                closed=True,
                front_waste_bin=None,
                back_waste_bin=None,
            ),
            create_pcc_right_chute_update(
                params.work_station_id,
                pulled_out_mm=0.0,
                pulled_out_rate=0.0,
                closed=True,
                front_waste_bin=None,
                back_waste_bin=None,
            ),
        ]
        await self._publish_log(task_id, updates, "bins returned to waste area")

        return RobotResult(code=0, msg="return_ccs_bins completed", task_id=task_id, updates=updates)

    async def _simulate_return_cartridges(self, task_id: str, params: ReturnCartridgesParams) -> RobotResult:
        """Simulate return_cartridges: 10-20s delay."""
        logger.info("Simulating return_cartridges for task {}", task_id)

        # Log: robot removing cartridges
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "moving"),
            ],
            "robot removing cartridges from mount",
        )

        await self._apply_delay(10.0, 20.0)

        # Log: cartridges returned
        updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_silica_cartridge_update(params.silica_cartridge_id, params.waste_area_id, "returned"),
            create_sample_cartridge_update(params.sample_cartridge_id, params.waste_area_id, "returned"),
            create_ccs_ext_module_update(params.work_station_id, EntityState.AVAILABLE),
        ]
        await self._publish_log(task_id, updates, "cartridges returned to waste area")

        return RobotResult(code=0, msg="return_cartridges completed", task_id=task_id, updates=updates)

    async def _simulate_return_tube_rack(self, task_id: str, params: ReturnTubeRackParams) -> RobotResult:
        """Simulate return_tube_rack: 10-20s delay."""
        logger.info("Simulating return_tube_rack for task {}", task_id)

        # Log: robot picking up tube rack
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "moving"),
            ],
            "robot picking up tube rack",
        )

        await self._apply_delay(10.0, 20.0)

        # Log: tube rack returned
        updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_tube_rack_update(params.tube_rack_id, params.waste_area_id, "returned"),
        ]
        await self._publish_log(task_id, updates, "tube rack returned to waste area")

        return RobotResult(code=0, msg="return_tube_rack completed", task_id=task_id, updates=updates)
