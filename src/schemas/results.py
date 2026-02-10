"""Robot result schemas for the mock server.

Aligned with v0.3 ground truth — uses enum types for entity state fields.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.schemas.protocol import (
    BinState,
    CCExperimentParams,
    EntityState,
    RobotState,
)
from src.schemas.protocol import (
    CapturedImage as CapturedImage,  # noqa: PLC0414
)

# --- Entity Property Models ---


class RobotProperties(BaseModel):
    """Properties for robot entity updates."""

    location: str
    state: RobotState


class CartridgeProperties(BaseModel):
    """Properties for silica/sample cartridge entity updates."""

    location: str
    state: EntityState


class TubeRackProperties(BaseModel):
    """Properties for tube rack entity updates."""

    location: str
    state: str  # Compound states like "used,pulled_out,ready_for_recovery"


class RoundBottomFlaskProperties(BaseModel):
    """Properties for round bottom flask entity updates."""

    location: str
    state: str  # Compound states like "used,evaporating"


class CCSExtModuleProperties(BaseModel):
    """Properties for CC external module entity updates."""

    state: EntityState


class CCSystemProperties(BaseModel):
    """Properties for CC system entity updates."""

    state: EntityState
    experiment_params: CCExperimentParams | None = None
    start_timestamp: str | None = None


class EvaporatorProperties(BaseModel):
    """Properties for evaporator entity updates with sensor readings."""

    running: bool
    lower_height: float
    rpm: int
    target_temperature: float
    current_temperature: float
    target_pressure: float
    current_pressure: float


class PCCChuteProperties(BaseModel):
    """Properties for post-column-chromatography chute entity updates."""

    pulled_out_mm: float
    pulled_out_rate: float
    closed: bool
    front_waste_bin: BinState | None = None
    back_waste_bin: BinState | None = None


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
    """Column chromatography system state update."""

    type: Literal["column_chromatography_system", "isco_combiflash_nextgen_300"]
    id: str
    properties: CCSystemProperties


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
    """Log message published to {robot_id}.log during skill execution."""

    code: int = 200
    msg: str = "state_update"
    task_id: str
    updates: list[EntityUpdate] = Field(default_factory=list)
    timestamp: str  # ISO format


class HeartbeatMessage(BaseModel):
    """Heartbeat message published to {robot_id}.hb."""

    robot_id: str
    timestamp: str  # ISO format
    state: str = "idle"  # simple status indicator


# Re-export for backwards compatibility with existing mock server code
__all__ = [
    "RobotProperties",
    "CartridgeProperties",
    "TubeRackProperties",
    "RoundBottomFlaskProperties",
    "CCSExtModuleProperties",
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
