"""Precondition checker for tasks based on current world state.

Validates that required entities exist and are in valid states before
skill execution begins. Returns error codes in 2000-2099 range for violations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic import BaseModel

if TYPE_CHECKING:
    from src.schemas.commands import TaskType
    from src.state.world_state import WorldState


class PreconditionResult(BaseModel):
    """Result of a precondition check."""

    ok: bool
    error_code: int = 0
    error_msg: str = ""


class PreconditionChecker:
    """Validates task preconditions against current world state.

    Checks that required entities exist and are in appropriate states
    before a task begins execution.
    """

    def __init__(self, world_state: WorldState) -> None:
        """Initialize precondition checker.

        Args:
            world_state: World state to check against
        """
        self._world_state = world_state

    def _find_entity_at_location(self, entity_type: str, location: str) -> tuple[str, dict[str, Any]] | None:
        """Find an entity by type whose ``location`` property matches.

        Some entities (tube_rack, round_bottom_flask) are keyed in WorldState
        by their location_id string rather than by work_station_id.  This
        helper searches all entities of the given type for one located at
        ``location``.

        Returns:
            (entity_id, properties) tuple, or None if not found.
        """
        entities = self._world_state.get_entities_by_type(entity_type)
        for entity_id, props in entities.items():
            if props.get("location") == location:
                return entity_id, props
        return None

    def check(self, task_type: TaskType, params: BaseModel) -> PreconditionResult:
        """Check if preconditions are met for a task.

        Args:
            task_type: Task to validate
            params: Validated task parameters

        Returns:
            PreconditionResult with ok=True if checks pass, ok=False with error otherwise
        """
        # Import here to avoid circular dependency
        from src.schemas.commands import TaskType

        match task_type:
            case TaskType.SETUP_CARTRIDGES:
                return self._check_setup_cartridges(params)
            case TaskType.START_CC:
                return self._check_start_cc(params)
            case TaskType.TERMINATE_CC:
                return self._check_terminate_cc(params)
            case TaskType.COLLECT_CC_FRACTIONS:
                return self._check_collect_cc_fractions(params)
            case TaskType.START_EVAPORATION:
                return self._check_start_evaporation(params)
            case _:
                # Tasks with no meaningful preconditions (take_photo, setup_tube_rack)
                return PreconditionResult(ok=True)

    # --- Precondition implementations ---

    def _check_setup_cartridges(self, params: BaseModel) -> PreconditionResult:
        """Check setup_cartridges: ext_module must not already be in use."""
        work_station = getattr(params, "work_station", None)
        if work_station is None:
            return PreconditionResult(ok=True)  # No work station to check

        ext_module = self._world_state.get_entity("ccs_ext_module", work_station)

        if ext_module is not None:
            state = ext_module.get("state", "")
            if state in ("using", "mounted", "inuse"):
                logger.warning(
                    "Precondition failed for setup_cartridges: ext_module {} already in state '{}'",
                    work_station,
                    state,
                )
                return PreconditionResult(
                    ok=False,
                    error_code=2001,
                    error_msg=f"External module {work_station} already has cartridges (state: {state})",
                )

        return PreconditionResult(ok=True)

    def _check_start_cc(self, params: BaseModel) -> PreconditionResult:
        """Check start_cc: CC system must not already be running."""
        device_id = getattr(params, "device_id", None)
        if device_id is None:
            return PreconditionResult(ok=True)

        cc_system = self._world_state.get_entity("column_chromatography_machine", device_id)
        if cc_system is not None:
            state = cc_system.get("state", "")
            if state in ("running", "using"):
                logger.warning("Precondition failed for start_cc: CC machine {} already in use ({})", device_id, state)
                return PreconditionResult(
                    ok=False,
                    error_code=2020,
                    error_msg=f"Column chromatography machine {device_id} is already in use (state: {state})",
                )

        return PreconditionResult(ok=True)

    def _check_terminate_cc(self, params: BaseModel) -> PreconditionResult:
        """Check terminate_cc: CC system must be in use."""
        device_id = getattr(params, "device_id", None)
        if device_id is None:
            return PreconditionResult(ok=True)

        cc_system = self._world_state.get_entity("column_chromatography_machine", device_id)
        if cc_system is None:
            logger.warning("Precondition failed for terminate_cc: CC machine {} not found", device_id)
            return PreconditionResult(
                ok=False,
                error_code=2030,
                error_msg=f"Column chromatography machine {device_id} not found in world state",
            )

        state = cc_system.get("state", "")
        if state not in ("running", "using"):
            logger.warning(
                "Precondition failed for terminate_cc: CC machine {} in state '{}', expected 'using'",
                device_id,
                state,
            )
            return PreconditionResult(
                ok=False,
                error_code=2031,
                error_msg=f"Column chromatography machine {device_id} is not in use (current state: {state})",
            )

        return PreconditionResult(ok=True)

    def _check_collect_cc_fractions(self, params: BaseModel) -> PreconditionResult:
        """Check collect_cc_fractions: tube_rack must exist and be in use or contaminated."""
        work_station = getattr(params, "work_station", None)
        if work_station is None:
            return PreconditionResult(ok=True)

        # Try direct lookup first, then fall back to location-based search.
        # tube_rack entities are keyed by location_id (e.g. "bic_09C_l3_002"),
        # not by work_station.
        tube_rack = self._world_state.get_entity("tube_rack", work_station)
        if tube_rack is None:
            result = self._find_entity_at_location("tube_rack", work_station)
            if result is not None:
                _, tube_rack = result

        if tube_rack is None:
            logger.warning("Precondition failed for collect_cc_fractions: tube_rack at {} not found", work_station)
            return PreconditionResult(
                ok=False,
                error_code=2040,
                error_msg=f"Tube rack at work station {work_station} not found in world state",
            )

        state = tube_rack.get("state", "")
        # Accept "used", "using", "inuse", "contaminated" and compound states
        valid_states = ("used", "using", "inuse", "contaminated")
        if not any(s in state for s in valid_states):
            logger.warning(
                "Precondition failed for collect_cc_fractions: tube_rack at {} state '{}', need valid state",
                work_station,
                state,
            )
            return PreconditionResult(
                ok=False,
                error_code=2041,
                error_msg=f"Tube rack at {work_station} must be in use (current: {state})",
            )

        return PreconditionResult(ok=True)

    def _check_start_evaporation(self, params: BaseModel) -> PreconditionResult:
        """Check start_evaporation: evaporator must not already be in use."""
        device_id = getattr(params, "device_id", None)
        if device_id is None:
            return PreconditionResult(ok=True)

        evaporator = self._world_state.get_entity("evaporator", device_id)
        if evaporator is not None:
            state = evaporator.get("state", "idle")
            if state == "using":
                logger.warning("Precondition failed for start_evaporation: evaporator {} already in use", device_id)
                return PreconditionResult(
                    ok=False,
                    error_code=2050,
                    error_msg=f"Evaporator {device_id} is already in use",
                )

        return PreconditionResult(ok=True)
