"""Integration test for take_photo with real workflow scenarios."""

from __future__ import annotations

import pytest

from src.config import MockSettings
from src.generators.entity_updates import (
    create_cc_system_update,
    create_evaporator_update,
)
from src.schemas.commands import TakePhotoParams, TaskType
from src.simulators.photo_simulator import PhotoSimulator
from src.state.world_state import WorldState


@pytest.fixture
def mock_producer():
    """Mock result producer."""
    return None


@pytest.fixture
def settings():
    """Mock settings."""
    return MockSettings(robot_id="talos_001", base_delay_multiplier=0.0)


@pytest.fixture
def world_state():
    """Fresh world state for each test."""
    return WorldState()


@pytest.fixture
def photo_sim(mock_producer, settings, world_state):
    """PhotoSimulator instance with world_state."""
    return PhotoSimulator(mock_producer, settings, world_state=world_state)


class TestPhotoIntegrationWorkflow:
    """Integration tests simulating real workflow scenarios."""

    @pytest.mark.asyncio
    async def test_cc_workflow_photo_after_start(self, photo_sim, world_state):
        """Simulate: start_cc -> take_photo (should include running CC state)."""
        # 1. Simulate start_cc completing and updating world_state
        cc_running_update = create_cc_system_update(
            system_id="combiflash_001",
            state="running",
            experiment_params={
                "silicone_cartridge": "silica_40g",
                "peak_gathering_mode": "peak",
                "air_purge_minutes": 1.2,
                "run_minutes": 30,
                "need_equilibration": True,
            },
            start_timestamp="2024-01-01T10:00:00Z",
        )
        world_state.apply_updates([cc_running_update])

        # 2. Take photo of the running CC device
        params = TakePhotoParams(
            work_station="cc_station_01",
            device_id="combiflash_001",
            device_type="combiflash",
            components=["screen", "fraction_collector", "column"],
        )
        result = await photo_sim.simulate("photo_001", TaskType.TAKE_PHOTO, params)

        # 3. Verify response includes CC state
        assert result.is_success()
        assert len(result.updates) == 2

        # Robot update
        assert result.updates[0].type == "robot"
        assert result.updates[0].id == "talos_001"

        # CC device update with experiment in progress
        cc_update = result.updates[1]
        assert cc_update.type == "column_chromatography_machine"
        assert cc_update.id == "combiflash_001"
        assert cc_update.properties.state == "running"
        assert cc_update.properties.experiment_params.silicone_cartridge == "silica_40g"
        assert cc_update.properties.start_timestamp == "2024-01-01T10:00:00Z"

        # Verify images were captured
        assert result.images is not None
        assert len(result.images) == 3
        assert result.images[0].component == "screen"
        assert result.images[1].component == "fraction_collector"
        assert result.images[2].component == "column"

    @pytest.mark.asyncio
    async def test_evaporation_workflow_photo_during_evaporation(self, photo_sim, world_state):
        """Simulate: start_evaporation -> take_photo (should include evaporator state)."""
        # 1. Simulate start_evaporation completing and updating world_state
        evap_running_update = create_evaporator_update(
            evaporator_id="evap_001",
            state="using",
            lower_height=50.0,
            rpm=120,
            target_temperature=45.0,
            current_temperature=42.3,
            target_pressure=50.0,
            current_pressure=51.2,
        )
        world_state.apply_updates([evap_running_update])

        # 2. Take photo of the evaporator while it's running
        params = TakePhotoParams(
            work_station="evap_station_01",
            device_id="evap_001",
            device_type="evaporator",
            components=["flask", "condenser", "sensor_panel"],
        )
        result = await photo_sim.simulate("photo_002", TaskType.TAKE_PHOTO, params)

        # 3. Verify response includes evaporator state
        assert result.is_success()
        assert len(result.updates) == 2

        # Robot update
        assert result.updates[0].type == "robot"

        # Evaporator update with current sensor readings
        evap_update = result.updates[1]
        assert evap_update.type == "evaporator"
        assert evap_update.id == "evap_001"
        assert evap_update.properties.state == "using"
        assert evap_update.properties.lower_height == 50.0
        assert evap_update.properties.rpm == 120
        assert evap_update.properties.target_temperature == 45.0
        assert evap_update.properties.current_temperature == 42.3
        assert evap_update.properties.target_pressure == 50.0
        assert evap_update.properties.current_pressure == 51.2

    @pytest.mark.asyncio
    async def test_cc_workflow_photo_after_terminate(self, photo_sim, world_state):
        """Simulate: terminate_cc -> take_photo (should include terminated CC state)."""
        # 1. Simulate terminate_cc completing and updating world_state
        cc_terminated_update = create_cc_system_update(
            system_id="combiflash_001",
            state="idle",
            experiment_params={
                "silicone_cartridge": "silica_40g",
                "peak_gathering_mode": "peak",
                "air_purge_minutes": 1.2,
                "run_minutes": 30,
                "need_equilibration": True,
            },
            start_timestamp="2024-01-01T10:00:00Z",
        )
        world_state.apply_updates([cc_terminated_update])

        # 2. Take photo after termination
        params = TakePhotoParams(
            work_station="cc_station_01",
            device_id="combiflash_001",
            device_type="combiflash",
            components=["screen"],
        )
        result = await photo_sim.simulate("photo_003", TaskType.TAKE_PHOTO, params)

        # 3. Verify response includes idle state
        assert result.is_success()
        assert len(result.updates) == 2

        cc_update = result.updates[1]
        assert cc_update.type == "column_chromatography_machine"
        assert cc_update.properties.state == "idle"
        assert cc_update.properties.experiment_params is not None

    @pytest.mark.asyncio
    async def test_multiple_photos_preserve_device_state(self, photo_sim, world_state):
        """Verify multiple photos of same device preserve device state."""
        # 1. Setup evaporator state
        evap_update = create_evaporator_update(
            evaporator_id="evap_001",
            state="using",
            lower_height=50.0,
            rpm=120,
            target_temperature=45.0,
            current_temperature=42.3,
            target_pressure=50.0,
            current_pressure=51.2,
        )
        world_state.apply_updates([evap_update])

        # 2. Take first photo
        params1 = TakePhotoParams(
            work_station="evap_station_01",
            device_id="evap_001",
            device_type="evaporator",
            components=["flask"],
        )
        result1 = await photo_sim.simulate("photo_004", TaskType.TAKE_PHOTO, params1)

        # 3. Take second photo (without changing world_state)
        params2 = TakePhotoParams(
            work_station="evap_station_01",
            device_id="evap_001",
            device_type="evaporator",
            components=["sensor_panel"],
        )
        result2 = await photo_sim.simulate("photo_005", TaskType.TAKE_PHOTO, params2)

        # 4. Verify both photos have same device state
        assert result1.is_success()
        assert result2.is_success()
        assert len(result1.updates) == 2
        assert len(result2.updates) == 2

        evap1 = result1.updates[1]
        evap2 = result2.updates[1]
        assert evap1.properties.state == evap2.properties.state
        assert evap1.properties.rpm == evap2.properties.rpm
        assert evap1.properties.current_temperature == evap2.properties.current_temperature
