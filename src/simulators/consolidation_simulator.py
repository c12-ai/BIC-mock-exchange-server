"""Simulator for fraction_consolidation task."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.generators.entity_updates import (
    create_pcc_left_chute_update,
    create_pcc_right_chute_update,
    create_robot_update,
    create_round_bottom_flask_update,
    create_tube_rack_update,
)
from src.schemas.commands import RobotState, TaskName
from src.schemas.results import RobotResult
from src.simulators.base import BaseSimulator

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.schemas.commands import FractionConsolidationParams


class ConsolidationSimulator(BaseSimulator):
    """Handles fraction_consolidation task."""

    async def simulate(self, task_id: str, task_name: TaskName, params: BaseModel) -> RobotResult:
        if task_name != TaskName.FRACTION_CONSOLIDATION:
            raise ValueError(f"ConsolidationSimulator cannot handle task: {task_name}")
        return await self._simulate_consolidation(task_id, params)  # type: ignore[arg-type]

    async def _simulate_consolidation(self, task_id: str, params: FractionConsolidationParams) -> RobotResult:
        """Simulate fraction_consolidation: timing scales with collect_config tube count."""
        tubes_to_collect = sum(1 for v in params.collect_config if v == 1)
        base_delay = tubes_to_collect * 3.0 + 10.0
        logger.info("Simulating fraction_consolidation for task {} ({} tubes)", task_id, tubes_to_collect)

        # Log: robot pulling out tube rack
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station_id, "pulling_out_tube_rack"),
                create_tube_rack_update(params.work_station_id, params.work_station_id, "used,pulled_out"),
            ],
            "robot pulling out tube rack",
        )

        await self._apply_delay(base_delay * 0.8, base_delay * 1.2)

        updates = [
            create_robot_update(self.robot_id, params.work_station_id, RobotState.MOVING_WITH_FLASK),
            create_tube_rack_update(
                params.work_station_id, params.work_station_id, "used,pulled_out,ready_for_recovery"
            ),
            create_round_bottom_flask_update(
                params.work_station_id, params.work_station_id, "used,ready_for_evaporate"
            ),
            create_pcc_left_chute_update(params.work_station_id),
            create_pcc_right_chute_update(params.work_station_id),
        ]

        # Log: consolidation complete
        await self._publish_log(task_id, updates, "consolidation complete")

        return RobotResult(code=0, msg="fraction_consolidation completed", task_id=task_id, updates=updates)
