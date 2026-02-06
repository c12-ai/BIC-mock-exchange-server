"""Simulator for column chromatography tasks.

Handles two task types:
- start_column_chromatography (LONG-RUNNING): sends periodic intermediate updates
  while the CC process runs, then publishes a final result.
- terminate_column_chromatography (QUICK): stops the process and returns screen captures.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from src.generators.entity_updates import (
    create_cc_system_update,
    create_ccs_ext_module_update,
    create_robot_update,
    create_sample_cartridge_update,
    create_silica_cartridge_update,
    create_tube_rack_update,
    generate_robot_timestamp,
)
from src.generators.images import generate_captured_images
from src.generators.timing import calculate_cc_duration, calculate_intermediate_interval
from src.schemas.commands import EntityState, RobotState, TaskName
from src.schemas.results import EntityUpdate, RobotResult
from src.simulators.base import BaseSimulator

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.schemas.commands import StartCCParams, TerminateCCParams


class CCSimulator(BaseSimulator):
    """Handles start_column_chromatography (long-running) and terminate_column_chromatography (quick)."""

    async def simulate(self, task_id: str, task_name: TaskName, params: BaseModel) -> RobotResult:
        match task_name:
            case TaskName.START_CC:
                return await self._simulate_start_cc(task_id, params)  # type: ignore[arg-type]
            case TaskName.TERMINATE_CC:
                return await self._simulate_terminate_cc(task_id, params)  # type: ignore[arg-type]
            case _:
                raise ValueError(f"CCSimulator cannot handle task: {task_name}")

    # ------------------------------------------------------------------
    # start_column_chromatography — LONG-RUNNING
    # ------------------------------------------------------------------

    async def _simulate_start_cc(self, task_id: str, params: StartCCParams) -> RobotResult:
        """Simulate start_column_chromatography with intermediate updates.

        Flow:
        1. Short initial delay (robot navigating to station).
        2. Publish initial entity state changes (robot watching, CC running, materials in use).
        3. Sleep in intervals, publishing periodic progress updates.
        4. Return final result with updated entity states.
        """
        logger.info("Simulating start_cc for task {} (run_minutes={})", task_id, params.experiment_params.run_minutes)

        # 1. Short initial delay — robot moving to work station
        # Log: robot moving to CC station
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "moving"),
            ],
            "robot moving to CC station",
        )

        await self._apply_delay(3.0, 5.0)

        # 2. Publish initial intermediate updates
        start_timestamp = generate_robot_timestamp()
        experiment_params_dict = params.experiment_params.model_dump()

        # Resolve material IDs from WorldState (setup tasks tracked them earlier)
        silica_id = self._resolve_entity_id("silica_cartridge", params.work_station_id)
        sample_id = self._resolve_entity_id("sample_cartridge", params.work_station_id)
        tube_rack_id = self._resolve_entity_id("tube_rack", params.work_station_id)

        initial_updates = [
            create_robot_update(self.robot_id, params.work_station_id, RobotState.WATCH_CC_SCREEN),
            create_cc_system_update(
                params.device_id,
                EntityState.RUNNING,
                experiment_params=experiment_params_dict,
                start_timestamp=start_timestamp,
            ),
            create_silica_cartridge_update(silica_id, params.work_station_id, EntityState.USING),
            create_sample_cartridge_update(sample_id, params.work_station_id, EntityState.USING),
            create_tube_rack_update(tube_rack_id, params.work_station_id, EntityState.USING),
        ]
        await self._producer.publish_intermediate_update(task_id, initial_updates)

        # Log: CC process started with all initial state changes
        await self._publish_log(task_id, initial_updates, "CC process started")

        # 3. Calculate total duration and interval
        total_duration = calculate_cc_duration(params.experiment_params.run_minutes, self.multiplier)
        interval = calculate_intermediate_interval(total_duration)
        elapsed = 0.0

        # 4. Publish periodic progress updates
        while elapsed < total_duration:
            sleep_time = min(interval, total_duration - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time

            if elapsed < total_duration:
                progress_updates: list[EntityUpdate] = [
                    create_cc_system_update(params.device_id, EntityState.RUNNING),
                ]
                await self._producer.publish_intermediate_update(task_id, progress_updates)
                await self._publish_log(task_id, progress_updates, "CC in progress")
                logger.debug("CC progress for task {}: {:.0f}/{:.0f}s", task_id, elapsed, total_duration)

        # 5. Final result
        final_updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_cc_system_update(params.device_id, EntityState.RUNNING),
        ]
        logger.info("CC simulation complete for task {} ({:.0f}s)", task_id, total_duration)
        return RobotResult(code=0, msg="start_column_chromatography completed", task_id=task_id, updates=final_updates)

    # ------------------------------------------------------------------
    # terminate_column_chromatography — QUICK
    # ------------------------------------------------------------------

    async def _simulate_terminate_cc(self, task_id: str, params: TerminateCCParams) -> RobotResult:
        """Simulate terminate_column_chromatography with result images.

        Flow:
        1. Short delay (robot pressing stop, capturing screen).
        2. Retrieve experiment context from world_state (if available).
        3. Build entity updates — CC terminated, materials marked used, ext_module marked used.
        4. Generate mock screen capture images.
        5. Return final result.
        """
        logger.info("Simulating terminate_cc for task {}", task_id)

        # Log: robot terminating CC
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "terminating_cc"),
                create_cc_system_update(params.device_id, EntityState.RUNNING),
            ],
            "robot terminating CC",
        )

        await self._apply_delay(5.0, 10.0)

        # Retrieve experiment context from world_state if available
        experiment_params = None
        start_timestamp = None
        if self._world_state is not None:
            device_entity = self._world_state.get_entity("column_chromatography_system", params.device_id)
            if device_entity is not None:
                experiment_params = device_entity.get("experiment_params")
                start_timestamp = device_entity.get("start_timestamp")
                logger.debug(
                    "Retrieved experiment context for device {}: experiment_params={}, start_timestamp={}",
                    params.device_id,
                    experiment_params is not None,
                    start_timestamp,
                )

        # Resolve material IDs from WorldState
        silica_id = self._resolve_entity_id("silica_cartridge", params.work_station_id)
        sample_id = self._resolve_entity_id("sample_cartridge", params.work_station_id)
        tube_rack_id = self._resolve_entity_id("tube_rack", params.work_station_id)

        updates = [
            create_robot_update(self.robot_id, params.work_station_id, params.end_state),
            create_cc_system_update(
                params.device_id,
                EntityState.TERMINATED,
                experiment_params=experiment_params,
                start_timestamp=start_timestamp,
            ),
            create_silica_cartridge_update(silica_id, params.work_station_id, EntityState.USED),
            create_sample_cartridge_update(sample_id, params.work_station_id, EntityState.USED),
            create_tube_rack_update(tube_rack_id, params.work_station_id, EntityState.USED),
            create_ccs_ext_module_update(params.work_station_id, EntityState.USED),
        ]

        # Log: CC terminated, materials used
        await self._publish_log(task_id, updates, "CC terminated, materials used")

        images = generate_captured_images(
            self.image_base_url, params.work_station_id, params.device_id, params.device_type, "screen"
        )

        return RobotResult(
            code=0, msg="terminate_column_chromatography completed", task_id=task_id, updates=updates, images=images
        )
