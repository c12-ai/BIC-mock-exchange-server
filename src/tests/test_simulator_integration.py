"""Integration tests for all simulators end-to-end.

Tests each simulator directly with mock producer, verifying results
and entity updates without going through the consumer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.schemas.commands import (
    RobotState,
    SetupTubeRackParams,
    TaskType,
    TerminateCCParams,
)
from src.schemas.results import (
    CCSystemUpdate,
    RobotUpdate,
    SampleCartridgeUpdate,
    SilicaCartridgeUpdate,
    TubeRackUpdate,
)
from src.simulators.cc_simulator import CCSimulator
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


class TestSetupSimulatorIntegration:
    """Integration tests for SetupSimulator."""

    @pytest.mark.asyncio
    async def test_setup_tube_rack(self, setup_simulator):
        """Test setup_tube_rack returns success with expected updates."""
        params = SetupTubeRackParams(
            work_station="ws_bic_09_fh_001",
        )
        result = await setup_simulator.simulate("task-002", TaskType.SETUP_TUBE_RACK, params)

        assert result.code == 200
        assert result.msg == "success"
        assert result.task_id == "task-002"

        # Verify expected updates
        update_types = {type(u) for u in result.updates}
        assert RobotUpdate in update_types
        assert TubeRackUpdate in update_types

        # Verify tube rack is mounted with correct ID and description
        rack = next(u for u in result.updates if isinstance(u, TubeRackUpdate))
        assert rack.id == "tube_rack_001"
        assert rack.properties.state == "inuse"
        assert rack.properties.description == "mounted"


class TestCCSimulatorIntegration:
    """Integration tests for CCSimulator."""

    @pytest.mark.asyncio
    async def test_terminate_cc(self, cc_simulator):
        """Test terminate_cc returns success with screen captures."""
        from src.schemas.commands import CCExperimentParams

        params = TerminateCCParams(
            work_station="ws_bic_09_fh_001",
            device_id="cc-001",
            device_type="cc-isco-300p",
            experiment_params=CCExperimentParams(
                silicone_cartridge="silica_40g",
                peak_gathering_mode="peak",
                air_purge_minutes=1.2,
                run_minutes=30,
                need_equilibration=True,
            ),
        )
        result = await cc_simulator.simulate("task-006", TaskType.TERMINATE_CC, params)

        assert result.code == 200
        assert result.msg == "success"
        assert result.task_id == "task-006"

        # Verify CC system is terminated
        cc_update = next(u for u in result.updates if isinstance(u, CCSystemUpdate))
        assert cc_update.properties.state == "idle"

        # Verify images (screen captures) are included
        assert result.images is not None
        assert len(result.images) > 0
