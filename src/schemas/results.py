"""Robot result schemas for the mock server.

Aligned with v0.3 ground truth — uses typed state enums for entity properties,
includes ``description`` field on all entity properties.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.schemas.protocol import (
    CapturedImage as CapturedImage,  # noqa: PLC0414
)
from src.schemas.protocol import (
    CCExperimentParams,
    ContainerState,
    RobotState,
)

# --- Entity Property Models ---


class RobotProperties(BaseModel):
    """Properties for robot entity updates."""

    location: str
    state: RobotState
    description: str = ""


class CartridgeProperties(BaseModel):
    """Properties for silica/sample cartridge entity updates."""

    location: str
    state: str  # ConsumableState or plain string
    description: str = ""


class TubeRackProperties(BaseModel):
    """Properties for tube rack entity updates."""

    location: str
    state: str  # ToolState or plain string
    description: str = ""


class RoundBottomFlaskProperties(BaseModel):
    """Properties for round bottom flask entity updates."""

    location: str
    state: ContainerState | str = ""  # ContainerState model or legacy string
    description: str = ""


class CCSExtModuleProperties(BaseModel):
    """Properties for CC external module entity updates."""

    state: str  # DeviceState or plain string
    description: str = ""


class CCMachineProperties(BaseModel):
    """Properties for CC machine entity updates (v0.3 ground truth)."""

    state: str  # DeviceState or plain string
    experiment_params: CCExperimentParams | None = None
    start_timestamp: str | None = None
    description: str = ""


class EvaporatorProperties(BaseModel):
    """Properties for evaporator entity updates with sensor readings."""

    state: str = "idle"  # DeviceState or plain string
    lower_height: float = 0.0
    rpm: int = 0
    target_temperature: float = 0.0
    current_temperature: float = 0.0
    target_pressure: float = 0.0
    current_pressure: float = 0.0
    description: str = ""


class PCCChuteProperties(BaseModel):
    """Properties for post-column-chromatography chute entity updates."""

    state: str = "idle"  # DeviceState or plain string
    pulled_out_mm: float = 0.0
    pulled_out_rate: float = 0.0
    closed: bool = True
    front_waste_bin: ContainerState | None = None
    back_waste_bin: ContainerState | None = None
    description: str = ""


# --- Entity Update Models (Discriminated Union) ---


class RobotUpdate(BaseModel):
    """Robot state/location update."""

    type: Literal["robot"] = "robot"
    id: str
    properties: RobotProperties


class SilicaCartridgeUpdate(BaseModel):
    """Silica cartridge state update."""

    type: Literal["silica_cartridge"] = "silica_cartridge"
    id: str
    properties: CartridgeProperties


class SampleCartridgeUpdate(BaseModel):
    """Sample cartridge state update."""

    type: Literal["sample_cartridge"] = "sample_cartridge"
    id: str
    properties: CartridgeProperties


class TubeRackUpdate(BaseModel):
    """Tube rack state update."""

    type: Literal["tube_rack"] = "tube_rack"
    id: str
    properties: TubeRackProperties


class RoundBottomFlaskUpdate(BaseModel):
    """Round bottom flask state update."""

    type: Literal["round_bottom_flask"] = "round_bottom_flask"
    id: str
    properties: RoundBottomFlaskProperties


class CCSExtModuleUpdate(BaseModel):
    """CC external module state update."""

    type: Literal["ccs_ext_module"] = "ccs_ext_module"
    id: str
    properties: CCSExtModuleProperties


class CCSystemUpdate(BaseModel):
    """Column chromatography machine state update (v0.3: column_chromatography_machine)."""

    type: Literal["column_chromatography_machine", "isco_combiflash_nextgen_300"]
    id: str
    properties: CCMachineProperties


class EvaporatorUpdate(BaseModel):
    """Evaporator state update with sensor readings."""

    type: Literal["evaporator"] = "evaporator"
    id: str
    properties: EvaporatorProperties


class PCCLeftChuteUpdate(BaseModel):
    """Post-CC left chute state update."""

    type: Literal["pcc_left_chute"] = "pcc_left_chute"
    id: str
    properties: PCCChuteProperties


class PCCRightChuteUpdate(BaseModel):
    """Post-CC right chute state update."""

    type: Literal["pcc_right_chute"] = "pcc_right_chute"
    id: str
    properties: PCCChuteProperties


# --- Discriminated Union Type ---
EntityUpdate = Annotated[
    RobotUpdate
    | SilicaCartridgeUpdate
    | SampleCartridgeUpdate
    | TubeRackUpdate
    | RoundBottomFlaskUpdate
    | CCSExtModuleUpdate
    | CCSystemUpdate
    | EvaporatorUpdate
    | PCCLeftChuteUpdate
    | PCCRightChuteUpdate,
    Field(discriminator="type"),
]


# --- Result Message ---


class RobotResult(BaseModel):
    """Result message published to MQ after task simulation."""

    code: int
    msg: str
    task_id: str
    updates: list[EntityUpdate] = Field(default_factory=list)
    images: list[CapturedImage] | None = None

    def is_success(self) -> bool:
        """Check if the result indicates success."""
        return self.code == 200


class LogMessage(BaseModel):
    """Log message published to {robot_id}.log during skill execution.

    Mock-server internal type — not part of v0.3 protocol.
    """

    code: int = 200
    msg: str = "state_update"
    task_id: str
    updates: list[EntityUpdate] = Field(default_factory=list)
    timestamp: str  # ISO format


class HeartbeatMessage(BaseModel):
    """Heartbeat message published to {robot_id}.hb."""

    robot_id: str
    timestamp: str  # ISO format
    state: RobotState = RobotState.IDLE
    Work_station: str | None = None  # noqa: N815 — matches ground truth casing


# Backward compat alias: CCSystemProperties → CCMachineProperties
CCSystemProperties = CCMachineProperties

# Re-export for backwards compatibility with existing mock server code
__all__ = [
    "RobotProperties",
    "CartridgeProperties",
    "TubeRackProperties",
    "RoundBottomFlaskProperties",
    "CCSExtModuleProperties",
    "CCMachineProperties",
    "CCSystemProperties",
    "EvaporatorProperties",
    "PCCChuteProperties",
    "RobotUpdate",
    "SilicaCartridgeUpdate",
    "SampleCartridgeUpdate",
    "TubeRackUpdate",
    "RoundBottomFlaskUpdate",
    "CCSExtModuleUpdate",
    "CCSystemUpdate",
    "EvaporatorUpdate",
    "PCCLeftChuteUpdate",
    "PCCRightChuteUpdate",
    "EntityUpdate",
    "CapturedImage",
    "RobotResult",
    "LogMessage",
    "HeartbeatMessage",
]
