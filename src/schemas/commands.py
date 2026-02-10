"""Robot command schemas for the mock server.

Imports parameter schemas and enums from the local protocol module.
Uses string-based enums for mock-friendly parsing (StrEnum values work as strings).
"""

from __future__ import annotations

from pydantic import BaseModel

from src.schemas.protocol import (
    BinState,
    CCExperimentParams,
    CollapseCartridgesParams,
    EntityState,
    EquipmentState,
    EvaporationProfile,
    EvaporationProfiles,
    EvaporationTrigger,
    FractionConsolidationParams,
    PeakGatheringMode,
    ReturnCartridgesParams,
    ReturnCCSBinsParams,
    ReturnTubeRackParams,
    RobotState,
    SetupCartridgesParams,
    SetupCCSBinsParams,
    SetupTubeRackParams,
    StartCCParams,
    StartEvaporationParams,
    StopEvaporationParams,
    TakePhotoParams,
    TaskName,
    TerminateCCParams,
)

# Re-export for backwards compatibility
__all__ = [
    # Enums
    "TaskName",
    "RobotState",
    "EntityState",
    "EquipmentState",
    "PeakGatheringMode",
    "BinState",
    # Command wrapper
    "RobotCommand",
    # Parameter schemas
    "SetupCartridgesParams",
    "SetupTubeRackParams",
    "CollapseCartridgesParams",
    "TakePhotoParams",
    "CCExperimentParams",
    "StartCCParams",
    "TerminateCCParams",
    "FractionConsolidationParams",
    "EvaporationTrigger",
    "EvaporationProfile",
    "EvaporationProfiles",
    "StartEvaporationParams",
    "StopEvaporationParams",
    "SetupCCSBinsParams",
    "ReturnCCSBinsParams",
    "ReturnCartridgesParams",
    "ReturnTubeRackParams",
]


# --- Command Wrapper ---


class RobotCommand(BaseModel):
    """Command message consumed from MQ. Params kept as raw dict for flexible parsing."""

    task_id: str
    task_name: TaskName
    params: dict
