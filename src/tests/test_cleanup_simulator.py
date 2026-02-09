"""Tests for CleanupSimulator and new task parameter models."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import MockSettings
from src.schemas.commands import (
    ReturnCartridgesParams,
    ReturnCCSBinsParams,
    ReturnTubeRackParams,
    RobotState,
    SetupCCSBinsParams,
    StopEvaporationParams,
    TaskName,
)
from src.schemas.results import (
    EvaporatorUpdate,
    PCCLeftChuteUpdate,
    PCCRightChuteUpdate,
    RobotUpdate,
    RoundBottomFlaskUpdate,
    SampleCartridgeUpdate,
    SilicaCartridgeUpdate,
    TubeRackUpdate,
)
from src.simulators.cleanup_simulator import CleanupSimulator


@pytest.fixture
def cleanup_simulator(mock_settings: MockSettings) -> CleanupSimulator:
    """Create a CleanupSimulator with mocked dependencies."""
    producer = MagicMock()
    log_producer = AsyncMock()
    log_producer.publish_log = AsyncMock()
    return CleanupSimulator(producer, mock_settings, log_producer=log_producer)


class TestCleanupParamModels:
    """Tests for the 5 new parameter models."""

    def test_stop_evaporation_params(self) -> None:
        """StopEvaporationParams parses with defaults."""
        params = StopEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-001",
            device_type="evaporator",
        )
        assert params.work_station_id == "ws-1"
        assert params.device_id == "evap-001"
        assert params.end_state == RobotState.IDLE

    def test_stop_evaporation_params_custom_end_state(self) -> None:
        """StopEvaporationParams accepts custom end_state."""
        params = StopEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-001",
            device_type="evaporator",
            end_state=RobotState.WATCH_CC_SCREEN,
        )
        assert params.end_state == RobotState.WATCH_CC_SCREEN

    def test_setup_ccs_bins_params(self) -> None:
        """SetupCCSBinsParams parses with bin_location_ids list."""
        params = SetupCCSBinsParams(
            work_station_id="ws-1",
            bin_location_ids=["loc-A", "loc-B"],
        )
        assert params.work_station_id == "ws-1"
        assert params.bin_location_ids == ["loc-A", "loc-B"]
        assert params.end_state == RobotState.IDLE

    def test_return_ccs_bins_params(self) -> None:
        """ReturnCCSBinsParams parses with waste_area_id."""
        params = ReturnCCSBinsParams(
            work_station_id="ws-1",
            waste_area_id="waste-01",
        )
        assert params.work_station_id == "ws-1"
        assert params.waste_area_id == "waste-01"
        assert params.end_state == RobotState.IDLE

    def test_return_cartridges_params(self) -> None:
        """ReturnCartridgesParams parses with cartridge IDs and waste_area_id."""
        params = ReturnCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_id="sc-001",
            sample_cartridge_id="samp-001",
            waste_area_id="waste-01",
        )
        assert params.silica_cartridge_id == "sc-001"
        assert params.sample_cartridge_id == "samp-001"
        assert params.waste_area_id == "waste-01"
        assert params.end_state == RobotState.IDLE

    def test_return_tube_rack_params(self) -> None:
        """ReturnTubeRackParams parses with tube_rack_id and waste_area_id."""
        params = ReturnTubeRackParams(
            work_station_id="ws-1",
            tube_rack_id="rack-001",
            waste_area_id="waste-01",
        )
        assert params.tube_rack_id == "rack-001"
        assert params.waste_area_id == "waste-01"
        assert params.end_state == RobotState.IDLE


class TestCleanupSimulator:
    """Tests for CleanupSimulator task routing and results."""

    @pytest.mark.asyncio
    async def test_stop_evaporation(self, cleanup_simulator: CleanupSimulator) -> None:
        """stop_evaporation returns code=200 with evaporator and flask updates."""
        params = StopEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-001",
            device_type="evaporator",
        )
        result = await cleanup_simulator.simulate("task-100", TaskName.STOP_EVAPORATION, params)

        assert result.code == 200
        assert result.msg == "stop_evaporation completed"
        assert result.task_id == "task-100"

        update_types = {type(u) for u in result.updates}
        assert RobotUpdate in update_types
        assert EvaporatorUpdate in update_types
        assert RoundBottomFlaskUpdate in update_types

        # Verify evaporator is stopped
        evap = next(u for u in result.updates if isinstance(u, EvaporatorUpdate))
        assert evap.properties.running is False
        assert evap.properties.rpm == 0

    @pytest.mark.asyncio
    async def test_setup_ccs_bins(self, cleanup_simulator: CleanupSimulator) -> None:
        """setup_ccs_bins returns code=200 with chute updates."""
        params = SetupCCSBinsParams(
            work_station_id="ws-1",
            bin_location_ids=["loc-A", "loc-B"],
        )
        result = await cleanup_simulator.simulate("task-101", TaskName.SETUP_CCS_BINS, params)

        assert result.code == 200
        assert result.msg == "setup_ccs_bins completed"

        update_types = {type(u) for u in result.updates}
        assert RobotUpdate in update_types
        assert PCCLeftChuteUpdate in update_types
        assert PCCRightChuteUpdate in update_types

    @pytest.mark.asyncio
    async def test_return_ccs_bins(self, cleanup_simulator: CleanupSimulator) -> None:
        """return_ccs_bins returns code=200 with cleared chute updates."""
        params = ReturnCCSBinsParams(
            work_station_id="ws-1",
            waste_area_id="waste-01",
        )
        result = await cleanup_simulator.simulate("task-102", TaskName.RETURN_CCS_BINS, params)

        assert result.code == 200
        assert result.msg == "return_ccs_bins completed"

        # Verify chutes are cleared
        left = next(u for u in result.updates if isinstance(u, PCCLeftChuteUpdate))
        assert left.properties.closed is True
        assert left.properties.front_waste_bin is None
        assert left.properties.back_waste_bin is None

        right = next(u for u in result.updates if isinstance(u, PCCRightChuteUpdate))
        assert right.properties.closed is True
        assert right.properties.front_waste_bin is None
        assert right.properties.back_waste_bin is None

    @pytest.mark.asyncio
    async def test_return_cartridges(self, cleanup_simulator: CleanupSimulator) -> None:
        """return_cartridges returns code=200 with cartridge and ext module updates."""
        params = ReturnCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_id="sc-001",
            sample_cartridge_id="samp-001",
            waste_area_id="waste-01",
        )
        result = await cleanup_simulator.simulate("task-103", TaskName.RETURN_CARTRIDGES, params)

        assert result.code == 200
        assert result.msg == "return_cartridges completed"

        update_types = {type(u) for u in result.updates}
        assert RobotUpdate in update_types
        assert SilicaCartridgeUpdate in update_types
        assert SampleCartridgeUpdate in update_types

        # Verify cartridges are returned to waste area
        silica = next(u for u in result.updates if isinstance(u, SilicaCartridgeUpdate))
        assert silica.properties.location == "waste-01"
        assert silica.properties.state == "returned"

        sample = next(u for u in result.updates if isinstance(u, SampleCartridgeUpdate))
        assert sample.properties.location == "waste-01"
        assert sample.properties.state == "returned"

    @pytest.mark.asyncio
    async def test_return_tube_rack(self, cleanup_simulator: CleanupSimulator) -> None:
        """return_tube_rack returns code=200 with tube rack update."""
        params = ReturnTubeRackParams(
            work_station_id="ws-1",
            tube_rack_id="rack-001",
            waste_area_id="waste-01",
        )
        result = await cleanup_simulator.simulate("task-104", TaskName.RETURN_TUBE_RACK, params)

        assert result.code == 200
        assert result.msg == "return_tube_rack completed"

        update_types = {type(u) for u in result.updates}
        assert RobotUpdate in update_types
        assert TubeRackUpdate in update_types

        # Verify tube rack is returned to waste area
        rack = next(u for u in result.updates if isinstance(u, TubeRackUpdate))
        assert rack.properties.location == "waste-01"
        assert rack.properties.state == "returned"

    @pytest.mark.asyncio
    async def test_unknown_task_raises_error(self, cleanup_simulator: CleanupSimulator) -> None:
        """CleanupSimulator raises ValueError for unsupported task names."""
        params = StopEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-001",
            device_type="evaporator",
        )
        with pytest.raises(ValueError, match="CleanupSimulator cannot handle task"):
            await cleanup_simulator.simulate("task-999", TaskName.TAKE_PHOTO, params)
