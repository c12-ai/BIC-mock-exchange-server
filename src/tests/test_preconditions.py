"""Tests for PreconditionChecker class."""

from __future__ import annotations

from src.schemas.commands import (
    CCExperimentParams,
    RobotState,
    SetupCartridgesParams,
    StartCCParams,
    StartEvaporationParams,
    TakePhotoParams,
    TaskType,
    TerminateCCParams,
)
from src.schemas.results import (
    CCSExtModuleUpdate,
    CCSystemUpdate,
    EvaporatorUpdate,
    SampleCartridgeUpdate,
    SilicaCartridgeUpdate,
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
            work_station="ws-1",
            silica_cartridge_type="silica_40g",
            sample_cartridge_location="storage-2",
            sample_cartridge_type="type-2",
            sample_cartridge_id="sac-1",
        )

        result = checker.check(TaskType.SETUP_CARTRIDGES, params)
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
            work_station="ws-1",
            silica_cartridge_type="silica_40g",
            sample_cartridge_location="storage-2",
            sample_cartridge_type="type-2",
            sample_cartridge_id="sac-1",
        )

        result = checker.check(TaskType.SETUP_CARTRIDGES, params)
        assert result.ok is False
        assert result.error_code == 2001


class TestCCPreconditions:
    """Tests for CC start/terminate preconditions."""

    def test_start_cc_passes_when_not_tracked(self) -> None:
        """Verify start_cc passes when CC system not yet tracked."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = StartCCParams(
            work_station="ws-1",
            device_id="cc-1",
            device_type="cc-isco-300p",
            experiment_params=CCExperimentParams(
                silicone_cartridge="silica_40g",
                peak_gathering_mode="all",
                air_purge_minutes=1.2,
                run_minutes=30,
                need_equilibration=True,
            ),
        )

        result = checker.check(TaskType.START_CC, params)
        assert result.ok is True

    def test_start_cc_fails_when_already_running(self) -> None:
        """Verify start_cc fails when CC system already running."""
        ws = WorldState()
        ws.apply_updates(
            [
                CCSystemUpdate(
                    type="column_chromatography_machine",
                    id="cc-1",
                    properties={"state": "running", "experiment_params": None, "start_timestamp": None},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = StartCCParams(
            work_station="ws-1",
            device_id="cc-1",
            device_type="cc-isco-300p",
            experiment_params=CCExperimentParams(
                silicone_cartridge="silica_40g",
                peak_gathering_mode="all",
                air_purge_minutes=1.2,
                run_minutes=30,
                need_equilibration=True,
            ),
        )

        result = checker.check(TaskType.START_CC, params)
        assert result.ok is False
        assert result.error_code == 2020

    def test_terminate_cc_passes_when_running(self) -> None:
        """Verify terminate_cc passes when CC system is running."""
        ws = WorldState()
        ws.apply_updates(
            [
                CCSystemUpdate(
                    type="column_chromatography_machine",
                    id="cc-1",
                    properties={"state": "running", "experiment_params": None, "start_timestamp": None},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = TerminateCCParams(
            work_station="ws-1",
            device_id="cc-1",
            device_type="cc-isco-300p",
            experiment_params=CCExperimentParams(
                silicone_cartridge="silica_40g",
                peak_gathering_mode="peak",
                air_purge_minutes=1.2,
                run_minutes=30,
                need_equilibration=True,
            ),
        )

        result = checker.check(TaskType.TERMINATE_CC, params)
        assert result.ok is True

    def test_terminate_cc_fails_when_not_running(self) -> None:
        """Verify terminate_cc fails when CC system not running."""
        ws = WorldState()
        ws.apply_updates(
            [
                CCSystemUpdate(
                    type="column_chromatography_machine",
                    id="cc-1",
                    properties={"state": "idle", "experiment_params": None, "start_timestamp": None},
                ),
            ]
        )

        checker = PreconditionChecker(ws)
        params = TerminateCCParams(
            work_station="ws-1",
            device_id="cc-1",
            device_type="cc-isco-300p",
            experiment_params=CCExperimentParams(
                silicone_cartridge="silica_40g",
                peak_gathering_mode="peak",
                air_purge_minutes=1.2,
                run_minutes=30,
                need_equilibration=True,
            ),
        )

        result = checker.check(TaskType.TERMINATE_CC, params)
        assert result.ok is False
        assert result.error_code == 2031


class TestEvaporationPreconditions:
    """Tests for evaporation start/stop preconditions."""

    def test_start_evaporation_passes_when_not_tracked(self) -> None:
        """Verify start_evaporation passes when evaporator not yet tracked."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = StartEvaporationParams(
            work_station="ws-1",
            device_id="evap-1",
            device_type="re-buchi-r180",
            profiles={
                "start": {
                    "target_temperature": 60.0,
                    "target_pressure": 100.0,
                    "lower_height": 50.0,
                    "rpm": 120,
                },
            },
        )

        result = checker.check(TaskType.START_EVAPORATION, params)
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
                        "state": "using",
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
            work_station="ws-1",
            device_id="evap-1",
            device_type="re-buchi-r180",
            profiles={
                "start": {
                    "target_temperature": 60.0,
                    "target_pressure": 100.0,
                    "lower_height": 50.0,
                    "rpm": 120,
                },
            },
        )

        result = checker.check(TaskType.START_EVAPORATION, params)
        assert result.ok is False
        assert result.error_code == 2050


class TestNoPreconditionTasks:
    """Tests for tasks with no preconditions."""

    def test_take_photo_always_passes(self) -> None:
        """Verify take_photo has no preconditions and always passes."""
        ws = WorldState()
        checker = PreconditionChecker(ws)

        params = TakePhotoParams(
            work_station="ws-1",
            device_id="cam-1",
            device_type="camera",
            components=["component1", "component2"],
        )

        result = checker.check(TaskType.TAKE_PHOTO, params)
        assert result.ok is True
