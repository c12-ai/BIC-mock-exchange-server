"""Precondition checker for tasks based on current world state.

Validates that required entities exist and are in valid states before
skill execution begins. Returns error codes in 2000-2099 range for violations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic import BaseModel

if TYPE_CHECKING:
    from src.schemas.commands import TaskName
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

    def check(self, task_name: TaskName, params: BaseModel) -> PreconditionResult:
        """Check if preconditions are met for a task.

        Args:
            task_name: Task to validate
            params: Validated task parameters

        Returns:
            PreconditionResult with ok=True if checks pass, ok=False with error otherwise
        """
        # Import here to avoid circular dependency
        from src.schemas.commands import TaskName

        match task_name:
            case TaskName.SETUP_CARTRIDGES:
                return self._check_setup_cartridges(params)
            case TaskName.COLLAPSE_CARTRIDGES:
                return self._check_collapse_cartridges(params)
            case TaskName.START_CC:
                return self._check_start_cc(params)
            case TaskName.TERMINATE_CC:
                return self._check_terminate_cc(params)
            case TaskName.FRACTION_CONSOLIDATION:
                return self._check_fraction_consolidation(params)
            case TaskName.START_EVAPORATION:
                return self._check_start_evaporation(params)
            case TaskName.STOP_EVAPORATION:
                return self._check_stop_evaporation(params)
            case TaskName.RETURN_CCS_BINS:
                return self._check_return_ccs_bins(params)
            case TaskName.RETURN_CARTRIDGES:
                return self._check_return_cartridges(params)
            case TaskName.RETURN_TUBE_RACK:
                return self._check_return_tube_rack(params)
            case _:
                # Tasks with no meaningful preconditions (take_photo, setup_tube_rack, setup_ccs_bins)
                return PreconditionResult(ok=True)

    # --- Precondition implementations ---

    def _check_setup_cartridges(self, params: BaseModel) -> PreconditionResult:
        """Check setup_cartridges: ext_module must not already be in use."""
        work_station_id = getattr(params, "work_station_id", None)
        if work_station_id is None:
            return PreconditionResult(ok=True)  # No work station to check

        ext_module = self._world_state.get_entity("ccs_ext_module", work_station_id)

        if ext_module is not None:
            state = ext_module.get("state", "")
            if state in ("using", "mounted"):
                logger.warning(
                    "Precondition failed for setup_cartridges: ext_module {} already in state '{}'",
                    work_station_id,
                    state,
                )
                return PreconditionResult(
                    ok=False,
                    error_code=2001,
                    error_msg=f"External module {work_station_id} already has cartridges (state: {state})",
                )

        return PreconditionResult(ok=True)

    def _check_collapse_cartridges(self, params: BaseModel) -> PreconditionResult:
        """Check collapse_cartridges: silica and sample cartridges must exist and be 'used'."""
        silica_id = getattr(params, "silica_cartridge_id", None)
        sample_id = getattr(params, "sample_cartridge_id", None)

        if silica_id is None or sample_id is None:
            return PreconditionResult(ok=True)  # Can't validate without IDs

        # Check silica cartridge
        silica = self._world_state.get_entity("silica_cartridge", silica_id)
        if silica is None:
            logger.warning("Precondition failed for collapse_cartridges: silica_cartridge {} not found", silica_id)
            return PreconditionResult(
                ok=False,
                error_code=2010,
                error_msg=f"Silica cartridge {silica_id} not found in world state",
            )

        silica_state = silica.get("state", "")
        if silica_state != "used":
            logger.warning(
                "Precondition failed for collapse_cartridges: silica_cartridge {} in state '{}', expected 'used'",
                silica_id,
                silica_state,
            )
            return PreconditionResult(
                ok=False,
                error_code=2011,
                error_msg=f"Silica cartridge {silica_id} must be in 'used' state (current: {silica_state})",
            )

        # Check sample cartridge
        sample = self._world_state.get_entity("sample_cartridge", sample_id)
        if sample is None:
            logger.warning("Precondition failed for collapse_cartridges: sample_cartridge {} not found", sample_id)
            return PreconditionResult(
                ok=False,
                error_code=2012,
                error_msg=f"Sample cartridge {sample_id} not found in world state",
            )

        sample_state = sample.get("state", "")
        if sample_state != "used":
            logger.warning(
                "Precondition failed for collapse_cartridges: sample_cartridge {} in state '{}', expected 'used'",
                sample_id,
                sample_state,
            )
            return PreconditionResult(
                ok=False,
                error_code=2013,
                error_msg=f"Sample cartridge {sample_id} must be in 'used' state (current: {sample_state})",
            )

        return PreconditionResult(ok=True)

    def _check_start_cc(self, params: BaseModel) -> PreconditionResult:
        """Check start_cc: CC system must not already be running."""
        device_id = getattr(params, "device_id", None)
        if device_id is None:
            return PreconditionResult(ok=True)

        cc_system = self._world_state.get_entity("column_chromatography_system", device_id)
        if cc_system is not None:
            state = cc_system.get("state", "")
            if state == "running":
                logger.warning("Precondition failed for start_cc: CC system {} already running", device_id)
                return PreconditionResult(
                    ok=False,
                    error_code=2020,
                    error_msg=f"Column chromatography system {device_id} is already running",
                )

        return PreconditionResult(ok=True)

    def _check_terminate_cc(self, params: BaseModel) -> PreconditionResult:
        """Check terminate_cc: CC system must be running."""
        device_id = getattr(params, "device_id", None)
        if device_id is None:
            return PreconditionResult(ok=True)

        cc_system = self._world_state.get_entity("column_chromatography_system", device_id)
        if cc_system is None:
            logger.warning("Precondition failed for terminate_cc: CC system {} not found", device_id)
            return PreconditionResult(
                ok=False,
                error_code=2030,
                error_msg=f"Column chromatography system {device_id} not found in world state",
            )

        state = cc_system.get("state", "")
        if state != "running":
            logger.warning(
                "Precondition failed for terminate_cc: CC system {} in state '{}', expected 'running'",
                device_id,
                state,
            )
            return PreconditionResult(
                ok=False,
                error_code=2031,
                error_msg=f"Column chromatography system {device_id} is not running (current state: {state})",
            )

        return PreconditionResult(ok=True)

    def _check_fraction_consolidation(self, params: BaseModel) -> PreconditionResult:
        """Check fraction_consolidation: tube_rack must exist and be 'used' or similar."""
        work_station_id = getattr(params, "work_station_id", None)
        if work_station_id is None:
            return PreconditionResult(ok=True)

        # Try direct lookup first, then fall back to location-based search.
        # tube_rack entities are keyed by location_id (e.g. "bic_09C_l3_002"),
        # not by work_station_id.
        tube_rack = self._world_state.get_entity("tube_rack", work_station_id)
        if tube_rack is None:
            result = self._find_entity_at_location("tube_rack", work_station_id)
            if result is not None:
                _, tube_rack = result

        if tube_rack is None:
            logger.warning("Precondition failed for fraction_consolidation: tube_rack at {} not found", work_station_id)
            return PreconditionResult(
                ok=False,
                error_code=2040,
                error_msg=f"Tube rack at work station {work_station_id} not found in world state",
            )

        state = tube_rack.get("state", "")
        # Accept "used" or compound states like "used,pulled_out"
        if "used" not in state and "using" not in state:
            logger.warning(
                "Precondition failed for fraction_consolidation: tube_rack at {} state '{}', need 'used'/'using'",
                work_station_id,
                state,
            )
            return PreconditionResult(
                ok=False,
                error_code=2041,
                error_msg=f"Tube rack at {work_station_id} must be in 'used' or 'using' state (current: {state})",
            )

        return PreconditionResult(ok=True)

    def _check_start_evaporation(self, params: BaseModel) -> PreconditionResult:
        """Check start_evaporation: evaporator must not already be running."""
        device_id = getattr(params, "device_id", None)
        if device_id is None:
            return PreconditionResult(ok=True)

        evaporator = self._world_state.get_entity("evaporator", device_id)
        if evaporator is not None:
            running = evaporator.get("running", False)
            if running:
                logger.warning("Precondition failed for start_evaporation: evaporator {} already running", device_id)
                return PreconditionResult(
                    ok=False,
                    error_code=2050,
                    error_msg=f"Evaporator {device_id} is already running",
                )

        return PreconditionResult(ok=True)

    def _check_stop_evaporation(self, params: BaseModel) -> PreconditionResult:
        """Check stop_evaporation: evaporator must be running."""
        device_id = getattr(params, "device_id", None)
        if device_id is None:
            return PreconditionResult(ok=True)

        evaporator = self._world_state.get_entity("evaporator", device_id)
        if evaporator is None:
            logger.warning("Precondition failed for stop_evaporation: evaporator {} not found", device_id)
            return PreconditionResult(
                ok=False,
                error_code=2060,
                error_msg=f"Evaporator {device_id} not found in world state",
            )

        running = evaporator.get("running", False)
        if not running:
            logger.warning("Precondition failed for stop_evaporation: evaporator {} not running", device_id)
            return PreconditionResult(
                ok=False,
                error_code=2061,
                error_msg=f"Evaporator {device_id} is not running",
            )

        return PreconditionResult(ok=True)

    def _check_return_ccs_bins(self, params: BaseModel) -> PreconditionResult:
        """Check return_ccs_bins: bins must exist in chutes."""
        work_station_id = getattr(params, "work_station_id", None)
        if work_station_id is None:
            return PreconditionResult(ok=True)

        left_chute = self._world_state.get_entity("pcc_left_chute", work_station_id)
        right_chute = self._world_state.get_entity("pcc_right_chute", work_station_id)

        # At least one chute must have bins
        has_bins = False
        if left_chute is not None and (left_chute.get("front_waste_bin") or left_chute.get("back_waste_bin")):
            has_bins = True
        if right_chute is not None and (right_chute.get("front_waste_bin") or right_chute.get("back_waste_bin")):
            has_bins = True

        if not has_bins:
            logger.warning(
                "Precondition failed for return_ccs_bins: no bins found in chutes for work_station {}", work_station_id
            )
            return PreconditionResult(
                ok=False,
                error_code=2070,
                error_msg=f"No bins found in chutes for work station {work_station_id}",
            )

        return PreconditionResult(ok=True)

    def _check_return_cartridges(self, params: BaseModel) -> PreconditionResult:
        """Check return_cartridges: cartridges must exist."""
        silica_id = getattr(params, "silica_cartridge_id", None)
        sample_id = getattr(params, "sample_cartridge_id", None)

        if silica_id is None or sample_id is None:
            return PreconditionResult(ok=True)

        # Check silica cartridge exists
        if not self._world_state.has_entity("silica_cartridge", silica_id):
            logger.warning("Precondition failed for return_cartridges: silica_cartridge {} not found", silica_id)
            return PreconditionResult(
                ok=False,
                error_code=2080,
                error_msg=f"Silica cartridge {silica_id} not found in world state",
            )

        # Check sample cartridge exists
        if not self._world_state.has_entity("sample_cartridge", sample_id):
            logger.warning("Precondition failed for return_cartridges: sample_cartridge {} not found", sample_id)
            return PreconditionResult(
                ok=False,
                error_code=2081,
                error_msg=f"Sample cartridge {sample_id} not found in world state",
            )

        return PreconditionResult(ok=True)

    def _check_return_tube_rack(self, params: BaseModel) -> PreconditionResult:
        """Check return_tube_rack: tube_rack must exist."""
        tube_rack_id = getattr(params, "tube_rack_id", None)
        if tube_rack_id is None:
            return PreconditionResult(ok=True)

        if not self._world_state.has_entity("tube_rack", tube_rack_id):
            logger.warning("Precondition failed for return_tube_rack: tube_rack {} not found", tube_rack_id)
            return PreconditionResult(
                ok=False,
                error_code=2090,
                error_msg=f"Tube rack {tube_rack_id} not found in world state",
            )

        return PreconditionResult(ok=True)
