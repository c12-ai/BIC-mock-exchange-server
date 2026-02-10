"""Tests for PreconditionChecker class."""

from __future__ import annotations

from src.schemas.commands import (
    CCExperimentParams,
    CollapseCartridgesParams,
    ReturnCartridgesParams,
    ReturnCCSBinsParams,
    ReturnTubeRackParams,
    RobotState,
    SetupCartridgesParams,
    StartCCParams,
    StartEvaporationParams,
    StopEvaporationParams,
    TakePhotoParams,
    TaskName,
    TerminateCCParams,
)
from src.schemas.results import (
    CCSExtModuleUpdate,
    CCSystemUpdate,
    EvaporatorUpdate,
    PCCLeftChuteUpdate,
    SampleCartridgeUpdate,
    SilicaCartridgeUpdate,
    TubeRackUpdate,
)
from src.state.preconditions import PreconditionChecker
from src.state.world_state import WorldState


class TestSetupCartridgesPreconditions:
    """Tests for setup_cartridges preconditions."""

    def test_passes_when_ext_module_not_tracked(self) -> None:
        """Verify passes when ext_module not in world state."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = SetupCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_location_id="storage-1",
            silica_cartridge_type="type-1",
            silica_cartridge_id="sc-1",
            sample_cartridge_location_id="storage-2",
            sample_cartridge_type="type-2",
            sample_cartridge_id="sac-1",
        )

        result = checker.check(TaskName.SETUP_CARTRIDGES, params)
        assert result.ok is True

    def test_fails_when_ext_module_already_using(self) -> None:
        """Verify fails when ext_module is already 'using'."""
        ws = WorldState()
        ws.apply_updates(
            [
                CCSExtModuleUpdate(
                    type="ccs_ext_module",
                    id="ws-1",
                    properties={"state": "using"},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = SetupCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_location_id="storage-1",
            silica_cartridge_type="type-1",
            silica_cartridge_id="sc-1",
            sample_cartridge_location_id="storage-2",
            sample_cartridge_type="type-2",
            sample_cartridge_id="sac-1",
        )

        result = checker.check(TaskName.SETUP_CARTRIDGES, params)
        assert result.ok is False
        assert result.error_code == 2001


class TestCollapseCartridgesPreconditions:
    """Tests for collapse_cartridges preconditions."""

    def test_passes_when_both_cartridges_used(self) -> None:
        """Verify passes when both cartridges are 'used'."""
        ws = WorldState()
        ws.apply_updates(
            [
                SilicaCartridgeUpdate(
                    type="silica_cartridge",
                    id="sc-1",
                    properties={"location": "ws-1", "state": "used"},
                ),
                SampleCartridgeUpdate(
                    type="sample_cartridge",
                    id="sac-1",
                    properties={"location": "ws-1", "state": "used"},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = CollapseCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_id="sc-1",
            sample_cartridge_id="sac-1",
        )

        result = checker.check(TaskName.COLLAPSE_CARTRIDGES, params)
        assert result.ok is True

    def test_fails_when_silica_cartridge_missing(self) -> None:
        """Verify fails when silica_cartridge not tracked."""
        ws = WorldState()
        ws.apply_updates(
            [
                SampleCartridgeUpdate(
                    type="sample_cartridge",
                    id="sac-1",
                    properties={"location": "ws-1", "state": "used"},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = CollapseCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_id="sc-1",
            sample_cartridge_id="sac-1",
        )

        result = checker.check(TaskName.COLLAPSE_CARTRIDGES, params)
        assert result.ok is False
        assert result.error_code == 2010


class TestCCPreconditions:
    """Tests for CC start/terminate preconditions."""

    def test_start_cc_passes_when_not_tracked(self) -> None:
        """Verify start_cc passes when CC system not yet tracked."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = StartCCParams(
            work_station_id="ws-1",
            device_id="cc-1",
            device_type="cc_device",
            experiment_params=CCExperimentParams(
                silicone_column="40g",
                peak_gathering_mode="all",
                air_clean_minutes=5,
                run_minutes=30,
                need_equilibration=True,
            ),
            end_state=RobotState.IDLE,
        )

        result = checker.check(TaskName.START_CC, params)
        assert result.ok is True

    def test_start_cc_fails_when_already_running(self) -> None:
        """Verify start_cc fails when CC system already running."""
        ws = WorldState()
        ws.apply_updates(
            [
                CCSystemUpdate(
                    type="column_chromatography_system",
                    id="cc-1",
                    properties={"state": "running", "experiment_params": None, "start_timestamp": None},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = StartCCParams(
            work_station_id="ws-1",
            device_id="cc-1",
            device_type="cc_device",
            experiment_params=CCExperimentParams(
                silicone_column="40g",
                peak_gathering_mode="all",
                air_clean_minutes=5,
                run_minutes=30,
                need_equilibration=True,
            ),
            end_state=RobotState.IDLE,
        )

        result = checker.check(TaskName.START_CC, params)
        assert result.ok is False
        assert result.error_code == 2020

    def test_terminate_cc_passes_when_running(self) -> None:
        """Verify terminate_cc passes when CC system is running."""
        ws = WorldState()
        ws.apply_updates(
            [
                CCSystemUpdate(
                    type="column_chromatography_system",
                    id="cc-1",
                    properties={"state": "running", "experiment_params": None, "start_timestamp": None},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = TerminateCCParams(
            work_station_id="ws-1",
            device_id="cc-1",
            device_type="cc_device",
            end_state=RobotState.IDLE,
        )

        result = checker.check(TaskName.TERMINATE_CC, params)
        assert result.ok is True

    def test_terminate_cc_fails_when_not_running(self) -> None:
        """Verify terminate_cc fails when CC system not running."""
        ws = WorldState()
        ws.apply_updates(
            [
                CCSystemUpdate(
                    type="column_chromatography_system",
                    id="cc-1",
                    properties={"state": "terminated", "experiment_params": None, "start_timestamp": None},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = TerminateCCParams(
            work_station_id="ws-1",
            device_id="cc-1",
            device_type="cc_device",
            end_state=RobotState.IDLE,
        )

        result = checker.check(TaskName.TERMINATE_CC, params)
        assert result.ok is False
        assert result.error_code == 2031


class TestEvaporationPreconditions:
    """Tests for evaporation start/stop preconditions."""

    def test_start_evaporation_passes_when_not_tracked(self) -> None:
        """Verify start_evaporation passes when evaporator not yet tracked."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = StartEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-1",
            device_type="evaporator",
            profiles={
                "start": {
                    "target_temperature": 60.0,
                    "target_pressure": 100.0,
                    "lower_height": 50.0,
                    "rpm": 120,
                },
            },
            post_run_state=RobotState.IDLE,
        )

        result = checker.check(TaskName.START_EVAPORATION, params)
        assert result.ok is True

    def test_start_evaporation_fails_when_already_running(self) -> None:
        """Verify start_evaporation fails when evaporator already running."""
        ws = WorldState()
        ws.apply_updates(
            [
                EvaporatorUpdate(
                    type="evaporator",
                    id="evap-1",
                    properties={
                        "running": True,
                        "lower_height": 50.0,
                        "rpm": 120,
                        "target_temperature": 60.0,
                        "current_temperature": 45.0,
                        "target_pressure": 100.0,
                        "current_pressure": 500.0,
                    },
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = StartEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-1",
            device_type="evaporator",
            profiles={
                "start": {
                    "target_temperature": 60.0,
                    "target_pressure": 100.0,
                    "lower_height": 50.0,
                    "rpm": 120,
                },
            },
            post_run_state=RobotState.IDLE,
        )

        result = checker.check(TaskName.START_EVAPORATION, params)
        assert result.ok is False
        assert result.error_code == 2050

    def test_stop_evaporation_passes_when_running(self) -> None:
        """Verify stop_evaporation passes when evaporator is running."""
        ws = WorldState()
        ws.apply_updates(
            [
                EvaporatorUpdate(
                    type="evaporator",
                    id="evap-1",
                    properties={
                        "running": True,
                        "lower_height": 50.0,
                        "rpm": 120,
                        "target_temperature": 60.0,
                        "current_temperature": 60.0,
                        "target_pressure": 100.0,
                        "current_pressure": 100.0,
                    },
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = StopEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-1",
            device_type="evaporator",
        )

        result = checker.check(TaskName.STOP_EVAPORATION, params)
        assert result.ok is True

    def test_stop_evaporation_fails_when_not_running(self) -> None:
        """Verify stop_evaporation fails when evaporator not running."""
        ws = WorldState()
        ws.apply_updates(
            [
                EvaporatorUpdate(
                    type="evaporator",
                    id="evap-1",
                    properties={
                        "running": False,
                        "lower_height": 0.0,
                        "rpm": 0,
                        "target_temperature": 25.0,
                        "current_temperature": 25.0,
                        "target_pressure": 1013.0,
                        "current_pressure": 1013.0,
                    },
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = StopEvaporationParams(
            work_station_id="ws-1",
            device_id="evap-1",
            device_type="evaporator",
        )

        result = checker.check(TaskName.STOP_EVAPORATION, params)
        assert result.ok is False
        assert result.error_code == 2061


class TestCleanupPreconditions:
    """Tests for cleanup task preconditions."""

    def test_return_ccs_bins_passes_when_bins_in_chute(self) -> None:
        """Verify return_ccs_bins passes when bins exist in chutes."""
        ws = WorldState()
        ws.apply_updates(
            [
                PCCLeftChuteUpdate(
                    type="pcc_left_chute",
                    id="ws-1",
                    properties={
                        "pulled_out_mm": 100.0,
                        "pulled_out_rate": 5.0,
                        "closed": False,
                        "front_waste_bin": "open",
                        "back_waste_bin": None,
                    },
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = ReturnCCSBinsParams(
            work_station_id="ws-1",
            waste_area_id="waste-1",
        )

        result = checker.check(TaskName.RETURN_CCS_BINS, params)
        assert result.ok is True

    def test_return_ccs_bins_fails_when_no_bins(self) -> None:
        """Verify return_ccs_bins fails when no bins in chutes."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = ReturnCCSBinsParams(
            work_station_id="ws-1",
            waste_area_id="waste-1",
        )

        result = checker.check(TaskName.RETURN_CCS_BINS, params)
        assert result.ok is False
        assert result.error_code == 2070

    def test_return_cartridges_passes_when_both_exist(self) -> None:
        """Verify return_cartridges passes when both cartridges exist."""
        ws = WorldState()
        ws.apply_updates(
            [
                SilicaCartridgeUpdate(
                    type="silica_cartridge",
                    id="sc-1",
                    properties={"location": "ws-1", "state": "used"},
                ),
                SampleCartridgeUpdate(
                    type="sample_cartridge",
                    id="sac-1",
                    properties={"location": "ws-1", "state": "used"},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = ReturnCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_id="sc-1",
            sample_cartridge_id="sac-1",
            waste_area_id="waste-1",
        )

        result = checker.check(TaskName.RETURN_CARTRIDGES, params)
        assert result.ok is True

    def test_return_cartridges_fails_when_silica_missing(self) -> None:
        """Verify return_cartridges fails when silica_cartridge not found."""
        ws = WorldState()
        ws.apply_updates(
            [
                SampleCartridgeUpdate(
                    type="sample_cartridge",
                    id="sac-1",
                    properties={"location": "ws-1", "state": "used"},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = ReturnCartridgesParams(
            work_station_id="ws-1",
            silica_cartridge_id="sc-1",
            sample_cartridge_id="sac-1",
            waste_area_id="waste-1",
        )

        result = checker.check(TaskName.RETURN_CARTRIDGES, params)
        assert result.ok is False
        assert result.error_code == 2080

    def test_return_tube_rack_passes_when_exists(self) -> None:
        """Verify return_tube_rack passes when tube_rack exists."""
        ws = WorldState()
        ws.apply_updates(
            [
                TubeRackUpdate(
                    type="tube_rack",
                    id="tr-1",
                    properties={"location": "ws-1", "state": "used"},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = ReturnTubeRackParams(
            work_station_id="ws-1",
            tube_rack_id="tr-1",
            waste_area_id="waste-1",
        )

        result = checker.check(TaskName.RETURN_TUBE_RACK, params)
        assert result.ok is True

    def test_return_tube_rack_fails_when_not_found(self) -> None:
        """Verify return_tube_rack fails when tube_rack not found."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = ReturnTubeRackParams(
            work_station_id="ws-1",
            tube_rack_id="tr-1",
            waste_area_id="waste-1",
        )

        result = checker.check(TaskName.RETURN_TUBE_RACK, params)
        assert result.ok is False
        assert result.error_code == 2090


class TestNoPreconditionTasks:
    """Tests for tasks with no preconditions."""

    def test_take_photo_always_passes(self) -> None:
        """Verify take_photo has no preconditions and always passes."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = TakePhotoParams(
            work_station_id="ws-1",
            device_id="cam-1",
            device_type="camera",
            components=["component1", "component2"],
            end_state=RobotState.IDLE,
        )

        result = checker.check(TaskName.TAKE_PHOTO, params)
        assert result.ok is True
