"""Command consumer — routes incoming RobotCommand messages to simulators."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from loguru import logger
from pydantic import BaseModel, ValidationError

from src.schemas.commands import (
    CollapseCartridgesParams,
    FractionConsolidationParams,
    ReturnCartridgesParams,
    ReturnCCSBinsParams,
    ReturnTubeRackParams,
    RobotCommand,
    SetupCartridgesParams,
    SetupCCSBinsParams,
    SetupTubeRackParams,
    StartCCParams,
    StartEvaporationParams,
    StopEvaporationParams,
    TakePhotoParams,
    TaskName,
    TerminateCCParams,
)
from src.schemas.results import RobotResult

if TYPE_CHECKING:
    from aio_pika.abc import AbstractQueue

    from src.config import MockSettings
    from src.mq.connection import MQConnection
    from src.mq.producer import ResultProducer
    from src.state.preconditions import PreconditionChecker
    from src.state.world_state import WorldState

# ---------------------------------------------------------------------------
# Protocols for dependencies that live in other (not-yet-implemented) packages
# ---------------------------------------------------------------------------


@runtime_checkable
class BaseSimulator(Protocol):
    """Protocol matching the simulator interface expected by the consumer."""

    async def simulate(self, task_id: str, task_name: TaskName, params: BaseModel) -> RobotResult: ...


@runtime_checkable
class ScenarioManager(Protocol):
    """Protocol matching the scenario manager interface expected by the consumer."""

    def should_timeout(self, task_name: TaskName) -> bool: ...
    def should_fail(self, task_name: TaskName) -> bool: ...
    def get_failure_result(self, task_id: str, task_name: TaskName) -> RobotResult: ...


# ---------------------------------------------------------------------------
# Parameter model mapping
# ---------------------------------------------------------------------------

PARAM_MODELS: dict[TaskName, type[BaseModel]] = {
    TaskName.SETUP_CARTRIDGES: SetupCartridgesParams,
    TaskName.SETUP_TUBE_RACK: SetupTubeRackParams,
    TaskName.COLLAPSE_CARTRIDGES: CollapseCartridgesParams,
    TaskName.TAKE_PHOTO: TakePhotoParams,
    TaskName.START_CC: StartCCParams,
    TaskName.TERMINATE_CC: TerminateCCParams,
    TaskName.FRACTION_CONSOLIDATION: FractionConsolidationParams,
    TaskName.START_EVAPORATION: StartEvaporationParams,
    TaskName.STOP_EVAPORATION: StopEvaporationParams,
    TaskName.SETUP_CCS_BINS: SetupCCSBinsParams,
    TaskName.RETURN_CCS_BINS: ReturnCCSBinsParams,
    TaskName.RETURN_CARTRIDGES: ReturnCartridgesParams,
    TaskName.RETURN_TUBE_RACK: ReturnTubeRackParams,
}

LONG_RUNNING_TASKS: set[TaskName] = {TaskName.START_CC, TaskName.START_EVAPORATION}


# ---------------------------------------------------------------------------
# Consumer
# ---------------------------------------------------------------------------


class CommandConsumer:
    """Consumes RobotCommand messages, routes them to the matching simulator."""

    def __init__(
        self,
        connection: MQConnection,
        producer: ResultProducer,
        scenario_manager: ScenarioManager,
        settings: MockSettings,
        world_state: WorldState | None = None,
    ) -> None:
        self._connection = connection
        self._producer = producer
        self._scenario_manager = scenario_manager
        self._settings = settings
        self._world_state = world_state
        self._simulators: dict[TaskName, BaseSimulator] = {}
        self._queue: AbstractQueue | None = None
        self._consumer_tag: str | None = None
        self._precondition_checker: PreconditionChecker | None = None

    # -- public API ----------------------------------------------------------

    @property
    def precondition_checker(self) -> PreconditionChecker | None:
        """Lazy-initialized precondition checker."""
        if self._world_state is not None and self._precondition_checker is None:
            from src.state.preconditions import PreconditionChecker

            self._precondition_checker = PreconditionChecker(self._world_state)
        return self._precondition_checker

    def register_simulator(self, task_name: TaskName, simulator: BaseSimulator) -> None:
        """Register a simulator for a given task type."""
        self._simulators[task_name] = simulator

    async def initialize(self) -> None:
        """Declare queue and exchange, bind them together."""
        channel = await self._connection.get_channel()

        queue_name = f"{self._settings.robot_id}.cmd"
        routing_key = f"{self._settings.robot_id}.cmd"

        # Declare the topic exchange (idempotent, shared with producer)
        exchange = await channel.declare_exchange(
            self._settings.mq_exchange,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        # Declare the per-robot command queue
        self._queue = await channel.declare_queue(
            queue_name,
            durable=True,
        )

        # Bind queue to exchange via routing key
        await self._queue.bind(exchange, routing_key=routing_key)

        logger.info(
            "Consumer initialized, queue '{}' bound to exchange '{}' via '{}'",
            queue_name,
            self._settings.mq_exchange,
            routing_key,
        )

    async def start_consuming(self) -> None:
        """Begin consuming messages from the queue."""
        if self._queue is None:
            raise RuntimeError("Consumer not initialized. Call initialize() first.")

        self._consumer_tag = await self._queue.consume(self._process_message)
        logger.info("Consuming commands from queue '{}.cmd'...", self._settings.robot_id)

    async def stop(self) -> None:
        """Cancel the active consumer."""
        if self._queue is not None and self._consumer_tag is not None:
            await self._queue.cancel(self._consumer_tag)
            self._consumer_tag = None
            logger.info("Consumer stopped")

    # -- internal ------------------------------------------------------------

    async def _process_message(self, message: AbstractIncomingMessage) -> None:  # noqa: C901
        """Core routing logic: parse command, apply scenarios, dispatch to simulator."""
        async with message.process(requeue=False):
            try:
                # Log raw message for debugging
                logger.debug("Raw message body (first 500 chars): {}", message.body[:500])
                raw = json.loads(message.body)
                logger.debug("Parsed JSON structure: {}", json.dumps(raw, indent=2)[:1000])

                # Handle special command: reset_state (before Pydantic validation)
                if raw.get("task_name") == "reset_state":
                    task_id = raw.get("task_id", "unknown")
                    if self._world_state is not None:
                        self._world_state.reset()
                        logger.info("World state reset via reset_state command")
                        await self._producer.publish_result(
                            RobotResult(code=200, msg="World state reset", task_id=task_id)
                        )
                    else:
                        await self._producer.publish_result(
                            RobotResult(code=1002, msg="World state tracking not enabled", task_id=task_id)
                        )
                    return

                command = RobotCommand.model_validate(raw)
            except json.JSONDecodeError:
                logger.error("Failed to decode message body as JSON: {}", message.body[:200])
                return
            except ValidationError as exc:
                logger.error("Invalid RobotCommand envelope: {}", exc)
                return

            task_id = command.task_id
            task_name = command.task_name

            logger.info("Received command: task_id={}, task_name={}, params={}", task_id, task_name, command.params)
            logger.debug(
                "Params dict keys: {}, Params values sample: {}",
                list(command.params.keys())[:10],
                {k: v for i, (k, v) in enumerate(command.params.items()) if i < 3},
            )

            try:
                # --- Scenario overrides ---
                if self._scenario_manager.should_timeout(task_name):
                    logger.warning("Simulating timeout for task {}", task_id)
                    return

                if self._scenario_manager.should_fail(task_name):
                    failure_result = self._scenario_manager.get_failure_result(task_id, task_name)
                    logger.warning("Simulating failure for task {}", task_id)
                    await self._producer.publish_result(failure_result)
                    return

                # --- Simulator lookup ---
                simulator = self._simulators.get(task_name)
                if simulator is None:
                    error_result = RobotResult(
                        code=1000,
                        msg=f"Unknown task type: {task_name}",
                        task_id=task_id,
                    )
                    await self._producer.publish_result(error_result)
                    return

                # --- Parse task-specific params ---
                params_model = self._parse_params(task_name, command.params)

                # --- Precondition check ---
                if self.precondition_checker is not None:
                    precondition_result = self.precondition_checker.check(task_name, params_model)
                    if not precondition_result.ok:
                        logger.warning(
                            "Precondition check failed for task {}: {}",
                            task_id,
                            precondition_result.error_msg,
                        )
                        error_result = RobotResult(
                            code=precondition_result.error_code,
                            msg=precondition_result.error_msg,
                            task_id=task_id,
                        )
                        await self._producer.publish_result(error_result)
                        return

                # --- Dispatch ---
                if task_name in LONG_RUNNING_TASKS:
                    asyncio.create_task(self._run_long_task(task_id, task_name, simulator, params_model))
                else:
                    result = await simulator.simulate(task_id, task_name, params_model)
                    await self._producer.publish_result(result)
                    # Apply state updates after successful execution
                    if self._world_state is not None and result.is_success():
                        self._world_state.apply_updates(result.updates)

            except ValidationError as exc:
                logger.error("Parameter validation failed for task {}: {}", task_id, exc)
                logger.error("Raw params that failed validation: {}", json.dumps(command.params, indent=2)[:500])
                await self._producer.publish_result(
                    RobotResult(code=1001, msg=f"Parameter validation error: {exc}", task_id=task_id)
                )
            except Exception:
                logger.exception("Unexpected error processing task {}", task_id)
                await self._producer.publish_result(
                    RobotResult(code=9999, msg="Internal mock server error", task_id=task_id)
                )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _parse_params(task_name: TaskName, raw_params: dict[str, Any]) -> BaseModel:
        """Validate raw params dict against the correct Pydantic model."""
        model_cls = PARAM_MODELS.get(task_name)
        if model_cls is None:
            raise ValueError(f"No parameter model registered for {task_name}")
        return model_cls.model_validate(raw_params)

    async def _run_long_task(
        self,
        task_id: str,
        task_name: TaskName,
        simulator: BaseSimulator,
        params: BaseModel,
    ) -> None:
        """Execute a long-running simulation and publish its result."""
        try:
            result = await simulator.simulate(task_id, task_name, params)
            await self._producer.publish_result(result)
            # Apply state updates after successful execution
            if self._world_state is not None and result.is_success():
                self._world_state.apply_updates(result.updates)
        except Exception:
            logger.exception("Long-running task {} ({}) failed", task_id, task_name)
            await self._producer.publish_result(
                RobotResult(code=9999, msg="Internal mock server error (long-running)", task_id=task_id)
            )
