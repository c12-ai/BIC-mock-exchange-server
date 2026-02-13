"""Simulator for collect_column_chromatography_fractions task."""

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
from src.schemas.commands import DeviceState, RobotState, TaskType, ToolState
from src.schemas.protocol import ContainerContentState, ContainerState, Substance, SubstanceUnit
from src.schemas.results import RobotResult
from src.simulators.base import BaseSimulator

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.schemas.commands import CollectCCFractionsParams


class ConsolidationSimulator(BaseSimulator):
    """Handles collect_column_chromatography_fractions task."""

    async def simulate(self, task_id: str, task_type: TaskType, params: BaseModel) -> RobotResult:
        if task_type != TaskType.COLLECT_CC_FRACTIONS:
            raise ValueError(f"ConsolidationSimulator cannot handle task: {task_type}")
        return await self._simulate_consolidation(task_id, params)  # type: ignore[arg-type]

    async def _simulate_consolidation(self, task_id: str, params: CollectCCFractionsParams) -> RobotResult:
        """Simulate collect_column_chromatography_fractions: timing scales with collect_config tube count."""
        tubes_to_collect = sum(1 for v in params.collect_config if v == 1)
        base_delay = tubes_to_collect * 3.0 + 10.0
        logger.info("Simulating collect_cc_fractions for task {} ({} tubes)", task_id, tubes_to_collect)

        # Resolve material IDs from WorldState
        tube_rack_id = self._resolve_entity_id("tube_rack", params.work_station)

        # TODO: Robot get a flask from somewhere and return its ID and state to Lab Server
        flask_id = "rbf_001"

        # Log: robot pulling out tube rack
        await self._publish_log(
            task_id,
            [
                create_robot_update(self.robot_id, params.work_station, RobotState.WORKING),
                create_tube_rack_update(
                    tube_rack_id, params.work_station, ToolState.CONTAMINATED, description="pulled_out"
                ),
            ],
            "robot pulling out tube rack",
        )

        await self._apply_delay(base_delay * 0.8, base_delay * 1.2)

        # Build ContainerState for flask
        flask_state = ContainerState(
            content_state=ContainerContentState.FILL,
            has_lid=False,
            lid_state=None,
            substance=Substance(name="", zh_name="", unit=SubstanceUnit.ML, amount=0.0),
        )

        # TODO: How the chute IDs get is not determined yet. Somehow get. left to Robot Team

        left_chute_id = "pcc_left_chute_001"
        right_chute_id = "pcc_right_chute_001"

        # Log: robot pulling out tube rack

        updates = [
            create_robot_update(self.robot_id, params.work_station, RobotState.IDLE),
            create_tube_rack_update(
                tube_rack_id,
                params.work_station,
                ToolState.CONTAMINATED,
                description="pulled_out, ready_for_recovery",
            ),
            create_round_bottom_flask_update(flask_id, params.work_station, flask_state),
            create_pcc_left_chute_update(chute_id=left_chute_id, state=DeviceState.USING),
            create_pcc_right_chute_update(chute_id=right_chute_id, state=DeviceState.USING),
        ]

        return RobotResult(code=200, msg="success", task_id=task_id, updates=updates)
