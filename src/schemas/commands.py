"""Robot command schemas for the mock server.

Imports parameter schemas and enums from the local protocol module.
Uses string-based enums for mock-friendly parsing (StrEnum values work as strings).
"""

from __future__ import annotations

from pydantic import BaseModel

from src.schemas.protocol import (
    BinState,
    CCExperimentParams,
    CCGradientConfig,
    CollectCCFractionsParams,
    ConsumableState,
    ContainerContentState,
    ContainerLidState,
    ContainerState,
    DeviceState,
    EntityState,
    EvaporationProfile,
    EvaporationProfiles,
    EvaporationTrigger,
    PeakGatheringMode,
    RobotPosture,
    RobotState,
    SetupCartridgesParams,
    SetupTubeRackParams,
    StartCCParams,
    StartEvaporationParams,
    Substance,
    SubstanceUnit,
    TakePhotoParams,
    TaskType,
    TerminateCCParams,
    ToolState,
)

# Re-export for backwards compatibility
__all__ = [
    # Enums
    "TaskType",
    "RobotState",
    "RobotPosture",
    "EntityState",
    "DeviceState",
    "ConsumableState",
    "ToolState",
    "ContainerContentState",
    "ContainerLidState",
    "SubstanceUnit",
    "PeakGatheringMode",
    "BinState",
    # Shared types
    "Substance",
    "ContainerState",
    "CCGradientConfig",
    # Command wrapper
    "RobotCommand",
    # Parameter schemas
    "SetupCartridgesParams",
    "SetupTubeRackParams",
    "TakePhotoParams",
    "CCExperimentParams",
    "StartCCParams",
    "TerminateCCParams",
    "CollectCCFractionsParams",
    "EvaporationTrigger",
    "EvaporationProfile",
    "EvaporationProfiles",
    "StartEvaporationParams",
]


# --- Command Wrapper ---


class RobotCommand(BaseModel):
    """Command message consumed from MQ. Params kept as raw dict for flexible parsing."""

    task_id: str
    task_type: TaskType
    params: dict
