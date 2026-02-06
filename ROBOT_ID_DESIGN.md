# Robot ID Design Document

## Overview

This document explains how `robot_id` is used in the mock robot server architecture and why it **should NOT** be included in task parameters.

## Architecture

### RabbitMQ Topic Exchange Pattern

```
┌─────────┐                    ┌───────────────┐                    ┌────────────┐
│ LabRun  │                    │  bic_exchange │                    │ Robot Mock │
│         │                    │    (TOPIC)    │                    │  Server    │
└─────────┘                    └───────────────┘                    └────────────┘
     │                                 │                                    │
     │  publish(routing_key:           │                                    │
     │    "talos_001.cmd")            │                                    │
     ├────────────────────────────────>│                                    │
     │                                 │  queue: talos_001.cmd             │
     │                                 │  binding: talos_001.cmd           │
     │                                 ├──────────────────────────────────>│
     │                                 │                                    │
     │                                 │  publish(routing_key:              │
     │                                 │    "talos_001.result")            │
     │  queue: results                 │<───────────────────────────────────┤
     │  binding: #.result              │                                    │
     │<────────────────────────────────┤                                    │
```

### Routing Keys

Each robot instance uses its `robot_id` to construct routing keys:

| Channel   | Routing Key Pattern | Direction      | Purpose                          |
|-----------|---------------------|----------------|----------------------------------|
| Command   | `{robot_id}.cmd`    | LabRun → Robot | Task commands                    |
| Result    | `{robot_id}.result` | Robot → LabRun | Task results (success/failure)   |
| Log       | `{robot_id}.log`    | Robot → LabRun | Real-time state updates          |
| Heartbeat | `{robot_id}.hb`     | Robot → LabRun | Periodic health check (every 2s) |

### LabRun Bindings

LabRun binds to wildcard patterns to receive messages from all robots:

```python
# LabRun side (pseudo-code)
queue.bind(exchange="bic_exchange", routing_key="#.result")  # All results
queue.bind(exchange="bic_exchange", routing_key="#.log")     # All logs
queue.bind(exchange="bic_exchange", routing_key="#.hb")      # All heartbeats
```

## Robot ID Configuration

### Mock Server Configuration

The mock server's `robot_id` is configured via environment variable:

```bash
# .env or .env.mock
MOCK_ROBOT_ID=talos_001
```

Or in `src/config.py`:

```python
class MockSettings(BaseSettings):
    robot_id: str = "00000000-0000-4000-a000-000000000001"  # Default UUID format
```

### Multi-Robot Deployment

To run multiple robot instances:

```bash
# Terminal 1: Robot 1
MOCK_ROBOT_ID=talos_001 uv run python -m src.main

# Terminal 2: Robot 2
MOCK_ROBOT_ID=talos_002 uv run python -m src.main

# Terminal 3: Robot 3
MOCK_ROBOT_ID=talos_003 uv run python -m src.main
```

Or using Docker Compose:

```yaml
services:
  robot-001:
    image: mock-robot-server
    environment:
      - MOCK_ROBOT_ID=talos_001

  robot-002:
    image: mock-robot-server
    environment:
      - MOCK_ROBOT_ID=talos_002
```

## Why robot_id is NOT in Task Parameters

### Design Principle

**The `robot_id` is part of the transport layer (routing), not the application layer (task parameters).**

### Reasons

1. **Routing Context**: The `robot_id` is already implicit in the routing key when LabRun sends a command to `{robot_id}.cmd`. The receiving robot knows its own identity from configuration.

2. **Separation of Concerns**:
   - **Transport layer**: Where to send the message (routing key)
   - **Application layer**: What to do and with what parameters (task params)

3. **Avoid Redundancy**: Including `robot_id` in params would be redundant since:
   - LabRun already specified it in the routing key
   - Robot already knows its own ID from configuration

4. **Consistency**: Other entity IDs in params (e.g., `work_station_id`, `silica_cartridge_id`) refer to **external entities** that the robot needs to interact with, not the robot itself.

### Example: Correct Message Format

```json
{
  "task_id": "task-123",
  "task_name": "setup_tubes_to_column_machine",
  "params": {
    "work_station_id": "ws-001",              // ✅ External entity
    "silica_cartridge_id": "sc-001",          // ✅ External entity
    "silica_cartridge_location_id": "loc-1",  // ✅ External entity
    "silica_cartridge_type": "sepaflash_40g", // ✅ Task parameter
    "sample_cartridge_id": "sac-001",         // ✅ External entity
    "sample_cartridge_location_id": "loc-2",  // ✅ External entity
    "sample_cartridge_type": "ilok_40g"       // ✅ Task parameter
    // ❌ NO robot_id here!
  }
}
```

**Routing**: LabRun publishes this message with routing key `talos_001.cmd`

### What Happens If robot_id is Included?

If LabRun mistakenly includes `robot_id` in `params`:

```json
{
  "params": {
    "work_station_id": "ws-001",
    "robot_id": "talos_001"  // ❌ Extra field
  }
}
```

**Result**: The extra field is **silently ignored** by Pydantic validation (default behavior: `extra="ignore"`).

**Why this is safe**: The parameter models (`SetupCartridgesParams`, etc.) don't define a `robot_id` field, so Pydantic discards it during validation.

## Where robot_id IS Used

### 1. Heartbeat Messages (Message Body)

```json
{
  "robot_id": "talos_001",       // ✅ Identifies which robot is alive
  "timestamp": "2025-02-06T12:34:56Z",
  "state": "idle"
}
```

**Routing**: Published with routing key `talos_001.hb`

**Why needed**: LabRun binds to `#.hb` (all robots), so it needs to know which robot sent each heartbeat.

### 2. Result/Log Messages (Implicit via Routing Key)

The `robot_id` is implicit in the routing key:

```json
{
  "code": 0,
  "msg": "Success",
  "task_id": "task-123",
  "updates": [...]
  // ❌ NO robot_id in the message body
}
```

**Routing**: Published with routing key `talos_001.result`

**Why not needed in body**: LabRun can extract the robot ID from the routing key if needed.

## Summary Table

| Use Case                   | robot_id in Message Body? | robot_id in Routing Key? | Notes                                  |
|----------------------------|---------------------------|--------------------------|----------------------------------------|
| Task Command (params)      | ❌ No                      | ✅ Yes (`*.cmd`)          | Implicit via routing                   |
| Task Result                | ❌ No                      | ✅ Yes (`*.result`)       | Implicit via routing                   |
| Log Stream                 | ❌ No                      | ✅ Yes (`*.log`)          | Implicit via routing                   |
| Heartbeat                  | ✅ Yes                     | ✅ Yes (`*.hb`)           | Needed because LabRun binds to `#.hb`  |
| Mock Server Configuration  | ✅ Yes (config)            | N/A                      | Environment variable `MOCK_ROBOT_ID`   |

## Testing

### Verify Extra Fields are Ignored

```python
from src.schemas.commands import SetupCartridgesParams

params_with_extra = {
    'work_station_id': 'ws-1',
    'silica_cartridge_id': 'sc-001',
    # ... other required fields ...
    'robot_id': 'talos_001',  # Extra field
    'unknown_field': 'value'  # Another extra field
}

params = SetupCartridgesParams.model_validate(params_with_extra)
# ✅ Validation succeeds, extra fields are ignored
# params.robot_id  # ❌ AttributeError: no such attribute
```

### Send Test Message

Use the included test script:

```bash
# Ensure mock server is running
uv run python -m src.main

# In another terminal
uv run python test_labrun_message.py
```

The script sends a properly formatted message (without `robot_id` in params) to verify correct behavior.

## Conclusion

**LabRun should NOT include `robot_id` in task parameters.** The robot identity is conveyed through the MQ routing key, which is the correct design for a topic-based exchange architecture. Including it in params would be redundant and violate separation of concerns.
