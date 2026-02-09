"""Integration tests for all simulators end-to-end.

Tests each simulator directly with mock producer, verifying results
and entity updates without going through the consumer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.schemas.commands import (
    CollapseCartridgesParams,
    ReturnCartridgesParams,
    ReturnCCSBinsParams,
    ReturnTubeRackParams,
    RobotState,
    SetupCCSBinsParams,
    SetupTubeRackParams,
    StopEvaporationParams,
    TaskName,
    TerminateCCParams,
)
from src.schemas.results import (
    CCSystemUpdate,
    EvaporatorUpdate,
    PCCLeftChuteUpdate,
    PCCRightChuteUpdate,
    RobotUpdate,
    SampleCartridgeUpdate,
    SilicaCartridgeUpdate,
    TubeRackUpdate,
)
from src.simulators.cc_simulator import CCSimulator
from src.simulators.cleanup_simulator import CleanupSimulator
from src.simulators.setup_simulator import SetupSimulator


@pytest.fixture
def mock_producer():
    """Mock ResultProducer."""
    producer = AsyncMock()
    producer.publish_result = AsyncMock()
    return producer


@pytest.fixture
def mock_log_producer():
    """Mock LogProducer."""
    log_producer = AsyncMock()
    log_producer.publish_log = AsyncMock()
    return log_producer


@pytest.fixture
def world_state():
    """Create WorldState."""
    from src.state.world_state import WorldState

    return WorldState()


@pytest.fixture
def setup_simulator(mock_producer, mock_log_producer, mock_settings, world_state):
    """Create SetupSimulator."""
    return SetupSimulator(mock_producer, mock_settings, log_producer=mock_log_producer, world_state=world_state)


@pytest.fixture
def cc_simulator(mock_producer, mock_log_producer, mock_settings, world_state):
    """Create CCSimulator."""
    return CCSimulator(mock_producer, mock_settings, log_producer=mock_log_producer, world_state=world_state)


@pytest.fixture
def cleanup_simulator(mock_producer, mock_log_producer, mock_settings, world_state):
    """Create CleanupSimulator."""
    return CleanupSimulator(mock_producer, mock_settings, log_producer=mock_log_producer, world_state=world_state)


class TestSetupSimulatorIntegration:
    """Integration tests for SetupSimulator."""

    @pytest.mark.asyncio
    async def test_setup_tube_rack(self, setup_simulator):
        """Test setup_tube_rack returns success with expected updates."""
        params = SetupTubeRackParams(
            work_station_id="ws-1",
            tube_rack_location_id="rack-001",
            end_state=RobotState.IDLE,
        )
        result = await setup_simulator.simulate("task-002", TaskName.SETUP_TUBE_RACK, params)

        assert result.code == 200
        assert result.msg == "setup_tube_rack completed"
        assert result.task_id == "task-002"

        # Verify expected updates
        update_types = {type(u) for u in result.updates}
        assert RobotUpdate in update_types
        assert TubeRackUpdate in update_types

        # Verify tube rack is mounted
        rack = next(u for u in result.updates if isinstance(u, TubeRackUpdate))
        assert rack.properties.state == "mounted"

    @pytest.mark.asyncio
    async def test_collapse_cartridges(self, setup_simulator):
        """Test collapse_cartridges returns success with expected updates."""
        params = CollapseCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_id="sc-001",
            sample_cartridge_id="samp-001",
            end_state=RobotState.IDLE,
        )
        result = await setup_simulator.simulate("task-003", TaskName.COLLAPSE_CARTRIDGES, params)

        assert result.code == 200
        assert result.msg == "collapse_cartridges completed"
        assert result.task_id == "task-003"

        # Verify cartridges are marked as used
        silica = next(u for u in result.updates if isinstance(u, SilicaCartridgeUpdate))
        assert silica.properties.state == "used"

        sample = next(u for u in result.updates if isinstance(u, SampleCartridgeUpdate))
        assert sample.properties.state == "used"


class TestCCSimulatorIntegration:
    """Integration tests for CCSimulator."""

    @pytest.mark.asyncio
    async def test_terminate_cc(self, cc_simulator):
        """Test terminate_cc returns success with screen captures."""
        params = TerminateCCParams(
            work_station_id="ws-1",
            device_id="cc-001",
            device_type="column_chromatography_system",
            end_state=RobotState.IDLE,
        )
        result = await cc_simulator.simulate("task-006", TaskName.TERMINATE_CC, params)

        assert result.code == 200
        assert result.msg == "terminate_column_chromatography completed"
        assert result.task_id == "task-006"

        # Verify CC system is terminated
        cc_update = next(u for u in result.updates if isinstance(u, CCSystemUpdate))
        assert cc_update.properties.state == "terminated"

        # Verify images (screen captures) are included
        assert result.images is not None
        assert len(result.images) > 0


class TestCleanupSimulatorIntegration:
    """Integration tests for CleanupSimulator."""

    @pytest.mark.asyncio
    async def test_stop_evaporation(self, cleanup_simulator):
        """Test stop_evaporation returns success with evaporator stopped."""
        params = StopEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-001",
            device_type="evaporator",
            end_state=RobotState.IDLE,
        )
        result = await cleanup_simulator.simulate("task-009", TaskName.STOP_EVAPORATION, params)

        assert result.code == 200
        assert result.msg == "stop_evaporation completed"
        assert result.task_id == "task-009"

        # Verify evaporator is stopped
        evap = next(u for u in result.updates if isinstance(u, EvaporatorUpdate))
        assert evap.properties.running is False
        assert evap.properties.rpm == 0

    @pytest.mark.asyncio
    async def test_setup_ccs_bins(self, cleanup_simulator):
        """Test setup_ccs_bins returns success with chute updates."""
        params = SetupCCSBinsParams(
            work_station_id="ws-1",
            bin_location_ids=["bin-1", "bin-2"],
            end_state=RobotState.IDLE,
        )
        result = await cleanup_simulator.simulate("task-010", TaskName.SETUP_CCS_BINS, params)

        assert result.code == 200
        assert result.msg == "setup_ccs_bins completed"
        assert result.task_id == "task-010"

        # Verify chute updates
        update_types = {type(u) for u in result.updates}
        assert PCCLeftChuteUpdate in update_types
        assert PCCRightChuteUpdate in update_types

    @pytest.mark.asyncio
    async def test_return_ccs_bins(self, cleanup_simulator):
        """Test return_ccs_bins returns success with cleared chutes."""
        params = ReturnCCSBinsParams(
            work_station_id="ws-1",
            waste_area_id="waste-01",
            end_state=RobotState.IDLE,
        )
        result = await cleanup_simulator.simulate("task-011", TaskName.RETURN_CCS_BINS, params)

        assert result.code == 200
        assert result.msg == "return_ccs_bins completed"
        assert result.task_id == "task-011"

        # Verify chutes are cleared
        left = next(u for u in result.updates if isinstance(u, PCCLeftChuteUpdate))
        assert left.properties.closed is True
        assert left.properties.front_waste_bin is None

    @pytest.mark.asyncio
    async def test_return_cartridges(self, cleanup_simulator):
        """Test return_cartridges returns success with cartridges returned."""
        params = ReturnCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_id="sc-001",
            sample_cartridge_id="samp-001",
            waste_area_id="waste-01",
            end_state=RobotState.IDLE,
        )
        result = await cleanup_simulator.simulate("task-012", TaskName.RETURN_CARTRIDGES, params)

        assert result.code == 200
        assert result.msg == "return_cartridges completed"
        assert result.task_id == "task-012"

        # Verify cartridges returned to waste area
        silica = next(u for u in result.updates if isinstance(u, SilicaCartridgeUpdate))
        assert silica.properties.location == "waste-01"
        assert silica.properties.state == "returned"

    @pytest.mark.asyncio
    async def test_return_tube_rack(self, cleanup_simulator):
        """Test return_tube_rack returns success with rack returned."""
        params = ReturnTubeRackParams(
            work_station_id="ws-1",
            tube_rack_id="rack-001",
            waste_area_id="waste-01",
            end_state=RobotState.IDLE,
        )
        result = await cleanup_simulator.simulate("task-013", TaskName.RETURN_TUBE_RACK, params)

        assert result.code == 200
        assert result.msg == "return_tube_rack completed"
        assert result.task_id == "task-013"

        # Verify tube rack returned to waste area
        rack = next(u for u in result.updates if isinstance(u, TubeRackUpdate))
        assert rack.properties.location == "waste-01"
        assert rack.properties.state == "returned"
