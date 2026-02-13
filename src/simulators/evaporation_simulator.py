"""Simulator for start_evaporation task (long-running with sensor ramp)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from src.generators.entity_updates import (
    create_evaporator_update,
    create_robot_update,
    create_round_bottom_flask_update,
)
from src.generators.timing import calculate_evaporation_duration, calculate_intermediate_interval
from src.schemas.commands import DeviceState, RobotPosture, RobotState, TaskType
from src.schemas.protocol import ContainerContentState, ContainerState, Substance, SubstanceUnit
from src.schemas.results import RobotResult
from src.simulators.base import BaseSimulator

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.schemas.commands import StartEvaporationParams


class EvaporationSimulator(BaseSimulator):
    """Handles start_evaporation (long-running with intermediate updates showing sensor ramp)."""

    async def simulate(self, task_id: str, task_type: TaskType, params: BaseModel) -> RobotResult:
        if task_type != TaskType.START_EVAPORATION:
            raise ValueError(f"EvaporationSimulator cannot handle task: {task_type}")
        return await self._simulate_start_evaporation(task_id, params)  # type: ignore[arg-type]

    async def _simulate_start_evaporation(self, task_id: str, params: StartEvaporationParams) -> RobotResult:
        """LONG-RUNNING: Simulate evaporation with temperature/pressure ramp."""
        start_profile = params.profiles.start
        target_temp = start_profile.target_temperature
        target_pressure = start_profile.target_pressure
        lower_height = start_profile.lower_height
        rpm = start_profile.rpm

        logger.info(
            "Simulating start_evaporation for task {} (target_temp={}, target_pressure={})",
            task_id,
            target_temp,
            target_pressure,
        )

        # Log: robot moving to evaporation station
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station, RobotState.WORKING),
            ],
            "robot moving to evaporation station",
        )

        # 1. Short initial delay
        await self._apply_delay(3.0, 5.0)

        # 2. Publish initial intermediate updates (ambient values)
        initial_temp = 25.0  # Ambient
        initial_pressure = 1013.0  # Ambient

        # TODO: How the flask_id gets is not determined yet.
        # flask_id = self._resolve_entity_id("round_bottom_flask", params.work_station)
        flask_id = "rbf_001"

        flask_state = ContainerState(
            content_state=ContainerContentState.FILL,
            has_lid=False,
            lid_state=None,
            substance=Substance(name="", zh_name="", unit=SubstanceUnit.ML, amount=0.0),
        )

        initial_updates = [
            create_robot_update(
                self.robot_id,
                params.work_station,
                RobotState.WORKING,
                description=RobotPosture.OBSERVE_EVAPORATION,
            ),
            create_evaporator_update(
                params.device_id,
                state=DeviceState.USING,
                lower_height=lower_height,
                rpm=rpm,
                target_temperature=target_temp,
                current_temperature=initial_temp,
                target_pressure=target_pressure,
                current_pressure=initial_pressure,
            ),
            create_round_bottom_flask_update(flask_id, params.work_station, flask_state, description="evaporating"),
        ]
        # Log: evaporation started with initial sensor values
        await self._publish_log(task_id, initial_updates, "evaporation started")

        # 3. Calculate duration
        profiles_dict = params.profiles.model_dump()
        total_duration = calculate_evaporation_duration(profiles_dict, self.multiplier)
        interval = calculate_intermediate_interval(total_duration)
        elapsed = 0.0

        # 4. Ramp temperature and pressure toward targets
        while elapsed < total_duration:
            sleep_time = min(interval, total_duration - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time

            # Linear interpolation toward target
            progress = min(elapsed / total_duration, 1.0)
            current_temp = initial_temp + (target_temp - initial_temp) * progress
            current_pressure = initial_pressure + (target_pressure - initial_pressure) * progress

            if elapsed < total_duration:
                ramp_updates = [
                    create_evaporator_update(
                        params.device_id,
                        state=DeviceState.USING,
                        lower_height=lower_height,
                        rpm=rpm,
                        target_temperature=target_temp,
                        current_temperature=round(current_temp, 1),
                        target_pressure=target_pressure,
                        current_pressure=round(current_pressure, 1),
                    ),
                ]
                await self._publish_log(task_id, ramp_updates, "evaporation ramp in progress")
                logger.debug(
                    "Evaporation progress task {}: {:.0f}/{:.0f}s, temp={:.1f}/{:.1f}, pressure={:.1f}/{:.1f}",
                    task_id,
                    elapsed,
                    total_duration,
                    current_temp,
                    target_temp,
                    current_pressure,
                    target_pressure,
                )

        # 4b. Apply updates from profiles.updates if provided
        if params.profiles.updates:
            lp = params.profiles.updates[0]
            target_temp = lp.target_temperature
            target_pressure = lp.target_pressure
            lower_height = lp.lower_height
            rpm = lp.rpm
            logger.debug(
                "Applied profile update: target_temp={}, target_pressure={}, lower_height={}, rpm={}",
                target_temp,
                target_pressure,
                lower_height,
                rpm,
            )

        # 5. Final result -- at target values, state=idle
        final_updates = [
            create_robot_update(self.robot_id, params.work_station, RobotState.IDLE),
            create_evaporator_update(
                params.device_id,
                state=DeviceState.IDLE,
                lower_height=lower_height,
                rpm=0,
                target_temperature=target_temp,
                current_temperature=target_temp,
                target_pressure=target_pressure,
                current_pressure=target_pressure,
            ),
        ]
        logger.info("Evaporation simulation complete for task {} ({:.0f}s)", task_id, total_duration)
        return RobotResult(code=200, msg="success", task_id=task_id, updates=final_updates)
