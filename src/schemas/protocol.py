"""
Shared protocol types for robot MQ communication.

Self-contained copies of enums and Pydantic schemas that define the contract
between BIC Lab Service and the Robot Exchange. These types are the single
source of truth for the mock server — no imports from the production codebase.

When the production protocol changes, update this file to match.

Golden rule: `docs/robot_messages_new.py` is the single source of truth
for all message schemas.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class RobotState(StrEnum):
    """Robot operational states (v0.3 ground truth)."""

    IDLE = "idle"
    WORKING = "working"
    CHARGING = "charging"


class RobotPosture:
    """String constants for robot posture descriptions.

    These are NOT enum values — they are used in the ``description`` field
    of RobotProperties to describe what the robot is doing while in
    ``RobotState.WORKING``.
    """

    WAIT_FOR_SCREEN = "wait_for_screen_manipulation"
    WATCH_CC_SCREEN = "watch_column_machine_screen"
    MOVING_WITH_FLASK = "moving_with_round_bottom_flask"
    OBSERVE_EVAPORATION = "observe_evaporation"


class TaskType(StrEnum):
    """Robot task command types (v0.3 ground truth — 7 tasks)."""

    SETUP_CARTRIDGES = "setup_tubes_to_column_machine"
    SETUP_TUBE_RACK = "setup_tube_rack"
    TAKE_PHOTO = "take_photo"
    START_CC = "start_column_chromatography"
    TERMINATE_CC = "terminate_column_chromatography"
    COLLECT_CC_FRACTIONS = "collect_column_chromatography_fractions"
    START_EVAPORATION = "start_evaporation"


class EntityState(StrEnum):
    """Common entity states (v0.3 ground truth)."""

    IDLE = "idle"
    MOUNTED = "mounted"
    USING = "using"
    USED = "used"
    RUNNING = "running"


class DeviceState(StrEnum):
    """Device states (v0.3 ground truth)."""

    IDLE = "idle"
    USING = "using"
    UNAVAILABLE = "unavailable"


class ConsumableState(StrEnum):
    """Consumable states (v0.3 ground truth)."""

    UNUSED = "unused"
    INUSE = "inuse"
    USED = "used"


class ToolState(StrEnum):
    """Tool states (v0.3 ground truth)."""

    AVAILABLE = "available"
    INUSE = "inuse"
    CONTAMINATED = "contaminated"


class ContainerContentState(StrEnum):
    """Container content states (v0.3 ground truth)."""

    EMPTY = "empty"
    FILL = "fill"
    USED = "used"


class ContainerLidState(StrEnum):
    """Container lid states (v0.3 ground truth)."""

    CLOSED = "closed"
    OPENED = "opened"


class SubstanceUnit(StrEnum):
    """Substance unit types (v0.3 ground truth)."""

    ML = "ml"
    L = "l"
    G = "g"
    KG = "kg"
    MG = "mg"


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
# Shared Types
# =============================================================================


class Substance(BaseModel):
    """Substance definition (v0.3 ground truth)."""

    name: str = ""
    zh_name: str = ""
    unit: SubstanceUnit = SubstanceUnit.ML
    amount: float = 0.0


class ContainerState(BaseModel):
    """Container state (v0.3 ground truth)."""

    content_state: ContainerContentState = ContainerContentState.EMPTY
    has_lid: bool = False
    lid_state: ContainerLidState | None = None
    substance: Substance | None = None


class CCGradientConfig(BaseModel):
    """Column chromatography gradient configuration (v0.3 ground truth)."""

    duration_minutes: float
    solvent_b_ratio: float


# =============================================================================
# Command Parameters
# =============================================================================


class SetupCartridgesParams(BaseModel):
    """Parameters for setup_tubes_to_column_machine task (v0.3 ground truth)."""

    silica_cartridge_type: str = "silica_40g"
    sample_cartridge_location: str = "bic_09B_l3_002"
    sample_cartridge_type: str = "sample_40g"
    sample_cartridge_id: str
    work_station: str = "ws_bic_09_fh_001"


class SetupTubeRackParams(BaseModel):
    """Parameters for setup_tube_rack task (v0.3 ground truth)."""

    work_station: str = "ws_bic_09_fh_001"


class TakePhotoParams(BaseModel):
    """Parameters for take_photo task (v0.3 ground truth)."""

    work_station: str
    device_id: str
    device_type: str
    components: list[str] | str


class CCExperimentParams(BaseModel):
    """Column chromatography experiment parameters (v0.3 ground truth)."""

    silicone_cartridge: str = Field(default="silica_40g", description="Silica column spec, e.g. 'silica_40g'")
    peak_gathering_mode: PeakGatheringMode = Field(default=PeakGatheringMode.PEAK, description="all, peak, or none")
    air_purge_minutes: float = Field(default=1.2, description="Air purge duration in minutes")
    run_minutes: int = Field(default=30, description="Total run duration in minutes")
    solvent_a: str = Field(default="pet_ether", description="Solvent A")
    solvent_b: str = Field(default="ethyl_acetate", description="Solvent B")
    gradients: list[CCGradientConfig] = Field(default_factory=list, description="Gradient configurations")
    need_equilibration: bool = Field(default=True, description="Whether column equilibration needed")
    left_rack: str | None = Field(default="16x150", description="Left tube rack spec")
    right_rack: str | None = Field(default=None, description="Right tube rack spec")


class StartCCParams(BaseModel):
    """Parameters for start_column_chromatography task (v0.3 ground truth)."""

    work_station: str = "ws_bic_09_fh_001"
    device_id: str = "cc-isco-300p_001"
    device_type: str = "cc-isco-300p"
    experiment_params: CCExperimentParams


class TerminateCCParams(BaseModel):
    """Parameters for terminate_column_chromatography task (v0.3 ground truth)."""

    work_station: str = "ws_bic_09_fh_001"
    device_id: str = "cc-isco-300p_001"
    device_type: str = "cc-isco-300p"
    experiment_params: CCExperimentParams


class CollectCCFractionsParams(BaseModel):
    """Parameters for collect_column_chromatography_fractions task (v0.3 ground truth)."""

    work_station: str = "ws_bic_09_fh_001"
    device_id: str = "cc-isco-300p_001"
    device_type: str = "cc-isco-300p"
    collect_config: list[int] = Field(..., description="1=collect, 0=discard per tube")


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
    """Collection of evaporation profiles (v0.3 ground truth)."""

    start: EvaporationProfile = Field(..., description="Initial profile (required)")
    updates: list[EvaporationProfile] = Field(default_factory=list)


class StartEvaporationParams(BaseModel):
    """Parameters for start_evaporation task (v0.3 ground truth)."""

    work_station: str = "ws_bic_09_fh_002"
    device_id: str = "re-buchi-r180_001"
    device_type: str = "re-buchi-r180"
    profiles: EvaporationProfiles


# =============================================================================
# Result Types
# =============================================================================


class CapturedImage(BaseModel):
    """Captured image metadata (v0.3 ground truth)."""

    work_station: str
    device_id: str
    device_type: str
    component: str
    url: str
    create_time: str = ""


# =============================================================================
# Generic Command Type
# =============================================================================


class TypedRobotCommand[P: BaseModel](BaseModel):
    """Generic command message with typed params, matching ground truth RobotCommand[P]."""

    task_id: str
    task_type: TaskType
    params: P


# Concrete command type aliases
SetupCartridgesCommand = TypedRobotCommand[SetupCartridgesParams]
SetupTubeRackCommand = TypedRobotCommand[SetupTubeRackParams]
TakePhotoCommand = TypedRobotCommand[TakePhotoParams]
StartCCCommand = TypedRobotCommand[StartCCParams]
TerminateCCCommand = TypedRobotCommand[TerminateCCParams]
CollectCCFractionsCommand = TypedRobotCommand[CollectCCFractionsParams]
StartEvaporationCommand = TypedRobotCommand[StartEvaporationParams]
