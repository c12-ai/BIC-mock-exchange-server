# Mock Robot Server

A standalone microservice that simulates the Robot Exchange MQ Server for local development and testing of the BIC Lab Service. Consumes robot command messages from RabbitMQ, simulates task execution with configurable timing and failure modes, and publishes realistic result messages with entity state updates.

## Architecture

```
┌──────────────────┐         RabbitMQ           ┌──────────────────────┐
│  BIC Lab Service │   robot.exchange (TOPIC)   │  Mock Robot Server   │
│                  │                            │                      │
│  MQ Producer ────┼── {robot_id}.cmd ────────▶ │  Command Consumer    │
│                  │                            │        │             │
│                  │   {robot_id}.result        │   Task Simulator     │
│  Result Consumer◀┼── {robot_id}.log     ◀──── │        │             │
│  Log Consumer   ◀┼── {robot_id}.hb      ◀──── │  Result Publisher    │
│  HB Consumer    ◀┼───────────────────────     │  Log Producer        │
│                  │                            │  Heartbeat Publisher  │
└──────────────────┘                            └──────────────────────┘
```

All messages flow through a single **TOPIC exchange** (`robot.exchange`) with per-robot routing keys:
- `{robot_id}.cmd` — Commands from BIC Lab Service → Robot
- `{robot_id}.result` — Final task results from Robot → BIC Lab Service
- `{robot_id}.log` — Real-time intermediate state updates during execution
- `{robot_id}.hb` — Periodic heartbeat messages (every 2s)

**Dependencies:** RabbitMQ only. No PostgreSQL, Redis, or S3 required.

## Quick Start

### Docker (recommended)

```bash
# Build and run
docker build -t mock-robot-server .
docker run --rm \
  -e MOCK_MQ_HOST=rabbitmq \
  --network bic-lab-service_app-network \
  mock-robot-server
```

### Docker Compose (with BIC Lab Service)

Add to the BIC Lab Service project-level `docker-compose.override.yml`:

```yaml
services:
  mock-robot:
    build:
      context: ../mock-robot-server
      dockerfile: Dockerfile
    environment:
      MOCK_MQ_HOST: rabbitmq
      MOCK_BASE_DELAY_MULTIPLIER: "0.01"   # 100x speed for fast iteration
      MOCK_FAILURE_RATE: "0.1"             # 10% random failures
    depends_on:
      rabbitmq:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped
```

Then run everything together:

```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

### Local Development

```bash
# Install dependencies
uv sync

# Run directly
uv run python -m src.main
```

## Configuration Reference

All settings are loaded from environment variables with `MOCK_` prefix via pydantic-settings.

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_MQ_HOST` | `localhost` | RabbitMQ host |
| `MOCK_MQ_PORT` | `5672` | RabbitMQ port |
| `MOCK_MQ_USER` | `guest` | RabbitMQ username |
| `MOCK_MQ_PASSWORD` | `guest` | RabbitMQ password |
| `MOCK_MQ_VHOST` | `/` | RabbitMQ virtual host |
| `MOCK_MQ_EXCHANGE` | `robot.exchange` | Shared TOPIC exchange for all message routing |
| `MOCK_MQ_CONNECTION_TIMEOUT` | `30` | RabbitMQ connection timeout (seconds) |
| `MOCK_MQ_HEARTBEAT` | `60` | AMQP heartbeat interval (seconds) |
| `MOCK_MQ_PREFETCH_COUNT` | `5` | Consumer prefetch count |
| `MOCK_ROBOT_ID` | `00000000-0000-4000-a000-000000000001` | Simulated robot identifier (UUID) |
| `MOCK_DEFAULT_SCENARIO` | `success` | Default scenario: `success`, `failure`, or `timeout` |
| `MOCK_FAILURE_RATE` | `0.0` | Probability of injecting a failure (0.0 - 1.0) |
| `MOCK_TIMEOUT_RATE` | `0.0` | Probability of injecting a timeout / no response (0.0 - 1.0) |
| `MOCK_BASE_DELAY_MULTIPLIER` | `0.1` | Speed multiplier for task durations (0.01 = 100x fast, 1.0 = realistic) |
| `MOCK_MIN_DELAY_SECONDS` | `0.5` | Minimum delay floor (seconds) |
| `MOCK_IMAGE_BASE_URL` | `http://minio:9000/bic-robot/captures` | Base URL returned in mock captured image URLs |
| `MOCK_SERVER_NAME` | `mock-robot-server` | Server instance name for logging |
| `MOCK_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MOCK_HEARTBEAT_INTERVAL` | `2.0` | Seconds between heartbeat messages |
| `MOCK_CC_INTERMEDIATE_INTERVAL` | `300.0` | CC progress update interval at 1.0x (seconds) |
| `MOCK_RE_INTERMEDIATE_INTERVAL` | `300.0` | RE progress update interval at 1.0x (seconds) |

## Supported Task Types (All 13 Tasks)

| Task Name | Realistic Duration | At 0.1x Multiplier | Notes |
|-----------|-------------------|-------------------|-------|
| `setup_tubes_to_column_machine` | 15 - 30 s | 1.5 - 3 s | Retrieves and mounts silica + sample cartridges |
| `setup_tube_rack` | 10 - 20 s | 1 - 2 s | Retrieves and mounts tube rack at work station |
| `take_photo` | 2 - 5 s per component | 0.2 - 0.5 s | Navigates to station, captures device screen |
| `start_column_chromatography` | 30 - 60 min | 3 - 6 min | Long-running; intermediate updates via `.log` channel |
| `terminate_column_chromatography` | 5 - 10 s | 0.5 - 1 s | Stops CC operation, captures result images |
| `fraction_consolidation` | ~1 min (tube count) | ~6 s | Collects fractions from tubes into flask |
| `start_evaporation` | 30 - 90 min | 3 - 9 min | Long-running; sensor ramp via `.log` channel |
| `stop_evaporation` | 5 - 10 s | 0.5 - 1 s | Stops evaporator and returns flask |
| `collapse_cartridges` | 10 - 15 s | 1 - 1.5 s | Cleans up cartridges after process completion |
| `setup_ccs_bins` | 10 - 15 s | 1 - 1.5 s | Sets up waste bins at CC workstation |
| `return_ccs_bins` | 10 - 15 s | 1 - 1.5 s | Returns used bins to waste area |
| `return_cartridges` | 10 - 15 s | 1 - 1.5 s | Removes and returns used cartridges |
| `return_tube_rack` | 10 - 15 s | 1 - 1.5 s | Removes and returns used tube rack |

## World State Tracking & Preconditions

The mock server maintains an in-memory `WorldState` that tracks all entities (robots, devices, materials) and validates preconditions before executing tasks. This enables realistic error simulation based on current system state.

**Error Code Ranges:**
- `1000-1009`: General errors (unknown task, validation failure)
- `1010-1139`: Task-specific failures (per-task 10-code ranges)
- `2000-2099`: Precondition violations (state-driven errors)

**Special Commands:**
- `reset_state`: Clears WorldState back to initial conditions (useful for testing)

**Precondition Examples:**
- `setup_cartridges` fails if ext_module already has cartridges (code 2001)
- `terminate_cc` fails if CC system not running (code 2030-2031)
- `collapse_cartridges` fails if cartridges not in 'used' state (code 2010-2013)

## Scenarios

The mock server supports three execution scenarios, controlled globally by `MOCK_DEFAULT_SCENARIO` or injected randomly via `MOCK_FAILURE_RATE` / `MOCK_TIMEOUT_RATE`.

### Success

The default mode. The server simulates the full task lifecycle:
1. Acknowledges command receipt
2. Publishes intermediate entity state updates via `{robot_id}.log` during execution
3. Waits for the simulated duration
4. Publishes a final `RobotResult` via `{robot_id}.result` with `code: 200`, updated entity states, and any captured images

### Failure

Simulates a robot error mid-task:
1. Begins execution normally with intermediate updates
2. Aborts partway through
3. Publishes a `RobotResult` with task-specific error code (1010-1139), an error message, and partially updated entity states

### Timeout

Simulates a non-responsive robot:
1. Acknowledges the command
2. Never publishes a result message
3. Useful for testing the main service's timeout detection and recovery logic

**Injection priority:** Per-message random injection (`MOCK_FAILURE_RATE`, `MOCK_TIMEOUT_RATE`) takes precedence over `MOCK_DEFAULT_SCENARIO`. If both rates are `0.0`, the default scenario is used.

## Message Flow

```
1. BIC Lab Service publishes a RobotCommand to `robot.exchange` (TOPIC)
   with routing key `{robot_id}.cmd` (e.g., `talos_001.cmd`)

2. Mock Robot Server consumes from its `{robot_id}.cmd` queue:
   - Deserializes the command using Pydantic models
   - Validates preconditions against WorldState
   - Selects scenario (success / failure / timeout)
   - Logs the received command

3. During simulated execution:
   - Publishes intermediate entity updates to `{robot_id}.log`
     (e.g., cartridge state: available -> mounted)
   - Publishes heartbeats to `{robot_id}.hb` every 2 seconds
   - Sleeps for the computed duration (base delay × multiplier)

4. On completion:
   - Builds a RobotResult with:
     - task_id matching the command
     - code: 200 (success) or 1010-2099 (failure)
     - entity_updates: list of state changes
     - captured_images: mock image URLs (for take_photo, terminate_cc)
   - Publishes the result to `{robot_id}.result` routing key
   - Updates WorldState with final entity states
```

## Development

### Tech Stack

- **Python 3.12+**, async-first
- **aio-pika** — async RabbitMQ client
- **pydantic + pydantic-settings** — configuration and message schemas
- **loguru** — structured logging
- **uv** — package manager
- **ruff** — lint/format
- **pytest** — testing

### Project Structure

```
mock-robot-server/
├── src/
│   ├── __main__.py                    # Entry point: python -m src.main
│   ├── main.py                        # Server lifecycle (startup/shutdown)
│   ├── config.py                      # pydantic-settings with MOCK_ prefix
│   ├── schemas/
│   │   ├── protocol.py                # Shared protocol types (enums, params, result types)
│   │   ├── commands.py                # RobotCommand wrapper + re-exports
│   │   └── results.py                 # RobotResult + entity update models
│   ├── simulators/
│   │   ├── base.py                    # BaseSimulator ABC + WorldState helpers
│   │   ├── setup_simulator.py         # setup_cartridges, setup_tube_rack, collapse
│   │   ├── cc_simulator.py            # start_cc (long), terminate_cc (quick)
│   │   ├── photo_simulator.py         # take_photo
│   │   ├── consolidation_simulator.py # fraction_consolidation
│   │   ├── evaporation_simulator.py   # start_evaporation (long)
│   │   └── cleanup_simulator.py       # stop_evaporation, setup/return bins, return cartridges/rack
│   ├── generators/
│   │   ├── entity_updates.py          # Factory functions for 10 entity update types
│   │   ├── images.py                  # Mock image URL generation
│   │   └── timing.py                  # Delay calculation with multiplier
│   ├── scenarios/
│   │   ├── manager.py                 # ScenarioManager (success/failure/timeout)
│   │   └── failures.py                # Task-specific failure messages
│   ├── state/
│   │   ├── world_state.py             # In-memory entity state tracking
│   │   └── preconditions.py           # Pre-execution validation per task
│   ├── mq/
│   │   ├── connection.py              # RabbitMQ robust connection (singleton)
│   │   ├── consumer.py                # Command consumer + task routing
│   │   ├── producer.py                # Result publisher (final results)
│   │   ├── log_producer.py            # Log publisher (intermediate updates)
│   │   └── heartbeat.py               # Periodic heartbeat publisher
│   └── tests/
│       ├── conftest.py                # Shared test fixtures
│       ├── test_generators.py         # Entity update, image, timing tests
│       ├── test_scenarios.py          # ScenarioManager + failure message tests
│       ├── test_schemas.py            # Command/result parsing + serialization tests
│       ├── test_consumer_integration.py # Consumer dispatch flow tests
│       ├── test_simulator_integration.py # End-to-end task execution tests
│       ├── test_cleanup_simulator.py  # Cleanup task tests (5 tasks)
│       ├── test_heartbeat.py          # Heartbeat publisher lifecycle tests
│       ├── test_log_producer.py       # Log producer tests
│       ├── test_photo_device_state.py # Photo device state update tests
│       ├── test_photo_integration.py  # Photo integration tests
│       ├── test_preconditions.py      # Precondition checker tests
│       ├── test_world_state.py        # WorldState tracking tests
│       └── test_full_workflow.py      # Full CC experiment workflow tests
├── docs/
│   ├── note.md                        # Protocol spec (ground truth)
│   └── ROBOT_ID_DESIGN.md            # Robot ID design decisions
├── Dockerfile
├── docker-compose.mock.yml
├── pyproject.toml
├── .env
└── CLAUDE.md
```

### Protocol Schema Management

The protocol types (enums, command parameters, result types) are defined in `src/schemas/protocol.py`. This is a self-contained copy of the types from the BIC Lab Service's `app/data/schemas/messages.py` and related enum modules.

**When the production protocol changes**, update `protocol.py` to match the new contract. The types that need to stay in sync:
- `TaskName`, `RobotState`, `EquipmentState`, `BinState` (enums)
- All `*Params` models (command parameters)
- `CapturedImage` (result metadata)

### Extending

**Add a new task type:**
1. Add the task name to `TaskName` enum in `schemas/protocol.py`
2. Define parameter model in `schemas/protocol.py`
3. Re-export from `schemas/commands.py`
4. Create a new simulator in `simulators/` (extend `BaseSimulator`)
5. Add entity update factory functions in `generators/entity_updates.py`
6. Add failure messages in `scenarios/failures.py`
7. Register the simulator in `main.py` and add param model mapping in `mq/consumer.py`

**Adjust timing:**
Modify base duration ranges in `generators/timing.py`. Each task has a `(min, max)` range; the `MOCK_BASE_DELAY_MULTIPLIER` scales all durations uniformly.

**Add new entity update types:**
1. Add the update model in `schemas/results.py` following the discriminated union pattern
2. Add it to the `EntityUpdate` union type
3. Add a factory function in `generators/entity_updates.py`

### Running Tests

```bash
uv run pytest src/tests/ -v
```

134 tests cover generators, scenarios, schemas, consumer integration, simulator integration, cleanup tasks, heartbeat, log producer, photo handling, preconditions, world state tracking, and full CC workflow.

## Case Study: Column Chromatography Workflow

This case study demonstrates a complete column chromatography workflow using the mock server, exercising all major task types and both quick and long-running simulation patterns.

### Scenario

An AI agent orchestrates a column chromatography experiment. The workflow consists of 8 sequential steps:

```
setup_cartridges -> setup_tube_rack -> take_photo -> start_cc
    -> terminate_cc -> fraction_consolidation -> start_evaporation
    -> collapse_cartridges
```

### Step 1: Setup Cartridges

The agent publishes a command to mount silica and sample cartridges at the work station:

```json
{
  "task_id": "task-001",
  "task_name": "setup_tubes_to_column_machine",
  "params": {
    "silica_cartridge_location_id": "shelf-A3",
    "silica_cartridge_type": "40g",
    "silica_cartridge_id": "sc-001",
    "sample_cartridge_location_id": "shelf-B1",
    "sample_cartridge_type": "standard",
    "sample_cartridge_id": "sac-001",
    "work_station_id": "ws-01"
  }
}
```

**Mock behavior:** 1.5-3s delay (at 0.1x multiplier). Returns `code: 200` with entity updates:
- Robot -> `idle` at `ws-01`
- Silica cartridge `sc-001` -> `mounted` at `ws-01`
- Sample cartridge `sac-001` -> `mounted` at `ws-01`
- CCS ext module -> `using`

### Step 2: Setup Tube Rack

```json
{
  "task_id": "task-002",
  "task_name": "setup_tube_rack",
  "params": {
    "tube_rack_location_id": "shelf-C2",
    "work_station_id": "ws-01",
    "end_state": "idle"
  }
}
```

**Mock behavior:** 1-2s delay. Returns tube rack -> `mounted`, robot -> `idle`.

### Step 3: Take Pre-Run Photo

```json
{
  "task_id": "task-003",
  "task_name": "take_photo",
  "params": {
    "work_station_id": "ws-01",
    "device_id": "cc-system-01",
    "device_type": "column_chromatography_system",
    "components": ["screen", "column"],
    "end_state": "idle"
  }
}
```

**Mock behavior:** 0.4-1.0s delay (2 components). Returns 2 `CapturedImage` entries with mock URLs and robot -> `idle`.

### Step 4: Start Column Chromatography (Long-Running)

```json
{
  "task_id": "task-004",
  "task_name": "start_column_chromatography",
  "params": {
    "work_station_id": "ws-01",
    "device_id": "cc-system-01",
    "device_type": "column_chromatography_system",
    "experiment_params": {
      "silicone_column": "40g",
      "peak_gathering_mode": "peak",
      "air_clean_minutes": 5,
      "run_minutes": 45,
      "need_equilibration": true,
      "left_rack": "10x75mm",
      "right_rack": "10x75mm"
    },
    "end_state": "wait_for_screen_manipulation"
  }
}
```

**Mock behavior (long-running pattern):**
1. Message is acknowledged immediately; simulation runs in a background asyncio task
2. **Initial intermediate update** (via `{robot_id}.log`): robot -> `watch_column_machine_screen`, CC system -> `running` with experiment params and ISO timestamp, cartridges -> `using`, tube rack -> `using`
3. **Periodic progress updates** (via `{robot_id}.log`): CC system -> `running` published every N seconds
4. **Final result** (via `{robot_id}.result`, `code: 200`): robot -> `wait_for_screen_manipulation`, CC system -> `running`

### Step 5: Terminate CC

```json
{
  "task_id": "task-005",
  "task_name": "terminate_column_chromatography",
  "params": {
    "work_station_id": "ws-01",
    "device_id": "cc-system-01",
    "device_type": "column_chromatography_system",
    "end_state": "idle"
  }
}
```

**Mock behavior:** 0.5-1s delay. Returns CC system -> `terminated`, cartridges -> `used`, tube rack -> `used`, plus a captured `screen` image.

### Step 6: Fraction Consolidation

```json
{
  "task_id": "task-006",
  "task_name": "fraction_consolidation",
  "params": {
    "work_station_id": "ws-01",
    "device_id": "cc-system-01",
    "device_type": "column_chromatography_system",
    "collect_config": [1, 1, 0, 1, 1, 0, 0, 1],
    "end_state": "moving_with_round_bottom_flask"
  }
}
```

**Mock behavior:** Delay scales with tube count (5 collected × 3s + 10s base = 25s × 0.1 ≈ 2.5s). Returns:
- Robot -> `moving_with_round_bottom_flask`
- Tube rack -> `used,pulled_out,ready_for_recovery`
- Round bottom flask -> `used,ready_for_evaporate`
- Left/right PCC chutes with positioning data

### Step 7: Start Evaporation (Long-Running)

```json
{
  "task_id": "task-007",
  "task_name": "start_evaporation",
  "params": {
    "work_station_id": "ws-01",
    "device_id": "evaporator-01",
    "device_type": "evaporator",
    "profiles": {
      "start": {
        "lower_height": 150.0,
        "rpm": 120,
        "target_temperature": 45.0,
        "target_pressure": 200.0
      },
      "stop": {
        "trigger": { "type": "time_from_start", "time_in_sec": 3600 }
      }
    },
    "post_run_state": "idle"
  }
}
```

**Mock behavior (long-running pattern):**
1. **Initial intermediate update** (via `{robot_id}.log`): robot -> `observe_evaporation`, evaporator -> `running=True` with ambient values (`current_temperature=25.0C`, `current_pressure=1013.0 mbar`)
2. **Periodic ramp updates** (via `{robot_id}.log`): evaporator readings linearly interpolate toward targets (temperature: 25C -> 45C, pressure: 1013 -> 200 mbar)
3. **Final result** (via `{robot_id}.result`, `code: 200`): evaporator -> `running=False`, `current_temperature=45.0`, `current_pressure=200.0`, robot -> `idle`

### Step 8: Collapse Cartridges

```json
{
  "task_id": "task-008",
  "task_name": "collapse_cartridges",
  "params": {
    "work_station_id": "ws-01",
    "silica_cartridge_id": "sc-001",
    "sample_cartridge_id": "sac-001",
    "end_state": "idle"
  }
}
```

**Mock behavior:** 1-1.5s delay. Returns cartridges -> `used` (ready for disposal), CCS ext module -> `used`, robot -> `idle`.

**Prerequisite:** Robot must be `idle`. If step 7 used `post_run_state: "observe_evaporation"`, run `stop_evaporation` first.

### Testing Error Handling

Inject failures to test the main service's error recovery:

```bash
# 20% of tasks fail with realistic robot errors
MOCK_FAILURE_RATE=0.2 uv run python -m src.main

# All tasks timeout (no response published)
MOCK_DEFAULT_SCENARIO=timeout uv run python -m src.main

# Fast iteration: 100x speed + 10% failure rate
MOCK_BASE_DELAY_MULTIPLIER=0.01 MOCK_FAILURE_RATE=0.1 uv run python -m src.main
```

Example failure result for `setup_cartridges`:
```json
{
  "code": 1012,
  "msg": "Silica cartridge gripper malfunction: unable to secure cartridge",
  "task_id": "task-001",
  "updates": []
}
```

### Key Observations

1. **Quick vs. long-running**: Tasks like `setup_cartridges` (15-30s) block the consumer until complete, while `start_cc` and `start_evaporation` run in background asyncio tasks — the consumer immediately acknowledges the message and can process other commands concurrently.

2. **Intermediate updates via log channel**: Long-running tasks publish entity state changes in real-time via `{robot_id}.log`, allowing the main service to update its database incrementally. Final results go via `{robot_id}.result`.

3. **Timing fidelity**: At `MOCK_BASE_DELAY_MULTIPLIER=0.01`, a 45-minute CC run completes in ~27 seconds. At `1.0`, it takes the full 45 minutes. This enables both fast CI testing and realistic integration testing.

4. **Scenario injection**: `MOCK_FAILURE_RATE` and `MOCK_TIMEOUT_RATE` apply per-message random injection, while `MOCK_DEFAULT_SCENARIO` sets a global default. This allows testing specific error paths or general resilience.

5. **WorldState preconditions**: The server validates entity states before execution, returning 2000-series error codes for precondition violations. This catches workflow errors (e.g., starting CC when already running) without needing the real BIC Lab Service validation.
