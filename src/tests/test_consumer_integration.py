"""Integration tests for CommandConsumer with full pipeline (without real RabbitMQ).

Tests the full dispatch flow by mocking MQ layer and using real simulators,
world state, and scenario manager.
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
from src.simulators.cc_simulator import CCSimulator
from src.simulators.consolidation_simulator import ConsolidationSimulator
from src.simulators.evaporation_simulator import EvaporationSimulator
from src.simulators.photo_simulator import PhotoSimulator
from src.simulators.setup_simulator import SetupSimulator
from src.state.world_state import WorldState

if TYPE_CHECKING:
    from aio_pika.abc import AbstractIncomingMessage


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
    # Make async context manager work
    mock_msg.process = MagicMock(return_value=AsyncContextManagerMock())
    return mock_msg


@pytest.fixture
def mock_producer():
    """Mock ResultProducer that captures published results."""
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
def mock_connection():
    """Mock MQConnection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def consumer_with_simulators(mock_connection, mock_producer, mock_log_producer, mock_settings):
    """Fully wired consumer with real simulators and world state."""
    world_state = WorldState()
    scenario_manager = ScenarioManager(mock_settings)
    consumer = CommandConsumer(mock_connection, mock_producer, scenario_manager, mock_settings, world_state=world_state)

    # Create real simulators with mock producer
    setup_sim = SetupSimulator(mock_producer, mock_settings, log_producer=mock_log_producer, world_state=world_state)
    photo_sim = PhotoSimulator(mock_producer, mock_settings, log_producer=mock_log_producer, world_state=world_state)
    cc_sim = CCSimulator(mock_producer, mock_settings, log_producer=mock_log_producer, world_state=world_state)
    consolidation_sim = ConsolidationSimulator(
        mock_producer, mock_settings, log_producer=mock_log_producer, world_state=world_state
    )
    evaporation_sim = EvaporationSimulator(
        mock_producer, mock_settings, log_producer=mock_log_producer, world_state=world_state
    )

    # Register all simulators (v0.3 ground truth — 7 tasks)
    consumer.register_simulator(TaskType.SETUP_CARTRIDGES, setup_sim)
    consumer.register_simulator(TaskType.SETUP_TUBE_RACK, setup_sim)
    consumer.register_simulator(TaskType.TAKE_PHOTO, photo_sim)
    consumer.register_simulator(TaskType.START_CC, cc_sim)
    consumer.register_simulator(TaskType.TERMINATE_CC, cc_sim)
    consumer.register_simulator(TaskType.COLLECT_CC_FRACTIONS, consolidation_sim)
    consumer.register_simulator(TaskType.START_EVAPORATION, evaporation_sim)

    return consumer, mock_producer, world_state


class TestConsumerIntegration:
    """Integration tests for CommandConsumer with full pipeline."""

    @pytest.mark.asyncio
    async def test_full_dispatch_flow(self, consumer_with_simulators):
        """Test full command dispatch: receive message → simulator → publish result."""
        consumer, mock_producer, world_state = consumer_with_simulators

        # Create a setup_tube_rack command
        params = {
            "work_station": "ws_bic_09_fh_001",
        }
        msg = make_mock_message("task-001", "setup_tube_rack", params)

        # Process the message
        await consumer._process_message(msg)

        # Verify result was published
        mock_producer.publish_result.assert_called_once()
        result = mock_producer.publish_result.call_args[0][0]
        assert result.code == 200
        assert result.task_id == "task-001"
        assert result.msg == "success"
        assert len(result.updates) > 0

    @pytest.mark.asyncio
    async def test_world_state_tracking_across_commands(self, consumer_with_simulators):
        """Test world state tracking across multiple commands."""
        consumer, mock_producer, world_state = consumer_with_simulators

        # 1. Send setup_cartridges → verify world state updated
        params1 = {
            "silica_cartridge_type": "silica_40g",
            "sample_cartridge_location": "bic_09B_l3_002",
            "sample_cartridge_type": "sample_40g",
            "sample_cartridge_id": "samp-001",
            "work_station": "ws_bic_09_fh_001",
        }
        msg1 = make_mock_message("task-001", "setup_tubes_to_column_machine", params1)
        await consumer._process_message(msg1)

        # Verify world state has ext_module
        ext_module = world_state.get_entity("ccs_ext_module", "ws_bic_09_fh_001")
        assert ext_module is not None
        assert ext_module["state"] == "using"

        # 2. Send setup_tube_rack → verify tube_rack tracked
        params2 = {
            "work_station": "ws_bic_09_fh_001",
        }
        msg2 = make_mock_message("task-002", "setup_tube_rack", params2)
        await consumer._process_message(msg2)

        # Verify world state has tube_rack (keyed by "tube_rack_001")
        tube_rack = world_state.get_entity("tube_rack", "tube_rack_001")
        assert tube_rack is not None
        assert tube_rack["state"] == "inuse"

        # 3. Verify world state tracks multiple entities
        assert world_state.has_entity("ccs_ext_module", "ws_bic_09_fh_001")
        assert world_state.has_entity("sample_cartridge", "samp-001")
        assert world_state.has_entity("tube_rack", "tube_rack_001")
        assert world_state.has_entity("robot", "test-robot-001")

    @pytest.mark.asyncio
    async def test_precondition_check_integration(self, consumer_with_simulators):
        """Test precondition checks prevent invalid operations."""
        consumer, mock_producer, world_state = consumer_with_simulators

        # 1. Send terminate_cc without prior start_cc → expect precondition failure (2030-2031)
        params = {
            "work_station": "ws_bic_09_fh_001",
            "device_id": "cc-device-1",
            "device_type": "cc-isco-300p",
            "experiment_params": {
                "silicone_cartridge": "silica_40g",
                "peak_gathering_mode": "peak",
                "air_purge_minutes": 1.2,
                "run_minutes": 30,
                "need_equilibration": True,
            },
        }
        msg = make_mock_message("task-001", "terminate_column_chromatography", params)
        await consumer._process_message(msg)

        # Verify precondition failure
        result = mock_producer.publish_result.call_args[0][0]
        assert result.task_id == "task-001"
        assert result.code == 2030  # CC system not found
        assert "not found" in result.msg.lower()

        mock_producer.reset_mock()

        # 2. Send setup_cartridges twice → expect precondition failure (2001)
        params1 = {
            "silica_cartridge_type": "silica_40g",
            "sample_cartridge_location": "bic_09B_l3_002",
            "sample_cartridge_type": "sample_40g",
            "sample_cartridge_id": "samp-002",
            "work_station": "ws-2",
        }
        msg1 = make_mock_message("task-002", "setup_tubes_to_column_machine", params1)
        await consumer._process_message(msg1)

        # First should succeed
        result1 = mock_producer.publish_result.call_args[0][0]
        assert result1.code == 200

        mock_producer.reset_mock()

        # Second should fail with precondition error
        msg2 = make_mock_message("task-003", "setup_tubes_to_column_machine", params1)
        await consumer._process_message(msg2)

        result2 = mock_producer.publish_result.call_args[0][0]
        assert result2.task_id == "task-003"
        assert result2.code == 2001  # External module already has cartridges
        assert "already has cartridges" in result2.msg.lower()

    @pytest.mark.asyncio
    async def test_scenario_injection_failure(self, mock_connection, mock_producer, mock_log_producer):
        """Test scenario manager failure injection."""
        # Create settings with 100% failure rate
        settings = MockSettings(
            mq_host="localhost",
            mq_port=5672,
            mq_exchange="test_exchange",
            base_delay_multiplier=0.01,
            min_delay_seconds=0.0,
            default_scenario="success",
            failure_rate=1.0,  # Force failures
            timeout_rate=0.0,
            image_base_url="http://test:9000/mock-images",
            robot_id="test-robot-001",
            log_level="DEBUG",
            heartbeat_interval=1.0,
        )

        world_state = WorldState()
        scenario_manager = ScenarioManager(settings)
        consumer = CommandConsumer(mock_connection, mock_producer, scenario_manager, settings, world_state=world_state)

        # Register a simulator
        setup_sim = SetupSimulator(mock_producer, settings, log_producer=mock_log_producer)
        consumer.register_simulator(TaskType.SETUP_TUBE_RACK, setup_sim)

        # Send command
        params = {
            "work_station": "ws_bic_09_fh_001",
        }
        msg = make_mock_message("task-001", "setup_tube_rack", params)
        await consumer._process_message(msg)

        # Verify failure result published
        mock_producer.publish_result.assert_called_once()
        result = mock_producer.publish_result.call_args[0][0]
        assert result.task_id == "task-001"
        assert result.code != 200  # Should be a failure code (1020-1029 for setup_tube_rack)
        assert 1020 <= result.code <= 1029

    @pytest.mark.asyncio
    async def test_scenario_injection_timeout(self, mock_connection, mock_producer, mock_log_producer):
        """Test scenario manager timeout injection (no result published)."""
        # Create settings with 100% timeout rate
        settings = MockSettings(
            mq_host="localhost",
            mq_port=5672,
            mq_exchange="test_exchange",
            base_delay_multiplier=0.01,
            min_delay_seconds=0.0,
            default_scenario="success",
            failure_rate=0.0,
            timeout_rate=1.0,  # Force timeouts
            image_base_url="http://test:9000/mock-images",
            robot_id="test-robot-001",
            log_level="DEBUG",
            heartbeat_interval=1.0,
        )

        world_state = WorldState()
        scenario_manager = ScenarioManager(settings)
        consumer = CommandConsumer(mock_connection, mock_producer, scenario_manager, settings, world_state=world_state)

        # Register a simulator
        setup_sim = SetupSimulator(mock_producer, settings, log_producer=mock_log_producer)
        consumer.register_simulator(TaskType.SETUP_TUBE_RACK, setup_sim)

        # Send command
        params = {
            "work_station": "ws_bic_09_fh_001",
        }
        msg = make_mock_message("task-001", "setup_tube_rack", params)
        await consumer._process_message(msg)

        # Verify NO result was published (timeout simulation)
        mock_producer.publish_result.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_state_command(self, consumer_with_simulators):
        """Test world state can be cleared via reset() method."""
        consumer, mock_producer, world_state = consumer_with_simulators

        # 1. Populate world state via commands
        params1 = {
            "silica_cartridge_type": "silica_40g",
            "sample_cartridge_location": "bic_09B_l3_002",
            "sample_cartridge_type": "sample_40g",
            "sample_cartridge_id": "samp-001",
            "work_station": "ws_bic_09_fh_001",
        }
        msg1 = make_mock_message("task-001", "setup_tubes_to_column_machine", params1)
        await consumer._process_message(msg1)

        # Verify world state has entities
        ext_module = world_state.get_entity("ccs_ext_module", "ws_bic_09_fh_001")
        assert ext_module is not None

        # 2. Reset world state directly (simulating the reset_state command path)
        world_state.reset()

        # 3. Verify world state is cleared
        ext_module = world_state.get_entity("ccs_ext_module", "ws_bic_09_fh_001")
        assert ext_module is None

    @pytest.mark.asyncio
    async def test_unknown_task_handling(self, consumer_with_simulators):
        """Test unregistered task returns error result (code 1000)."""
        consumer, mock_producer, world_state = consumer_with_simulators

        # Unregister the take_photo simulator to simulate unknown task
        if TaskType.TAKE_PHOTO in consumer._simulators:
            del consumer._simulators[TaskType.TAKE_PHOTO]

        # Send take_photo command (unregistered)
        params = {
            "work_station": "ws-1",
            "device_id": "cam-001",
            "device_type": "camera",
            "components": ["component1"],
        }
        msg = make_mock_message("task-001", "take_photo", params)
        await consumer._process_message(msg)

        # Verify error result
        mock_producer.publish_result.assert_called_once()
        result = mock_producer.publish_result.call_args[0][0]
        assert result.task_id == "task-001"
        assert result.code == 1000
        assert "unknown task type" in result.msg.lower()

    @pytest.mark.asyncio
    async def test_parameter_validation_failure(self, consumer_with_simulators):
        """Test invalid parameters return validation error (code 1001)."""
        consumer, mock_producer, world_state = consumer_with_simulators

        # Send command with missing required parameter (sample_cartridge_id is required)
        params = {
            "work_station": "ws_bic_09_fh_001",
            # Missing: sample_cartridge_id (required)
        }
        msg = make_mock_message("task-001", "setup_tubes_to_column_machine", params)
        await consumer._process_message(msg)

        # Verify validation error
        mock_producer.publish_result.assert_called_once()
        result = mock_producer.publish_result.call_args[0][0]
        assert result.task_id == "task-001"
        assert result.code == 1001
        assert "validation error" in result.msg.lower()
