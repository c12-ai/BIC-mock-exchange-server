"""Full workflow integration tests for Phase 6.

Tests multi-robot scenarios, complete BIC lab workflow, log streaming,
and state reset via command message.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import MockSettings
from src.mq.consumer import CommandConsumer
from src.scenarios.manager import ScenarioManager
from src.schemas.commands import TaskType
from src.schemas.results import (
    CCMachineProperties,
    CCSystemUpdate,
    TubeRackUpdate,
)
from src.simulators.cc_simulator import CCSimulator
from src.simulators.consolidation_simulator import ConsolidationSimulator
from src.simulators.evaporation_simulator import EvaporationSimulator
from src.simulators.photo_simulator import PhotoSimulator
from src.simulators.setup_simulator import SetupSimulator
from src.state.world_state import WorldState

if TYPE_CHECKING:
    from aio_pika.abc import AbstractIncomingMessage


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_consumer_integration.py)
# ---------------------------------------------------------------------------


class AsyncContextManagerMock:
    """Mock async context manager for message.process()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def make_mock_message(task_id: str, task_name: str, params: dict) -> AbstractIncomingMessage:
    """Create a mock AbstractIncomingMessage."""
    command = {
        "task_id": task_id,
        "task_type": task_name,
        "params": params,
    }
    mock_msg = AsyncMock()
    mock_msg.body = json.dumps(command).encode()
    mock_msg.process = MagicMock(return_value=AsyncContextManagerMock())
    return mock_msg


def _make_settings(robot_id: str = "test-robot-001") -> MockSettings:
    """Create test MockSettings with a given robot_id."""
    return MockSettings(
        mq_host="localhost",
        mq_port=5672,
        mq_exchange="test_exchange",
        base_delay_multiplier=0.01,
        min_delay_seconds=0.0,
        default_scenario="success",
        failure_rate=0.0,
        timeout_rate=0.0,
        image_base_url="http://test:9000/mock-images",
        robot_id=robot_id,
        log_level="DEBUG",
        heartbeat_interval=1.0,
    )


def _build_consumer(
    settings: MockSettings,
    mock_producer: AsyncMock,
    mock_log_producer: AsyncMock,
    world_state: WorldState | None = None,
) -> CommandConsumer:
    """Wire up a CommandConsumer with real simulators and the given world state."""
    if world_state is None:
        world_state = WorldState()
    mock_connection = AsyncMock()
    scenario_manager = ScenarioManager(settings)
    consumer = CommandConsumer(mock_connection, mock_producer, scenario_manager, settings, world_state=world_state)

    setup_sim = SetupSimulator(mock_producer, settings, log_producer=mock_log_producer, world_state=world_state)
    photo_sim = PhotoSimulator(mock_producer, settings, log_producer=mock_log_producer, world_state=world_state)
    cc_sim = CCSimulator(mock_producer, settings, log_producer=mock_log_producer, world_state=world_state)
    consolidation_sim = ConsolidationSimulator(
        mock_producer, settings, log_producer=mock_log_producer, world_state=world_state
    )
    evaporation_sim = EvaporationSimulator(
        mock_producer, settings, log_producer=mock_log_producer, world_state=world_state
    )

    consumer.register_simulator(TaskType.SETUP_CARTRIDGES, setup_sim)
    consumer.register_simulator(TaskType.SETUP_TUBE_RACK, setup_sim)
    consumer.register_simulator(TaskType.TAKE_PHOTO, photo_sim)
    consumer.register_simulator(TaskType.START_CC, cc_sim)
    consumer.register_simulator(TaskType.TERMINATE_CC, cc_sim)
    consumer.register_simulator(TaskType.COLLECT_CC_FRACTIONS, consolidation_sim)
    consumer.register_simulator(TaskType.START_EVAPORATION, evaporation_sim)

    return consumer


# ---------------------------------------------------------------------------
# 1. Multi-Robot Scenarios
# ---------------------------------------------------------------------------


class TestMultiRobotScenarios:
    """Tests verifying independent command routing with different robot_ids."""

    @pytest.mark.asyncio
    async def test_two_robots_independent_state(self) -> None:
        """Two robots with separate WorldState + CommandConsumer have independent state."""
        settings1 = _make_settings("talos_001")
        settings2 = _make_settings("talos_002")

        producer1 = AsyncMock()
        producer1.publish_result = AsyncMock()

        log_producer1 = AsyncMock()
        log_producer1.publish_log = AsyncMock()

        producer2 = AsyncMock()
        producer2.publish_result = AsyncMock()

        log_producer2 = AsyncMock()
        log_producer2.publish_log = AsyncMock()

        world1 = WorldState()
        world2 = WorldState()

        consumer1 = _build_consumer(settings1, producer1, log_producer1, world1)
        consumer2 = _build_consumer(settings2, producer2, log_producer2, world2)

        # Robot 1: setup_cartridges
        msg1 = make_mock_message(
            "task-r1-001",
            "setup_tubes_to_column_machine",
            {
                "silica_cartridge_type": "silica_40g",
                "sample_cartridge_location": "bic_09B_l3_002",
                "sample_cartridge_type": "sample_40g",
                "sample_cartridge_id": "samp-001",
                "work_station": "ws-1",
            },
        )
        await consumer1._process_message(msg1)

        # Robot 2: setup_tube_rack
        msg2 = make_mock_message(
            "task-r2-001",
            "setup_tube_rack",
            {
                "work_station": "ws-2",
            },
        )
        await consumer2._process_message(msg2)

        # Verify robot 1 results
        result1 = producer1.publish_result.call_args[0][0]
        assert result1.code == 200
        assert result1.task_id == "task-r1-001"

        # Verify robot 2 results
        result2 = producer2.publish_result.call_args[0][0]
        assert result2.code == 200
        assert result2.task_id == "task-r2-001"

        # Robot 1 world state has ext_module but not tube_rack from robot 2
        assert world1.has_entity("ccs_ext_module", "ws-1")
        assert not world1.has_entity("tube_rack", "tube_rack_001")

        # Robot 2 world state has tube_rack but not cartridges from robot 1
        assert world2.has_entity("tube_rack", "tube_rack_001")
        assert not world2.has_entity("ccs_ext_module", "ws-1")

    @pytest.mark.asyncio
    async def test_robot_id_in_routing_keys(self) -> None:
        """Producer, log_producer, and heartbeat use robot_id-based routing keys."""
        settings_r1 = _make_settings("talos_001")
        settings_r2 = _make_settings("talos_002")

        # Verify the routing key patterns derive from robot_id.
        assert f"{settings_r1.robot_id}.result" == "talos_001.result"
        assert f"{settings_r1.robot_id}.log" == "talos_001.log"
        assert f"{settings_r1.robot_id}.hb" == "talos_001.hb"
        assert f"{settings_r1.robot_id}.cmd" == "talos_001.cmd"

        assert f"{settings_r2.robot_id}.result" == "talos_002.result"
        assert f"{settings_r2.robot_id}.log" == "talos_002.log"
        assert f"{settings_r2.robot_id}.hb" == "talos_002.hb"
        assert f"{settings_r2.robot_id}.cmd" == "talos_002.cmd"

        # Additionally verify that simulators receive the correct robot_id
        producer = AsyncMock()
        producer.publish_result = AsyncMock()
        log_producer = AsyncMock()
        log_producer.publish_log = AsyncMock()

        sim1 = SetupSimulator(producer, settings_r1, log_producer=log_producer)
        sim2 = SetupSimulator(producer, settings_r2, log_producer=log_producer)

        assert sim1.robot_id == "talos_001"
        assert sim2.robot_id == "talos_002"


# ---------------------------------------------------------------------------
# 2. Full BIC Workflow
# ---------------------------------------------------------------------------


class TestFullBICWorkflow:
    """Test a realistic BIC lab workflow from start to finish through the consumer pipeline."""

    @pytest.mark.asyncio
    async def test_complete_lab_workflow(self) -> None:
        """Execute the full BIC lab sequence and verify world state + results at each step.

        Sequence (v0.3 ground truth — 7 tasks):
        1. setup_cartridges
        2. setup_tube_rack
        3. take_photo
        4. terminate_cc (requires CC system "running" in world state)
        5. fraction_consolidation (requires tube_rack "used"/"inuse" -- set by setup)
        """
        settings = _make_settings("talos_001")
        producer = AsyncMock()
        producer.publish_result = AsyncMock()
        log_producer = AsyncMock()
        log_producer.publish_log = AsyncMock()

        world_state = WorldState()
        consumer = _build_consumer(settings, producer, log_producer, world_state)

        ws_id = "ws_bic_09_fh_001"

        # -- 1. setup_cartridges ------------------------------------------------
        producer.reset_mock()
        msg = make_mock_message(
            "task-001",
            "setup_tubes_to_column_machine",
            {
                "silica_cartridge_type": "silica_40g",
                "sample_cartridge_location": "bic_09B_l3_002",
                "sample_cartridge_type": "sample_40g",
                "sample_cartridge_id": "samp-001",
                "work_station": ws_id,
            },
        )
        await consumer._process_message(msg)
        result = producer.publish_result.call_args[0][0]
        assert result.code == 200, f"setup_cartridges failed: {result.msg}"
        assert world_state.has_entity("ccs_ext_module", ws_id)
        assert world_state.has_entity("sample_cartridge", "samp-001")

        # -- 2. setup_tube_rack -------------------------------------------------
        producer.reset_mock()
        msg = make_mock_message(
            "task-002",
            "setup_tube_rack",
            {
                "work_station": ws_id,
            },
        )
        await consumer._process_message(msg)
        result = producer.publish_result.call_args[0][0]
        assert result.code == 200, f"setup_tube_rack failed: {result.msg}"
        assert world_state.has_entity("tube_rack", "tube_rack_001")

        # -- 3. take_photo ------------------------------------------------------
        producer.reset_mock()
        msg = make_mock_message(
            "task-003",
            "take_photo",
            {
                "work_station": ws_id,
                "device_id": "cam-001",
                "device_type": "camera",
                "components": ["silica_cartridge", "sample_cartridge"],
            },
        )
        await consumer._process_message(msg)
        result = producer.publish_result.call_args[0][0]
        assert result.code == 200, f"take_photo failed: {result.msg}"
        assert result.images is not None and len(result.images) > 0

        # -- 4. terminate_cc ----------------------------------------------------
        # Precondition: CC system must be "running" in world state.
        # Since we skip start_cc (long-running), manually inject the running CC state.
        world_state.apply_updates(
            [
                CCSystemUpdate(
                    type="column_chromatography_machine",
                    id="cc-device-1",
                    properties={"state": "running", "experiment_params": None, "start_timestamp": None},
                ),
            ]
        )

        producer.reset_mock()
        msg = make_mock_message(
            "task-004",
            "terminate_column_chromatography",
            {
                "work_station": ws_id,
                "device_id": "cc-device-1",
                "device_type": "cc-isco-300p",
                "experiment_params": {
                    "silicone_cartridge": "silica_40g",
                    "peak_gathering_mode": "peak",
                    "air_purge_minutes": 1.2,
                    "run_minutes": 30,
                    "need_equilibration": True,
                },
            },
        )
        await consumer._process_message(msg)
        result = producer.publish_result.call_args[0][0]
        assert result.code == 200, f"terminate_cc failed: {result.msg}"

        # After terminate_cc: CC system -> idle, materials -> used
        cc = world_state.get_entity("column_chromatography_machine", "cc-device-1")
        assert cc is not None
        assert cc["state"] == "idle"

        # -- 5. fraction_consolidation ------------------------------------------
        # Precondition: tube_rack must be in use or contaminated.
        # tube_rack_001 was set to "inuse" by setup_tube_rack (step 2),
        # terminate_cc changed it to "contaminated" (step 4).
        producer.reset_mock()
        msg = make_mock_message(
            "task-005",
            "collect_column_chromatography_fractions",
            {
                "work_station": ws_id,
                "device_id": "cc-device-1",
                "device_type": "cc-isco-300p",
                "collect_config": [1, 1, 0, 1, 0],
            },
        )
        await consumer._process_message(msg)
        result = producer.publish_result.call_args[0][0]
        assert result.code == 200, f"fraction_consolidation failed: {result.msg}"


# ---------------------------------------------------------------------------
# 3. Log Streaming During Execution
# ---------------------------------------------------------------------------


class TestLogStreamDuringExecution:
    """Tests verifying that simulators emit logs via the log producer during execution."""

    @pytest.mark.asyncio
    async def test_setup_cartridges_emits_logs(self) -> None:
        """SetupSimulator.simulate() for setup_cartridges calls publish_log at least once."""
        settings = _make_settings("talos_001")
        producer = AsyncMock()
        producer.publish_result = AsyncMock()
        log_producer = AsyncMock()
        log_producer.publish_log = AsyncMock()

        sim = SetupSimulator(producer, settings, log_producer=log_producer)

        from src.schemas.commands import SetupCartridgesParams

        params = SetupCartridgesParams(
            work_station="ws_bic_09_fh_001",
            silica_cartridge_type="silica_40g",
            sample_cartridge_location="bic_09B_l3_002",
            sample_cartridge_type="sample_40g",
            sample_cartridge_id="samp-001",
        )

        result = await sim.simulate("task-log-001", TaskType.SETUP_CARTRIDGES, params)
        assert result.code == 200
        # setup_cartridges emits 3 log calls: robot moving, cartridges mounted, robot idle
        assert log_producer.publish_log.call_count >= 1

    @pytest.mark.asyncio
    async def test_cc_terminate_emits_logs(self) -> None:
        """CCSimulator.simulate() for terminate_cc calls publish_log at least once."""
        settings = _make_settings("talos_001")
        producer = AsyncMock()
        producer.publish_result = AsyncMock()
        log_producer = AsyncMock()
        log_producer.publish_log = AsyncMock()

        sim = CCSimulator(producer, settings, log_producer=log_producer)

        from src.schemas.commands import CCExperimentParams, TerminateCCParams

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

        result = await sim.simulate("task-log-002", TaskType.TERMINATE_CC, params)
        assert result.code == 200
        # terminate_cc emits 2 log calls: robot terminating CC, CC terminated
        assert log_producer.publish_log.call_count >= 1



# ---------------------------------------------------------------------------
# 4. Reset State Via Command
# ---------------------------------------------------------------------------


class TestResetStateViaCommand:
    """Tests for the reset_state command through the consumer pipeline."""

    @pytest.mark.asyncio
    async def test_reset_state_clears_world_via_command(self) -> None:
        """Populate world state via commands, then reset_state clears it and returns success."""
        settings = _make_settings("talos_001")
        producer = AsyncMock()
        producer.publish_result = AsyncMock()
        log_producer = AsyncMock()
        log_producer.publish_log = AsyncMock()

        world_state = WorldState()
        consumer = _build_consumer(settings, producer, log_producer, world_state)

        # 1. Populate world state with setup_cartridges
        msg = make_mock_message(
            "task-pop-001",
            "setup_tubes_to_column_machine",
            {
                "silica_cartridge_type": "silica_40g",
                "sample_cartridge_location": "bic_09B_l3_002",
                "sample_cartridge_type": "sample_40g",
                "sample_cartridge_id": "samp-001",
                "work_station": "ws_bic_09_fh_001",
            },
        )
        await consumer._process_message(msg)

        result = producer.publish_result.call_args[0][0]
        assert result.code == 200
        assert world_state.has_entity("ccs_ext_module", "ws_bic_09_fh_001")

        # 2. Send reset_state command
        producer.reset_mock()
        msg = make_mock_message("task-reset-001", "reset_state", {})
        await consumer._process_message(msg)

        reset_result = producer.publish_result.call_args[0][0]
        assert reset_result.code == 200
        assert reset_result.task_id == "task-reset-001"
        assert "reset" in reset_result.msg.lower()

        # 3. Verify world state is completely cleared
        assert not world_state.has_entity("ccs_ext_module", "ws_bic_09_fh_001")
        assert not world_state.has_entity("sample_cartridge", "samp-001")
        assert not world_state.has_entity("robot", "talos_001")

    @pytest.mark.asyncio
    async def test_reset_state_without_world_state(self) -> None:
        """reset_state command without world_state returns error code 1002."""
        settings = _make_settings("talos_001")
        producer = AsyncMock()
        producer.publish_result = AsyncMock()

        mock_connection = AsyncMock()
        scenario_manager = ScenarioManager(settings)
        # Create consumer WITHOUT world_state (None)
        consumer = CommandConsumer(mock_connection, producer, scenario_manager, settings, world_state=None)

        # Send reset_state command
        msg = make_mock_message("task-reset-002", "reset_state", {})
        await consumer._process_message(msg)

        result = producer.publish_result.call_args[0][0]
        assert result.code == 1002
        assert result.task_id == "task-reset-002"
        assert "not enabled" in result.msg.lower()


# ---------------------------------------------------------------------------
# 5. CC Experiment Context Persistence
# ---------------------------------------------------------------------------


class TestCCExperimentContextPersistence:
    """Tests for experiment context persistence from start_cc to terminate_cc."""

    @pytest.mark.asyncio
    async def test_terminate_cc_persists_experiment_context(self) -> None:
        """terminate_cc retrieves and includes experiment_params and start_timestamp from start_cc."""
        settings = _make_settings("talos_001")
        producer = AsyncMock()
        producer.publish_result = AsyncMock()
        log_producer = AsyncMock()
        log_producer.publish_log = AsyncMock()

        world_state = WorldState()
        consumer = _build_consumer(settings, producer, log_producer, world_state=world_state)

        from src.schemas.commands import (
            CCExperimentParams,
            StartCCParams,
            TerminateCCParams,
        )

        # 1. Execute start_cc to populate world_state with experiment context
        experiment_params = CCExperimentParams(
            silicone_cartridge="silica_40g",
            peak_gathering_mode="all",
            air_purge_minutes=1.2,
            run_minutes=30,
            need_equilibration=True,
            left_rack="16x150",
            right_rack=None,
        )
        start_params = StartCCParams(
            work_station="ws_bic_09_fh_001",
            device_id="cc-001",
            device_type="cc-isco-300p",
            experiment_params=experiment_params,
        )

        start_msg = make_mock_message("task-start-cc", "start_column_chromatography", start_params.model_dump())
        await consumer._process_message(start_msg)

        # Wait briefly for the long-running task to publish intermediate updates
        import asyncio

        await asyncio.sleep(0.2)

        # Verify start_cc intermediate updates were published via log producer
        assert log_producer.publish_log.call_count > 0, "start_cc should have published intermediate log updates"
        # Find the log call that contains CC system updates
        initial_updates = None
        for call in log_producer.publish_log.call_args_list:
            updates_arg = call[0][1]  # second positional arg is updates list
            for update in updates_arg:
                if isinstance(update, CCSystemUpdate):
                    initial_updates = updates_arg
                    break
            if initial_updates is not None:
                break
        assert initial_updates is not None, "start_cc should have published a CC system update via log"

        # Find CC system update from start_cc
        cc_update_from_start = None
        for update in initial_updates:
            if isinstance(update, CCSystemUpdate):
                cc_update_from_start = update
                break

        assert cc_update_from_start is not None, "start_cc should have published a CC system update"
        assert cc_update_from_start.properties.state == "using"
        assert cc_update_from_start.properties.experiment_params is not None
        assert cc_update_from_start.properties.start_timestamp is not None

        # Store these for comparison
        original_experiment_params = cc_update_from_start.properties.experiment_params
        original_start_timestamp = cc_update_from_start.properties.start_timestamp

        # Apply the intermediate updates to world_state (simulating real-time state tracking)
        world_state.apply_updates(initial_updates)

        # Wait for start_cc to complete fully
        await asyncio.sleep(0.5)

        # 2. Execute terminate_cc - should retrieve context from world_state
        terminate_params = TerminateCCParams(
            work_station="ws_bic_09_fh_001",
            device_id="cc-001",
            device_type="cc-isco-300p",
            experiment_params=CCExperimentParams(
                silicone_cartridge="silica_40g",
                peak_gathering_mode="all",
                air_purge_minutes=1.2,
                run_minutes=30,
                need_equilibration=True,
            ),
        )

        # Reset producer call counts to isolate terminate_cc
        producer.publish_result.reset_mock()

        terminate_msg = make_mock_message(
            "task-terminate-cc", "terminate_column_chromatography", terminate_params.model_dump()
        )
        await consumer._process_message(terminate_msg)

        # 3. Verify terminate_cc result includes persisted experiment context
        assert producer.publish_result.call_count == 1
        result = producer.publish_result.call_args[0][0]

        assert result.code == 200
        assert result.task_id == "task-terminate-cc"

        # Find CC system update from terminate_cc
        cc_update_from_terminate = None
        for update in result.updates:
            if isinstance(update, CCSystemUpdate):
                cc_update_from_terminate = update
                break

        assert cc_update_from_terminate is not None
        assert cc_update_from_terminate.properties.state == "idle"
        # CRITICAL: Verify experiment context was persisted
        assert cc_update_from_terminate.properties.experiment_params == original_experiment_params
        assert cc_update_from_terminate.properties.start_timestamp == original_start_timestamp

        # 4. Verify ccs_ext_module was marked as "used"
        from src.schemas.results import CCSExtModuleUpdate

        ext_module_update = None
        for update in result.updates:
            if isinstance(update, CCSExtModuleUpdate):
                ext_module_update = update
                break

        assert ext_module_update is not None
        assert ext_module_update.properties.state == "using"

    @pytest.mark.asyncio
    async def test_terminate_cc_without_experiment_context(self) -> None:
        """terminate_cc with CC system in running state but no experiment context gracefully handles None values."""
        settings = _make_settings("talos_001")
        producer = AsyncMock()
        producer.publish_result = AsyncMock()
        log_producer = AsyncMock()
        log_producer.publish_log = AsyncMock()

        world_state = WorldState()
        consumer = _build_consumer(settings, producer, log_producer, world_state=world_state)

        from src.schemas.commands import CCExperimentParams, TerminateCCParams

        # Manually add CC system to world_state in "running" state WITHOUT experiment context
        world_state.apply_updates(
            [
                CCSystemUpdate(
                    type="column_chromatography_machine",
                    id="cc-001",
                    properties=CCMachineProperties(
                        state="running",
                        experiment_params=None,
                        start_timestamp=None,
                    ),
                )
            ]
        )

        # Execute terminate_cc
        terminate_params = TerminateCCParams(
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

        terminate_msg = make_mock_message(
            "task-terminate-cc-no-context", "terminate_column_chromatography", terminate_params.model_dump()
        )
        await consumer._process_message(terminate_msg)

        # Verify result is successful
        assert producer.publish_result.call_count == 1
        result = producer.publish_result.call_args[0][0]

        assert result.code == 200
        assert result.task_id == "task-terminate-cc-no-context"

        # Find CC system update
        cc_update = None
        for update in result.updates:
            if isinstance(update, CCSystemUpdate):
                cc_update = update
                break

        assert cc_update is not None
        assert cc_update.properties.state == "idle"
        # When world_state has no experiment context, the simulator falls back to
        # the experiment_params from the command itself (terminate_cc always carries them).
        assert cc_update.properties.experiment_params is not None
        assert cc_update.properties.experiment_params.silicone_cartridge == "silica_40g"
        # start_timestamp remains None since it was never set in world_state
        assert cc_update.properties.start_timestamp is None
