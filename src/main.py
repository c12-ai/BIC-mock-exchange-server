"""Mock Robot Server lifecycle — wires all components and runs until shutdown."""

from __future__ import annotations

import asyncio
import signal
import sys

from loguru import logger

from src.config import MockSettings
from src.mq.connection import MQConnection
from src.mq.consumer import CommandConsumer
from src.mq.heartbeat import HeartbeatPublisher
from src.mq.log_producer import LogProducer
from src.mq.producer import ResultProducer
from src.scenarios.manager import ScenarioManager
from src.schemas.commands import TaskType
from src.simulators.cc_simulator import CCSimulator
from src.simulators.consolidation_simulator import ConsolidationSimulator
from src.simulators.evaporation_simulator import EvaporationSimulator
from src.simulators.photo_simulator import PhotoSimulator
from src.simulators.setup_simulator import SetupSimulator
from src.state.world_state import WorldState


async def run_server() -> None:
    """Start the mock robot server, wire all components, and wait for shutdown."""
    settings = MockSettings()

    # Configure loguru
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)

    logger.info("=== Mock Robot Server starting ===")
    logger.info(
        "server_name={} robot_id={} delay_multiplier={} scenario={} failure_rate={} timeout_rate={}",
        settings.server_name,
        settings.robot_id,
        settings.base_delay_multiplier,
        settings.default_scenario,
        settings.failure_rate,
        settings.timeout_rate,
    )

    # --- Infrastructure ---
    mq = MQConnection(settings)
    try:
        await mq.connect()
    except Exception:
        logger.exception("Failed to connect to RabbitMQ")
        raise

    producer = ResultProducer(mq, settings)
    try:
        await producer.initialize()
    except Exception:
        logger.exception("Failed to initialize result producer")
        await mq.disconnect()
        raise

    log_producer = LogProducer(mq, settings)
    try:
        await log_producer.initialize()
    except Exception:
        logger.exception("Failed to initialize log producer")
        await mq.disconnect()
        raise

    # --- Domain components ---
    world_state = WorldState()

    heartbeat = HeartbeatPublisher(mq, settings, world_state=world_state)
    try:
        await heartbeat.initialize()
        await heartbeat.start()
    except Exception:
        logger.exception("Failed to initialize heartbeat publisher")
        await mq.disconnect()
        raise

    scenario_manager = ScenarioManager(settings)

    setup_sim = SetupSimulator(producer, settings, log_producer=log_producer, world_state=world_state)
    photo_sim = PhotoSimulator(producer, settings, log_producer=log_producer, world_state=world_state)
    cc_sim = CCSimulator(producer, settings, log_producer=log_producer, world_state=world_state)
    consolidation_sim = ConsolidationSimulator(producer, settings, log_producer=log_producer, world_state=world_state)
    evaporation_sim = EvaporationSimulator(producer, settings, log_producer=log_producer, world_state=world_state)

    # --- Consumer ---
    consumer = CommandConsumer(
        mq, producer, scenario_manager, settings, world_state=world_state, log_producer=log_producer
    )

    consumer.register_simulator(TaskType.SETUP_CARTRIDGES, setup_sim)
    consumer.register_simulator(TaskType.SETUP_TUBE_RACK, setup_sim)
    consumer.register_simulator(TaskType.TAKE_PHOTO, photo_sim)
    consumer.register_simulator(TaskType.START_CC, cc_sim)
    consumer.register_simulator(TaskType.TERMINATE_CC, cc_sim)
    consumer.register_simulator(TaskType.COLLECT_CC_FRACTIONS, consolidation_sim)
    consumer.register_simulator(TaskType.START_EVAPORATION, evaporation_sim)

    try:
        await consumer.initialize()
    except Exception:
        logger.exception("Failed to initialize consumer")
        await mq.disconnect()
        raise

    await consumer.start_consuming()
    logger.info("Mock Robot Server ready - waiting for commands...")

    # --- Wait for shutdown signal ---
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    try:
        await shutdown_event.wait()
    finally:
        logger.info("Shutting down...")
        await heartbeat.stop()
        await consumer.stop()
        await mq.disconnect()
        logger.info("Mock Robot Server shutdown complete")


asyncio.run(run_server())
