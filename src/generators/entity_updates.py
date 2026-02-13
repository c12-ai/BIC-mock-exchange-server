"""Factory functions for creating entity update models.

Each function constructs the corresponding Pydantic model from schemas/results.py.
All functions are pure — no I/O, no side effects.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.schemas.protocol import ContainerState
from src.schemas.results import (
    CartridgeProperties,
    CCMachineProperties,
    CCSExtModuleProperties,
    CCSExtModuleUpdate,
    CCSystemUpdate,
    EvaporatorProperties,
    EvaporatorUpdate,
    PCCChuteProperties,
    PCCLeftChuteUpdate,
    PCCRightChuteUpdate,
    RobotProperties,
    RobotUpdate,
    RoundBottomFlaskProperties,
    RoundBottomFlaskUpdate,
    SampleCartridgeUpdate,
    SilicaCartridgeUpdate,
    TubeRackProperties,
    TubeRackUpdate,
)


def generate_robot_timestamp() -> str:
    """Generate timestamp in spec format: YYYY-MM-DD_HH-MM-SS.mmm

    Example: 2025-01-15_10-30-45.123

    This is the standardized timestamp format used across all robot messages
    (logs, heartbeats, entity updates) to match the BIC system specification.
    """
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%d_%H-%M-%S") + f".{now.microsecond // 1000:03d}"


def create_robot_update(
    robot_id: str,
    location: str,
    state: str,
    description: str = "",
) -> RobotUpdate:
    """Create a robot state/location update."""
    return RobotUpdate(
        id=robot_id,
        properties=RobotProperties(location=location, state=state, description=description),
    )


def create_silica_cartridge_update(
    cartridge_id: str,
    location: str,
    state: str,
    description: str = "",
) -> SilicaCartridgeUpdate:
    """Create a silica cartridge state update."""
    return SilicaCartridgeUpdate(
        id=cartridge_id,
        properties=CartridgeProperties(location=location, state=state, description=description),
    )


def create_sample_cartridge_update(
    cartridge_id: str,
    location: str,
    state: str,
    description: str = "",
) -> SampleCartridgeUpdate:
    """Create a sample cartridge state update."""
    return SampleCartridgeUpdate(
        id=cartridge_id,
        properties=CartridgeProperties(location=location, state=state, description=description),
    )


def create_tube_rack_update(
    rack_id: str,
    location: str,
    state: str,
    description: str = "",
) -> TubeRackUpdate:
    """Create a tube rack state update."""
    return TubeRackUpdate(
        id=rack_id,
        properties=TubeRackProperties(location=location, state=state, description=description),
    )


def create_round_bottom_flask_update(
    flask_id: str,
    location: str,
    state: ContainerState | str = "",
    description: str = "",
) -> RoundBottomFlaskUpdate:
    """Create a round bottom flask state update."""
    return RoundBottomFlaskUpdate(
        id=flask_id,
        properties=RoundBottomFlaskProperties(location=location, state=state, description=description),
    )


def create_ccs_ext_module_update(
    module_id: str,
    state: str,
    description: str = "",
) -> CCSExtModuleUpdate:
    """Create a CC external module state update."""
    return CCSExtModuleUpdate(
        id=module_id,
        properties=CCSExtModuleProperties(state=state, description=description),
    )


def create_cc_system_update(
    system_id: str,
    state: str,
    experiment_params: dict | None = None,
    start_timestamp: str | None = None,
    *,
    device_type: str = "column_chromatography_machine",
    description: str = "",
) -> CCSystemUpdate:
    """Create a CC machine state update with optional experiment params."""
    return CCSystemUpdate(
        type=device_type,
        id=system_id,
        properties=CCMachineProperties(
            state=state,
            experiment_params=experiment_params,
            start_timestamp=start_timestamp,
            description=description,
        ),
    )


def create_evaporator_update(
    evaporator_id: str,
    *,
    state: str = "using",
    lower_height: float = 0.0,
    rpm: int = 0,
    target_temperature: float = 0.0,
    current_temperature: float = 0.0,
    target_pressure: float = 0.0,
    current_pressure: float = 0.0,
    description: str = "",
) -> EvaporatorUpdate:
    """Create an evaporator state update with sensor readings."""
    return EvaporatorUpdate(
        id=evaporator_id,
        properties=EvaporatorProperties(
            state=state,
            lower_height=lower_height,
            rpm=rpm,
            target_temperature=target_temperature,
            current_temperature=current_temperature,
            target_pressure=target_pressure,
            current_pressure=current_pressure,
            description=description,
        ),
    )


def _open_waste_bin() -> ContainerState:
    """Create an 'open' waste bin as a proper ContainerState (empty, no lid)."""
    return ContainerState()


def create_pcc_left_chute_update(
    chute_id: str,
    *,
    state: str = "using",
    pulled_out_mm: float = 200.0,
    pulled_out_rate: float = 0.8,
    closed: bool = False,
    front_waste_bin: ContainerState | None = None,
    back_waste_bin: ContainerState | None = None,
    description: str = "",
) -> PCCLeftChuteUpdate:
    """Create a post-CC left chute state update.

    Default: front_waste_bin gets an open ContainerState if not explicitly provided.
    """
    if front_waste_bin is None:
        front_waste_bin = _open_waste_bin()
    return PCCLeftChuteUpdate(
        id=chute_id,
        properties=PCCChuteProperties(
            state=state,
            pulled_out_mm=pulled_out_mm,
            pulled_out_rate=pulled_out_rate,
            closed=closed,
            front_waste_bin=front_waste_bin,
            back_waste_bin=back_waste_bin,
            description=description,
        ),
    )


def create_pcc_right_chute_update(
    chute_id: str,
    *,
    state: str = "using",
    pulled_out_mm: float = 200.0,
    pulled_out_rate: float = 0.8,
    closed: bool = False,
    front_waste_bin: ContainerState | None = None,
    back_waste_bin: ContainerState | None = None,
    description: str = "",
) -> PCCRightChuteUpdate:
    """Create a post-CC right chute state update.

    Default: back_waste_bin gets an open ContainerState if not explicitly provided.
    """
    if back_waste_bin is None:
        back_waste_bin = _open_waste_bin()
    return PCCRightChuteUpdate(
        id=chute_id,
        properties=PCCChuteProperties(
            state=state,
            pulled_out_mm=pulled_out_mm,
            pulled_out_rate=pulled_out_rate,
            closed=closed,
            front_waste_bin=front_waste_bin,
            back_waste_bin=back_waste_bin,
            description=description,
        ),
    )
