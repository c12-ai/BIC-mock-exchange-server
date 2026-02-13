"""Tests for schema parsing and serialization."""

from __future__ import annotations

import json

from pydantic import TypeAdapter

from src.schemas.commands import (
    CCExperimentParams,
    EvaporationProfile,
    EvaporationProfiles,
    EvaporationTrigger,
    RobotCommand,
    RobotState,
    SetupCartridgesParams,
    StartCCParams,
    TaskType,
)
from src.schemas.results import (
    EntityUpdate,
    RobotProperties,
    RobotResult,
    RobotUpdate,
)


class TestCommandSchemas:
    """Tests for command schema parsing."""

    def test_robot_command_parsing(self) -> None:
        """Parse RobotCommand from dict with task_id, task_type, params."""
        data = {
            "task_id": "task-001",
            "task_type": "setup_tubes_to_column_machine",
            "params": {
                "silica_cartridge_type": "silica_40g",
                "sample_cartridge_location": "loc-2",
                "sample_cartridge_type": "sample",
                "sample_cartridge_id": "samp-001",
                "work_station": "ws-1",
            },
        }
        cmd = RobotCommand.model_validate(data)

        assert cmd.task_id == "task-001"
        assert cmd.task_type == TaskType.SETUP_CARTRIDGES
        assert cmd.params["work_station"] == "ws-1"

    def test_setup_cartridges_params(self) -> None:
        """Validate all required fields for SetupCartridgesParams."""
        params = SetupCartridgesParams(
            silica_cartridge_type="silica_40g",
            sample_cartridge_location="loc-2",
            sample_cartridge_type="sample",
            sample_cartridge_id="samp-001",
            work_station="ws-1",
        )

        assert params.sample_cartridge_id == "samp-001"
        assert params.work_station == "ws-1"
        assert params.silica_cartridge_type == "silica_40g"

    def test_start_cc_params_with_experiment(self) -> None:
        """Validate nested CCExperimentParams within StartCCParams."""
        exp = CCExperimentParams(
            silicone_cartridge="silica_40g",
            peak_gathering_mode="all",
            air_purge_minutes=5.0,
            run_minutes=30,
            need_equilibration=True,
            left_rack="16x100",
            right_rack=None,
        )
        params = StartCCParams(
            work_station="ws-1",
            device_id="isco-001",
            device_type="cc_system",
            experiment_params=exp,
        )

        assert params.experiment_params.silicone_cartridge == "silica_40g"
        assert params.experiment_params.run_minutes == 30
        assert params.experiment_params.need_equilibration is True

    def test_evaporation_profiles_parsing(self) -> None:
        """Complex nested profiles with trigger parse correctly."""
        data = {
            "start": {
                "lower_height": 150.0,
                "rpm": 200,
                "target_temperature": 45.0,
                "target_pressure": 300.0,
            },
            "updates": [
                {
                    "lower_height": 150.0,
                    "rpm": 200,
                    "target_temperature": 50.0,
                    "target_pressure": 150.0,
                    "trigger": {
                        "type": "time_from_start",
                        "time_in_sec": 600,
                    },
                },
            ],
        }
        profiles = EvaporationProfiles.model_validate(data)

        assert isinstance(profiles.start, EvaporationProfile)
        assert profiles.start.target_temperature == 45.0
        assert len(profiles.updates) == 1
        assert profiles.updates[0].trigger is not None
        assert isinstance(profiles.updates[0].trigger, EvaporationTrigger)
        assert profiles.updates[0].trigger.time_in_sec == 600
        assert profiles.updates[0].target_pressure == 150.0


class TestResultSchemas:
    """Tests for result schema serialization and deserialization."""

    def test_robot_result_serialization(self) -> None:
        """model_dump_json roundtrip preserves data."""
        result = RobotResult(
            code=200,
            msg="Success",
            task_id="task-001",
            updates=[],
        )
        json_str = result.model_dump_json()
        restored = RobotResult.model_validate_json(json_str)

        assert restored.code == 200
        assert restored.msg == "Success"
        assert restored.task_id == "task-001"
        assert restored.updates == []

    def test_robot_result_is_success(self) -> None:
        """code=200 -> True, code=1 -> False."""
        success = RobotResult(code=200, msg="OK", task_id="t-1", updates=[])
        failure = RobotResult(code=1, msg="Error", task_id="t-2", updates=[])

        assert success.is_success() is True
        assert failure.is_success() is False

    def test_entity_update_discriminated_union(self) -> None:
        """Parse RobotUpdate from dict with type='robot' via discriminated union."""
        data = {
            "type": "robot",
            "id": "robot-001",
            "properties": {
                "location": "ws-1",
                "state": "idle",
            },
        }
        adapter = TypeAdapter(EntityUpdate)
        update = adapter.validate_python(data)

        assert isinstance(update, RobotUpdate)
        assert update.type == "robot"
        assert update.id == "robot-001"
        assert update.properties.location == "ws-1"

    def test_robot_result_with_updates(self) -> None:
        """RobotResult with a list of entity updates serializes correctly."""
        robot_update = RobotUpdate(
            id="robot-001",
            properties=RobotProperties(location="ws-1", state="idle"),
        )
        result = RobotResult(
            code=200,
            msg="Task completed",
            task_id="task-001",
            updates=[robot_update],
        )

        json_str = result.model_dump_json()
        parsed = json.loads(json_str)

        assert len(parsed["updates"]) == 1
        assert parsed["updates"][0]["type"] == "robot"
        assert parsed["updates"][0]["id"] == "robot-001"

        # Roundtrip via model_validate_json
        restored = RobotResult.model_validate_json(json_str)
        assert len(restored.updates) == 1
        assert isinstance(restored.updates[0], RobotUpdate)
        assert restored.updates[0].properties.state == "idle"
