"""Tests for generator modules: entity updates, images, and timing."""

from __future__ import annotations

import re

from src.generators.entity_updates import (
    create_cc_system_update,
    create_ccs_ext_module_update,
    create_evaporator_update,
    create_pcc_left_chute_update,
    create_pcc_right_chute_update,
    create_robot_update,
    create_round_bottom_flask_update,
    create_sample_cartridge_update,
    create_silica_cartridge_update,
    create_tube_rack_update,
    generate_robot_timestamp,
)
from src.generators.images import generate_captured_images, generate_image_url
from src.generators.timing import (
    calculate_cc_duration,
    calculate_delay,
    calculate_evaporation_duration,
    calculate_intermediate_interval,
)
from src.schemas.protocol import ContainerState
from src.schemas.results import (
    CCSExtModuleUpdate,
    CCSystemUpdate,
    EvaporatorUpdate,
    PCCLeftChuteUpdate,
    PCCRightChuteUpdate,
    RobotUpdate,
    RoundBottomFlaskUpdate,
    SampleCartridgeUpdate,
    SilicaCartridgeUpdate,
    TubeRackUpdate,
)

# -- Timestamp Generator Tests ------------------------------------------------


class TestTimestampGenerator:
    """Tests for timestamp generation helper."""

    def test_generate_robot_timestamp_format(self) -> None:
        """Verify timestamp matches spec format: YYYY-MM-DD_HH-MM-SS.mmm"""
        timestamp = generate_robot_timestamp()

        # Should match format: 2025-01-15_10-30-45.123
        pattern = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.\d{3}$"
        assert re.match(pattern, timestamp), f"Timestamp {timestamp} doesn't match spec format"

        # Verify structure: date_time.milliseconds
        parts = timestamp.split(".")
        assert len(parts) == 2, "Timestamp should have date_time and milliseconds parts"
        assert len(parts[1]) == 3, "Milliseconds should be 3 digits"

        # Verify underscore separator between date and time
        date_time = parts[0]
        assert "_" in date_time, "Date and time should be separated by underscore"

        date_part, time_part = date_time.split("_")
        assert len(date_part) == 10, "Date part should be YYYY-MM-DD (10 chars)"
        assert len(time_part) == 8, "Time part should be HH-MM-SS (8 chars)"


# -- Entity Update Factory Tests ----------------------------------------------


class TestEntityUpdateFactories:
    """Tests for entity update factory functions."""

    def test_create_robot_update(self) -> None:
        """Verify type='robot' and correct id/properties."""
        update = create_robot_update("robot-001", "ws-1", "idle")

        assert isinstance(update, RobotUpdate)
        assert update.type == "robot"
        assert update.id == "robot-001"
        assert update.properties.location == "ws-1"
        assert update.properties.state == "idle"

    def test_create_silica_cartridge_update(self) -> None:
        """Verify type='silica_cartridge' and correct id/properties."""
        update = create_silica_cartridge_update("sc-001", "ws-1", "inuse")

        assert isinstance(update, SilicaCartridgeUpdate)
        assert update.type == "silica_cartridge"
        assert update.id == "sc-001"
        assert update.properties.location == "ws-1"
        assert update.properties.state == "inuse"

    def test_create_sample_cartridge_update(self) -> None:
        """Verify type='sample_cartridge' and correct id/properties."""
        update = create_sample_cartridge_update("samp-001", "ws-2", "inuse")

        assert isinstance(update, SampleCartridgeUpdate)
        assert update.type == "sample_cartridge"
        assert update.id == "samp-001"
        assert update.properties.location == "ws-2"
        assert update.properties.state == "inuse"

    def test_create_tube_rack_update(self) -> None:
        """Verify type='tube_rack' and correct id/properties."""
        update = create_tube_rack_update("rack-001", "ws-1", "inuse")

        assert isinstance(update, TubeRackUpdate)
        assert update.type == "tube_rack"
        assert update.id == "rack-001"
        assert update.properties.location == "ws-1"
        assert update.properties.state == "inuse"

    def test_create_round_bottom_flask_update(self) -> None:
        """Verify type='round_bottom_flask' and correct id/properties."""
        update = create_round_bottom_flask_update("flask-001", "evap-1", "evaporating")

        assert isinstance(update, RoundBottomFlaskUpdate)
        assert update.type == "round_bottom_flask"
        assert update.id == "flask-001"
        assert update.properties.location == "evap-1"
        assert update.properties.state == "evaporating"

    def test_create_ccs_ext_module_update(self) -> None:
        """Verify type='ccs_ext_module' and correct id/properties."""
        update = create_ccs_ext_module_update("ext-001", "using")

        assert isinstance(update, CCSExtModuleUpdate)
        assert update.type == "ccs_ext_module"
        assert update.id == "ext-001"
        assert update.properties.state == "using"

    def test_create_cc_system_update_basic(self) -> None:
        """Verify CC system update without experiment_params."""
        update = create_cc_system_update("cc-001", "using")

        assert isinstance(update, CCSystemUpdate)
        assert update.type == "column_chromatography_machine"
        assert update.id == "cc-001"
        assert update.properties.state == "using"
        assert update.properties.experiment_params is None
        assert update.properties.start_timestamp is None

    def test_create_cc_system_update_with_experiment_params(self) -> None:
        """Verify CC system update with experiment_params and start_timestamp."""
        exp_params = {
            "silicone_cartridge": "silica_40g",
            "peak_gathering_mode": "all",
            "air_purge_minutes": 5.0,
            "run_minutes": 30,
            "need_equilibration": True,
        }
        update = create_cc_system_update(
            "cc-001",
            "using",
            experiment_params=exp_params,
            start_timestamp="2025-01-15T10:00:00Z",
        )

        assert isinstance(update, CCSystemUpdate)
        assert update.properties.experiment_params is not None
        assert update.properties.experiment_params.silicone_cartridge == "silica_40g"
        assert update.properties.experiment_params.run_minutes == 30
        assert update.properties.start_timestamp == "2025-01-15T10:00:00Z"

    def test_create_evaporator_update(self) -> None:
        """Verify all sensor fields present in evaporator update."""
        update = create_evaporator_update(
            "evap-001",
            state="using",
            lower_height=150.0,
            rpm=200,
            target_temperature=45.0,
            current_temperature=43.5,
            target_pressure=200.0,
            current_pressure=205.0,
        )

        assert isinstance(update, EvaporatorUpdate)
        assert update.type == "evaporator"
        assert update.id == "evap-001"
        props = update.properties
        assert props.state == "using"
        assert props.lower_height == 150.0
        assert props.rpm == 200
        assert props.target_temperature == 45.0
        assert props.current_temperature == 43.5
        assert props.target_pressure == 200.0
        assert props.current_pressure == 205.0

    def test_create_pcc_left_chute_update(self) -> None:
        """Verify type='pcc_left_chute' and default properties."""
        update = create_pcc_left_chute_update("chute-L1")

        assert isinstance(update, PCCLeftChuteUpdate)
        assert update.type == "pcc_left_chute"
        assert update.id == "chute-L1"
        assert update.properties.pulled_out_mm == 200.0
        assert update.properties.pulled_out_rate == 0.8
        assert update.properties.closed is False
        assert isinstance(update.properties.front_waste_bin, ContainerState)
        assert update.properties.back_waste_bin is None

    def test_create_pcc_right_chute_update(self) -> None:
        """Verify type='pcc_right_chute' and default properties."""
        update = create_pcc_right_chute_update("chute-R1")

        assert isinstance(update, PCCRightChuteUpdate)
        assert update.type == "pcc_right_chute"
        assert update.id == "chute-R1"
        assert update.properties.pulled_out_mm == 200.0
        assert update.properties.pulled_out_rate == 0.8
        assert update.properties.closed is False
        assert update.properties.front_waste_bin is None
        assert isinstance(update.properties.back_waste_bin, ContainerState)


# -- Image Generator Tests ----------------------------------------------------


class TestImageGenerators:
    """Tests for image URL and CapturedImage generation."""

    def test_generate_image_url_format(self) -> None:
        """Verify URL contains base_url/ws_id/device_id/component."""
        url = generate_image_url(
            "http://test:9000/mock-images",
            "ws-1",
            "isco-001",
            "screen",
        )

        assert url.startswith("http://test:9000/mock-images/ws-1/isco-001/screen/")
        assert url.endswith(".jpg")

    def test_generate_captured_images_single_component(self) -> None:
        """String input produces exactly 1 CapturedImage."""
        images = generate_captured_images(
            "http://test:9000/mock-images",
            "ws-1",
            "isco-001",
            "cc_system",
            "screen",
        )

        assert len(images) == 1
        img = images[0]
        assert img.work_station == "ws-1"
        assert img.device_id == "isco-001"
        assert img.device_type == "cc_system"
        assert img.component == "screen"
        assert "http://test:9000/mock-images" in img.url

    def test_generate_captured_images_multiple_components(self) -> None:
        """List input produces matching count of CapturedImages."""
        components = ["screen", "panel", "indicator"]
        images = generate_captured_images(
            "http://test:9000/mock-images",
            "ws-2",
            "evap-001",
            "evaporator",
            components,
        )

        assert len(images) == len(components)
        for img, comp in zip(images, components, strict=True):
            assert img.component == comp
            assert img.device_id == "evap-001"


# -- Timing Calculation Tests -------------------------------------------------


class TestTimingCalculations:
    """Tests for timing utility functions."""

    def test_calculate_delay_with_multiplier(self) -> None:
        """Result = random(min, max) * multiplier, clamped to min_delay."""
        delay = calculate_delay(1.0, 5.0, 0.5, min_delay=0.0)

        # base in [1.0, 5.0], * 0.5 => [0.5, 2.5]
        assert 0.5 <= delay <= 2.5

    def test_calculate_delay_min_delay_clamp(self) -> None:
        """Verify result >= min_delay even when computed value is smaller."""
        # base in [0.01, 0.02], * 0.01 => [0.0001, 0.0002], but min_delay=1.0
        delay = calculate_delay(0.01, 0.02, 0.01, min_delay=1.0)

        assert delay >= 1.0

    def test_calculate_cc_duration(self) -> None:
        """Verify run_minutes * 60 * multiplier."""
        duration = calculate_cc_duration(run_minutes=30, multiplier=0.1)

        assert duration == 30 * 60.0 * 0.1  # 180.0

    def test_calculate_evaporation_duration_with_stop_trigger(self) -> None:
        """With time_in_sec in stop trigger, uses that value * multiplier."""
        profiles = {
            "start": {"lower_height": 100, "rpm": 200},
            "stop": {"trigger": {"type": "time_from_start", "time_in_sec": 600}},
        }
        duration = calculate_evaporation_duration(profiles, multiplier=0.1)

        assert duration == 600 * 0.1  # 60.0

    def test_calculate_evaporation_duration_default(self) -> None:
        """Without stop trigger, defaults to 30 * 60 * multiplier."""
        profiles = {"start": {"lower_height": 100, "rpm": 200}}
        duration = calculate_evaporation_duration(profiles, multiplier=0.1)

        assert duration == 30.0 * 60.0 * 0.1  # 180.0

    def test_calculate_intermediate_interval(self) -> None:
        """Interval = total / (min_updates + 1), at least 1.0s."""
        # total=100, min_updates=3 => 100/4 = 25.0
        interval = calculate_intermediate_interval(100.0, min_updates=3)

        assert interval == 25.0

    def test_calculate_intermediate_interval_floor(self) -> None:
        """Very short duration still returns at least 1.0s."""
        interval = calculate_intermediate_interval(2.0, min_updates=10)

        assert interval >= 1.0

    def test_calculate_intermediate_interval_zero_duration(self) -> None:
        """Zero duration returns 1.0s."""
        interval = calculate_intermediate_interval(0.0)

        assert interval == 1.0
