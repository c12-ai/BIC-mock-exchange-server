"""
Shared protocol types for robot MQ communication.

Self-contained copies of enums and Pydantic schemas that define the contract
between BIC Lab Service and the Robot Exchange. These types are the single
source of truth for the mock server — no imports from the production codebase.

When the production protocol changes, update this file to match.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class RobotState(StrEnum):
    """Robot operational states.

    Includes both stable end-states and intermediate states reported
    during task execution.
    """

    IDLE = "idle"
    WAIT_FOR_SCREEN = "wait_for_screen_manipulation"
    WATCH_CC_SCREEN = "watch_column_machine_screen"
    MOVING_WITH_FLASK = "moving_with_round_bottom_flask"
    OBSERVE_EVAPORATION = "observe_evaporation"
    # Intermediate states reported during task execution
    MOVING = "moving"
    TERMINATING_CC = "terminating_cc"
    PULLING_OUT_TUBE_RACK = "pulling_out_tube_rack"


class TaskName(StrEnum):
    """Robot task command names."""

    SETUP_CARTRIDGES = "setup_tubes_to_column_machine"
    SETUP_TUBE_RACK = "setup_tube_rack"
    COLLAPSE_CARTRIDGES = "collapse_cartridges"
    TAKE_PHOTO = "take_photo"
    START_CC = "start_column_chromatography"
    TERMINATE_CC = "terminate_column_chromatography"
    FRACTION_CONSOLIDATION = "fraction_consolidation"
    START_EVAPORATION = "start_evaporation"
    STOP_EVAPORATION = "stop_evaporation"
    SETUP_CCS_BINS = "setup_ccs_bins"
    RETURN_CCS_BINS = "return_ccs_bins"
    RETURN_CARTRIDGES = "return_cartridges"
    RETURN_TUBE_RACK = "return_tube_rack"


class EntityState(StrEnum):
    """Common entity states."""

    AVAILABLE = "available"
    MOUNTED = "mounted"
    USING = "using"
    USED = "used"
    RUNNING = "running"
    TERMINATED = "terminated"
    EVAPORATING = "evaporating"
    # Mock-server extras (not in production ground truth)
    RETURNED = "returned"
    MAINTENANCE = "maintenance"
    ERROR = "error"


# Backward-compatible alias
EquipmentState = EntityState


class BinState(StrEnum):
    """Waste bin states for PCC chute."""

    OPEN = "open"
    CLOSE = "close"
    FULL = "full"


class PeakGatheringMode(StrEnum):
    """Peak collection modes for column chromatography."""

    ALL = "all"
    PEAK = "peak"
    NONE = "none"


# =============================================================================
# Command Parameters
# =============================================================================


class SetupCartridgesParams(BaseModel):
    """Parameters for setup_cartridges task."""

    silica_cartridge_location_id: str
    silica_cartridge_type: str
    silica_cartridge_id: str
    sample_cartridge_location_id: str
    sample_cartridge_type: str
    sample_cartridge_id: str
    work_station_id: str


class SetupTubeRackParams(BaseModel):
    """Parameters for setup_tube_rack task."""

    tube_rack_location_id: str
    work_station_id: str
    end_state: RobotState = RobotState.IDLE


class CollapseCartridgesParams(BaseModel):
    """Parameters for collapse_cartridges task."""

    work_station_id: str
    silica_cartridge_id: str
    sample_cartridge_id: str
    end_state: RobotState = RobotState.IDLE


class TakePhotoParams(BaseModel):
    """Parameters for take_photo task."""

    work_station_id: str
    device_id: str
    device_type: str
    components: list[str] | str
    end_state: RobotState


class CCExperimentParams(BaseModel):
    """Column chromatography experiment parameters."""

    silicone_column: str = Field(..., description="Silica column spec, e.g. '40g'")
    peak_gathering_mode: PeakGatheringMode = Field(..., description="all, peak, or none")
    air_clean_minutes: int = Field(..., description="Air clean duration in minutes")
    run_minutes: int = Field(..., description="Total run duration in minutes")
    need_equilibration: bool = Field(..., description="Whether column equilibration needed")
    left_rack: str | None = Field(default=None, description="Left tube rack spec")
    right_rack: str | None = Field(default=None, description="Right tube rack spec")


class StartCCParams(BaseModel):
    """Parameters for start_column_chromatography task."""

    work_station_id: str
    device_id: str
    device_type: str
    experiment_params: CCExperimentParams
    end_state: RobotState


class TerminateCCParams(BaseModel):
    """Parameters for terminate_column_chromatography task."""

    work_station_id: str
    device_id: str
    device_type: str
    end_state: RobotState


class FractionConsolidationParams(BaseModel):
    """Parameters for fraction_consolidation task."""

    work_station_id: str
    device_id: str
    device_type: str
    collect_config: list[int] = Field(..., description="1=collect, 0=discard per tube")
    end_state: RobotState


class EvaporationTrigger(BaseModel):
    """Trigger condition for evaporation profile changes."""

    type: Literal["time_from_start", "event"]
    time_in_sec: int | None = Field(default=None, description="Delay in seconds")
    event_name: str | None = Field(default=None, description="Event name for event trigger")


class EvaporationProfile(BaseModel):
    """Evaporation parameter profile."""

    lower_height: float = Field(..., description="Flask lowering height in mm")
    rpm: int = Field(..., description="Rotation speed in rpm")
    target_temperature: float = Field(..., description="Water bath temp in Celsius")
    target_pressure: float = Field(..., description="Vacuum pressure in mbar")
    trigger: EvaporationTrigger | None = None


class EvaporationProfiles(BaseModel):
    """Collection of evaporation profiles for different stages."""

    start: EvaporationProfile = Field(..., description="Initial profile (required)")
    stop: EvaporationProfile | None = None
    lower_pressure: EvaporationProfile | None = None
    reduce_bumping: EvaporationProfile | None = Field(
        default=None,
        description="Anti-bumping safety",
    )


class StartEvaporationParams(BaseModel):
    """Parameters for start_evaporation task."""

    work_station_id: str
    device_id: str
    device_type: str
    profiles: EvaporationProfiles
    post_run_state: RobotState


class StopEvaporationParams(BaseModel):
    """Parameters for stop_evaporation task."""

    work_station_id: str
    device_id: str
    device_type: str
    end_state: RobotState = RobotState.IDLE


class SetupCCSBinsParams(BaseModel):
    """Parameters for setup_ccs_bins task."""

    work_station_id: str
    bin_location_ids: list[str]  # locations to fetch bins from
    end_state: RobotState = RobotState.IDLE


class ReturnCCSBinsParams(BaseModel):
    """Parameters for return_ccs_bins task."""

    work_station_id: str
    waste_area_id: str  # where to bring the used bins
    end_state: RobotState = RobotState.IDLE


class ReturnCartridgesParams(BaseModel):
    """Parameters for return_cartridges task."""

    work_station_id: str
    silica_cartridge_id: str
    sample_cartridge_id: str
    waste_area_id: str
    end_state: RobotState = RobotState.IDLE


class ReturnTubeRackParams(BaseModel):
    """Parameters for return_tube_rack task."""

    work_station_id: str
    tube_rack_id: str
    waste_area_id: str
    end_state: RobotState = RobotState.IDLE


# =============================================================================
# Result Types
# =============================================================================


class CapturedImage(BaseModel):
    """Captured image metadata."""

    work_station_id: str
    device_id: str
    device_type: str
    component: str
    url: str


# =============================================================================
# Generic Command Type
# =============================================================================


class TypedRobotCommand[P: BaseModel](BaseModel):
    """Generic command message with typed params, matching ground truth RobotCommand[P]."""

    task_id: str
    task_name: TaskName
    params: P


# Concrete command type aliases
SetupCartridgesCommand = TypedRobotCommand[SetupCartridgesParams]
SetupTubeRackCommand = TypedRobotCommand[SetupTubeRackParams]
CollapseCartridgesCommand = TypedRobotCommand[CollapseCartridgesParams]
TakePhotoCommand = TypedRobotCommand[TakePhotoParams]
StartCCCommand = TypedRobotCommand[StartCCParams]
TerminateCCCommand = TypedRobotCommand[TerminateCCParams]
FractionConsolidationCommand = TypedRobotCommand[FractionConsolidationParams]
StartEvaporationCommand = TypedRobotCommand[StartEvaporationParams]
