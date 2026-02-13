"""Test device state updates in take_photo task."""

from __future__ import annotations

import pytest

from src.config import MockSettings
from src.generators.entity_updates import create_cc_system_update, create_evaporator_update
from src.schemas.commands import TakePhotoParams, TaskType
from src.simulators.photo_simulator import PhotoSimulator
from src.state.world_state import WorldState


@pytest.fixture
def mock_producer():
    """Mock result producer (not used in these tests)."""
    return None


@pytest.fixture
def settings():
    """Mock settings."""
    return MockSettings(
        robot_id="talos_001",
        base_delay_multiplier=0.0,  # No delay for tests
    )


@pytest.fixture
def world_state():
    """Fresh world state for each test."""
    return WorldState()


@pytest.fixture
def photo_sim(mock_producer, settings, world_state):
    """PhotoSimulator instance with world_state."""
    return PhotoSimulator(mock_producer, settings, world_state=world_state)


class TestPhotoDeviceStateUpdate:
    """Test device state updates are included in take_photo responses."""

    @pytest.mark.asyncio
    async def test_take_photo_includes_cc_device_state(self, photo_sim, world_state):
        """Verify take_photo includes CC system state from world_state."""
        # Setup: Add CC system to world_state
        cc_update = create_cc_system_update(
            system_id="combiflash_001",
            state="running",
            experiment_params={
                "silicone_cartridge": "silica_40g",
                "peak_gathering_mode": "peak",
                "air_purge_minutes": 1.2,
                "run_minutes": 30,
                "need_equilibration": True,
            },
            start_timestamp="2024-01-01T12:00:00Z",
        )
        world_state.apply_updates([cc_update])

        # Execute: Take photo of CC device
        params = TakePhotoParams(
            work_station="cc_station_01",
            device_id="combiflash_001",
            device_type="combiflash",
            components=["screen", "fraction_collector"],
        )
        result = await photo_sim.simulate("task_001", TaskType.TAKE_PHOTO, params)

        # Verify: Result includes both robot and device updates
        assert result.is_success()
        assert len(result.updates) == 2

        robot_update = result.updates[0]
        assert robot_update.type == "robot"
        assert robot_update.id == "talos_001"

        device_update = result.updates[1]
        assert device_update.type == "column_chromatography_machine"
        assert device_update.id == "combiflash_001"
        assert device_update.properties.state == "running"
        assert device_update.properties.experiment_params is not None
        assert device_update.properties.experiment_params.silicone_cartridge == "silica_40g"
        assert device_update.properties.start_timestamp == "2024-01-01T12:00:00Z"

    @pytest.mark.asyncio
    async def test_take_photo_includes_evaporator_state(self, photo_sim, world_state):
        """Verify take_photo includes evaporator state from world_state."""
        # Setup: Add evaporator to world_state
        evap_update = create_evaporator_update(
            evaporator_id="evap_001",
            state="using",
            lower_height=50.0,
            rpm=100,
            target_temperature=45.0,
            current_temperature=44.8,
            target_pressure=50.0,
            current_pressure=52.3,
        )
        world_state.apply_updates([evap_update])

        # Execute: Take photo of evaporator
        params = TakePhotoParams(
            work_station="evap_station_01",
            device_id="evap_001",
            device_type="evaporator",
            components=["flask", "sensor_panel"],
        )
        result = await photo_sim.simulate("task_002", TaskType.TAKE_PHOTO, params)

        # Verify: Result includes both robot and evaporator updates
        assert result.is_success()
        assert len(result.updates) == 2

        robot_update = result.updates[0]
        assert robot_update.type == "robot"

        device_update = result.updates[1]
        assert device_update.type == "evaporator"
        assert device_update.id == "evap_001"
        assert device_update.properties.state == "using"
        assert device_update.properties.lower_height == 50.0
        assert device_update.properties.rpm == 100
        assert device_update.properties.target_temperature == 45.0
        assert device_update.properties.current_temperature == 44.8
        assert device_update.properties.target_pressure == 50.0
        assert device_update.properties.current_pressure == 52.3

    @pytest.mark.asyncio
    async def test_take_photo_without_device_state_in_world(self, photo_sim, world_state):
        """Verify take_photo works when device not in world_state (only robot update)."""
        # Setup: world_state is empty (no device state)

        # Execute: Take photo of device not in world_state
        params = TakePhotoParams(
            work_station="cc_station_01",
            device_id="combiflash_999",
            device_type="combiflash",
            components=["screen"],
        )
        result = await photo_sim.simulate("task_003", TaskType.TAKE_PHOTO, params)

        # Verify: Result includes only robot update (graceful fallback)
        assert result.is_success()
        assert len(result.updates) == 1
        assert result.updates[0].type == "robot"

    @pytest.mark.asyncio
    async def test_take_photo_without_world_state(self, mock_producer, settings):
        """Verify take_photo works when world_state is None (backward compatibility)."""
        # Setup: Create simulator without world_state
        photo_sim_no_ws = PhotoSimulator(mock_producer, settings, world_state=None)

        # Execute: Take photo
        params = TakePhotoParams(
            work_station="cc_station_01",
            device_id="combiflash_001",
            device_type="combiflash",
            components=["screen"],
        )
        result = await photo_sim_no_ws.simulate("task_004", TaskType.TAKE_PHOTO, params)

        # Verify: Result includes only robot update (no crash)
        assert result.is_success()
        assert len(result.updates) == 1
        assert result.updates[0].type == "robot"

    @pytest.mark.asyncio
    async def test_take_photo_unknown_device_type(self, photo_sim, world_state):
        """Verify take_photo handles unknown device types gracefully."""
        # Setup: world_state is empty

        # Execute: Take photo of unknown device type
        params = TakePhotoParams(
            work_station="station_01",
            device_id="mystery_device_001",
            device_type="mystery_device",
            components=["component_a"],
        )
        result = await photo_sim.simulate("task_005", TaskType.TAKE_PHOTO, params)

        # Verify: Result includes only robot update (unknown device type ignored)
        assert result.is_success()
        assert len(result.updates) == 1
        assert result.updates[0].type == "robot"

    @pytest.mark.asyncio
    async def test_take_photo_column_chromatography_device_type(self, photo_sim, world_state):
        """Verify take_photo handles 'column_chromatography' device_type variant."""
        # Setup: Add CC system to world_state
        cc_update = create_cc_system_update(
            system_id="cc_system_001",
            state="mounted",
            experiment_params=None,
            start_timestamp=None,
        )
        world_state.apply_updates([cc_update])

        # Execute: Take photo using 'column_chromatography' device_type
        params = TakePhotoParams(
            work_station="cc_station_01",
            device_id="cc_system_001",
            device_type="column_chromatography",
            components=["screen"],
        )
        result = await photo_sim.simulate("task_006", TaskType.TAKE_PHOTO, params)

        # Verify: Device state is included
        assert result.is_success()
        assert len(result.updates) == 2
        assert result.updates[1].type == "column_chromatography_machine"
        assert result.updates[1].id == "cc_system_001"
