# Mock Robot Server — CLAUDE.md

## Project Overview

This repository is a **mock Exchange server** that simulates the RabbitMQ-based communication layer between **LabRun** (the orchestrator) and **Robot workers** (Talos humanoid robots) in a BIC (Bio-Inspired Chemistry) laboratory automation system. It replaces the real robot-side `mars_service` for development and testing of the LabRun side.

### Target Architecture (from `system_architecture.png` and `v0.2 Skill-level Runtime Service.pdf`)

```
LabRun ──publish──> [Exchange (TOPIC)] ──queue_bind──> [robot_id.cmd] ──consume──> Robot
LabRun <──consume── [#.log / #.result / #.hb] <──publish── Robot
LabRun <──read──── [MinIO] <──write── Robot (photos, objects)
```

The architecture runs on an **Edge Box** with:
- **RabbitMQ** — Central TOPIC exchange for all message routing
- **MinIO** — Object storage for photos/captures
- **Local Server** — Optional edge-side offline monitor/logger

**IMPORTANT**: `robot_id` is used for routing (via MQ routing keys) and configuration, but **should NOT be included in task parameters**. See [ROBOT_ID_DESIGN.md](./ROBOT_ID_DESIGN.md) for detailed explanation.

---

## Gap Analysis: Current State vs. Target Specification

### Legend
- `[DONE]` — Fully implemented and tested
- `[PARTIAL]` — Implemented but incomplete or diverges from spec
- `[MISSING]` — Not implemented at all

---

### 1. Communication Layer (RabbitMQ Exchange)

| Aspect | Spec Requirement | Current State | Gap |
|--------|-----------------|---------------|-----|
| Exchange type | Single TOPIC exchange for all messages | `[DONE]` | Uses single TOPIC exchange (`bic_exchange`) with proper routing keys |
| Routing keys — Commands | `<robot_id>.cmd` (e.g. `talos_001.cmd`) | `[DONE]` | Command queue bound to `<robot_id>.cmd` pattern |
| Routing keys — Logs | `<robot_id>.log` and `device_xxx.log` | `[DONE]` | LogProducer publishes to `<robot_id>.log` during skill execution |
| Routing keys — Results | `<robot_id>.result` | `[DONE]` | ResultProducer publishes via `<robot_id>.result` routing key |
| Routing keys — Heartbeat | `<robot_id>.hb` | `[DONE]` | HeartbeatPublisher sends periodic messages via `<robot_id>.hb` |
| Queue binding on LabRun side | Binds `#.log`, `#.result`, `#.hb` wildcards | N/A (not LabRun side) | — |
| Queue binding on Robot side | Binds `<robot_id>.cmd` per robot | `[DONE]` | Consumer binds to `<robot_id>.cmd` queue |
| Multi-robot support | Multiple robots (`talos_001`, `talos_002`, etc.) | `[PARTIAL]` | Single `robot_id` per instance; can run multiple instances with different IDs |

### 2. Skill API — Command/Response Contract

| Skill | Spec Task Name | Current Task Name | Status | Gap Details |
|-------|---------------|-------------------|--------|-------------|
| Setup Cartridges | `setup_tubes_to_column_machine` | `setup_tubes_to_column_machine` | `[DONE]` | Request/response schemas match |
| Setup Tube Rack | `setup_tube_rack` | `setup_tube_rack` | `[DONE]` | Request/response schemas match |
| Collapse Cartridges | `collapse_cartridges` | `collapse_cartridges` | `[DONE]` | Request/response schemas match |
| Take Photo | `take_photo` | `take_photo` | `[DONE]` | Request/response schemas match |
| Start CC | `start_column_chromatography` | `start_column_chromatography` | `[DONE]` | Long-running with intermediate updates |
| Terminate CC | `terminate_column_chromatography` | `terminate_column_chromatography` | `[DONE]` | Includes screen capture on termination |
| Fraction Consolidation | `fraction_consolidation` | `fraction_consolidation` | `[DONE]` | `collect_config` array handled correctly |
| Start Evaporation | `start_evaporation` | `start_evaporation` | `[DONE]` | Profiles/triggers system implemented |

### 3. Real-time Log Streaming

| Aspect | Spec Requirement | Current State | Gap |
|--------|-----------------|---------------|-----|
| Log channel | Robot publishes state updates via `<robot_id>.log` routing key **as they happen** during skill execution | `[DONE]` | LogProducer publishes state changes to `<robot_id>.log` during execution |
| Device log channel | Device state published via `device_xxx.log` | `[PARTIAL]` | No device-specific log routing (all logs go to `<robot_id>.log`) |
| Incremental updates | Each state change emits an individual update message | `[DONE]` | All simulators emit log entries for significant state transitions |

### 4. Heartbeat System

| Aspect | Spec Requirement | Current State | Gap |
|--------|-----------------|---------------|-----|
| Heartbeat publishing | Robot publishes heartbeat every 2 seconds via `<robot_id>.hb` | `[DONE]` | HeartbeatPublisher sends periodic messages (configurable interval) |
| Heartbeat format | Periodic pulse message | `[DONE]` | HeartbeatMessage schema with robot_id, timestamp, state |
| Online/offline detection | LabRun detects offline if >5 seconds without heartbeat | N/A (LabRun side) | — |

### 5. MinIO / Object Storage Integration

| Aspect | Spec Requirement | Current State | Gap |
|--------|-----------------|---------------|-----|
| Photo upload | Robot saves photos to MinIO, returns accessible URL | `[PARTIAL]` — Generates mock URLs (`http://minio:9000/bic-robot/captures/...`) | URLs are fabricated; no actual MinIO interaction. Acceptable for mock server, but URL format should match real MinIO bucket paths. |
| Object retrieval | LabRun reads images/objects from MinIO by URI | N/A (LabRun side) | — |
| Local Server dump | Local Server dumps logs to MinIO | `[MISSING]` | Not in scope for mock server |

### 6. State Management

| Aspect | Spec Requirement | Current State | Gap |
|--------|-----------------|---------------|-----|
| Robot states | idle, wait_for_screen_manipulation, watch_column_machine_screen, moving_with_round_bottom_flask, observe_evaporation | `[DONE]` | All defined in `RobotState` enum |
| Entity states | mounted, using, used, running, terminated, evaporating | `[DONE]` | Defined in `EntityState` enum (v0.3 ground truth) |
| Compound states | e.g. `"used,pulled_out,ready_for_recovery"` | `[PARTIAL]` | Handled as raw strings in some cases, no formal state machine |
| Entity types — 10 types | robot, silica_cartridge, sample_cartridge, tube_rack, round_bottom_flask, ccs_ext_module, column_chromatography_system, evaporator, pcc_left_chute, pcc_right_chute | `[DONE]` | All 10 entity types have factory functions and Pydantic models |
| Device state lifecycle | Formal state transitions (spec notes: "needs systematic design") | `[PARTIAL]` | States exist but no validation of legal transitions |

### 7. Error Handling

| Aspect | Spec Requirement | Current State | Gap |
|--------|-----------------|---------------|-----|
| Safety conflict detection | Robot checks preconditions (e.g., cartridge position, existing mounts) | `[DONE]` | PreconditionChecker validates state before task execution |
| Stateful error responses | Errors based on current world state | `[DONE]` | WorldState tracks all entities; precondition failures return error code 2000-2099 |
| Error code ranges | Task-specific error codes | `[DONE]` | Codes 1010-1089 for task failures, 2000-2099 for precondition violations |

### 8. Configuration & Deployment

| Aspect | Spec Requirement | Current State | Gap |
|--------|-----------------|---------------|-----|
| Docker | Containerized deployment | `[DONE]` | Multi-stage Alpine Dockerfile |
| Docker Compose | Service integration with BIC Lab Service | `[DONE]` | `docker-compose.mock.yml` override |
| Env config | Environment-based configuration | `[DONE]` | Pydantic-settings with `MOCK_` prefix |
| Multi-robot instances | Run multiple robot workers | `[PARTIAL]` | Single robot_id per instance; need ability to spin up N instances |

### 9. Testing

| Aspect | Current State | Gap |
|--------|---------------|-----|
| Unit tests | `[DONE]` — 108 tests covering all components | — |
| Integration tests (MQ) | `[DONE]` — 8 consumer integration tests verifying dispatch flow, world state, preconditions, scenarios |  |
| Simulator integration tests | `[DONE]` — 3 simulator tests verifying end-to-end task execution | — |
| Heartbeat tests | `[DONE]` — Heartbeat publisher lifecycle and message publishing tested | — |
| Multi-robot tests | `[PARTIAL]` | No multi-robot scenarios; single instance tested |

---

## Implementation Plan

### Phase 1: MQ Topology Alignment ✅ COMPLETE

**Goal:** Align the RabbitMQ exchange and routing key patterns with the spec's single-exchange architecture.

✅ Single TOPIC exchange (`bic_exchange`) with per-robot routing keys
✅ Command routing via `<robot_id>.cmd`
✅ Result routing via `<robot_id>.result`
✅ Log routing via `<robot_id>.log`
✅ Heartbeat routing via `<robot_id>.hb`

### Phase 2: Real-time Log Channel ✅ COMPLETE

**Goal:** Implement the `<robot_id>.log` channel for real-time state updates during skill execution.

✅ LogProducer publishes to `<robot_id>.log` routing key
✅ All simulators emit log entries for state transitions
✅ Long-running tasks (CC, Evaporation) publish intermediate logs

### Phase 3: Heartbeat System ✅ COMPLETE

**Goal:** Implement the periodic heartbeat mechanism per spec.

✅ HeartbeatPublisher with configurable interval (default 2s)
✅ HeartbeatMessage schema (robot_id, timestamp, state)
✅ Graceful lifecycle management (start/stop with MQ connection)

### Phase 4: TODO Skills Stubs ✅ COMPLETE

**Goal:** Add placeholder simulators for the spec's TODO skills to complete the API surface.

✅ `stop_evaporation` — Implemented in CleanupSimulator
✅ `setup_ccs_bins` — Implemented in CleanupSimulator
✅ `return_ccs_bins` — Implemented in CleanupSimulator
✅ `return_cartridges` — Implemented in CleanupSimulator
✅ `return_tube_rack` — Implemented in CleanupSimulator

### Phase 5: World State Tracking ✅ COMPLETE

**Goal:** Add in-memory state tracking to enable stateful error simulation.

✅ WorldState class tracks all entities (robots, devices, materials)
✅ PreconditionChecker validates state before task execution
✅ State-driven error responses (error codes 2000-2099)
✅ `reset_state` command to clear world state

### Phase 6: Integration Tests & Documentation ✅ COMPLETE

**Goal:** End-to-end confidence in the mock server.

✅ Consumer integration tests (8 tests) — Full dispatch flow, world state tracking, preconditions, scenario injection
✅ Simulator integration tests (8 tests) — End-to-end task execution verification
✅ Documentation updates (CLAUDE.md updated with implementation status)

---

## Quick Reference

### Tech Stack
- **Python 3.12+**, async-first
- **aio-pika** (RabbitMQ), **pydantic** (schemas), **loguru** (logging)
- **uv** (package manager), **ruff** (lint/format), **pytest** (testing)

### Project Structure
```
src/
  config.py          # Pydantic-settings, MOCK_ env prefix
  main.py            # Entry point, wiring, graceful shutdown
  mq/                # RabbitMQ connection, consumer, producer, log producer, heartbeat
  schemas/           # Protocol enums, command/result Pydantic models
  simulators/        # Per-skill simulation logic (base ABC + 5 simulators)
  generators/        # Pure factories for entity updates, images, timing
  scenarios/         # Failure/timeout injection
  state/             # WorldState tracking, precondition checking
  tests/             # 108 tests (unit + integration)
```

### Running
```bash
uv run python -m src.main          # Run mock server
uv run pytest src/tests/           # Run tests
```

### Key Config (`.env`)
```env
MOCK_MQ_HOST=localhost
MOCK_MQ_EXCHANGE=robot.exchange                          # Single TOPIC exchange
MOCK_ROBOT_ID=talos.001                                  # String format (was UUID)
MOCK_BASE_DELAY_MULTIPLIER=0.01   # 100x speed (0.1 = 10x, 1.0 = realistic)
MOCK_FAILURE_RATE=0.0             # 0.0-1.0
MOCK_TIMEOUT_RATE=0.0             # 0.0-1.0
MOCK_DEFAULT_SCENARIO=success     # success | failure | timeout
MOCK_HEARTBEAT_INTERVAL=2.0      # seconds between heartbeats
```

### Implemented Skills (v0.3 Ground Truth — 8 Tasks)
1. `setup_tubes_to_column_machine` — Mount cartridges to CCS workstation
2. `setup_tube_rack` — Mount tube rack to CCS workstation
3. `collapse_cartridges` — Disassemble used cartridges
4. `take_photo` — Photograph device components
5. `start_column_chromatography` — Long-running CC with intermediate updates
6. `terminate_column_chromatography` — Stop CC, capture results
7. `fraction_consolidation` — Collect fractions, prepare for evaporation
8. `start_evaporation` — Long-running evaporation with sensor ramp

### World State Tracking & Preconditions

The mock server tracks an in-memory world state for all entities (robots, devices, materials) and validates preconditions before executing tasks. This enables realistic error simulation based on current system state.

**Error Code Ranges:**
- `1000-1009`: General errors (unknown task, validation failure)
- `1010-1089`: Task-specific failures (per-task 10-code ranges)
- `2000-2099`: Precondition violations (state-driven errors)

**Special Commands:**
- `reset_state`: Clears world state back to initial conditions (useful for testing)

**Precondition Examples:**
- `setup_cartridges` fails if ext_module already has cartridges (code 2001)
- `terminate_cc` fails if CC system not running (code 2030-2031)
- `collapse_cartridges` fails if cartridges not in 'used' state (code 2010-2013)

### Lessons Learned

- **HeartbeatPublisher now reports actual robot state from WorldState** — Previously, heartbeat messages always reported `state: "idle"` regardless of the robot's actual operational state. This caused the BIC Lab Service to overwrite real robot states (e.g., `"watch_column_machine_screen"`) back to `"idle"` during heartbeat processing. The fix passes `WorldState` to `HeartbeatPublisher` so it reads the current robot state from the in-memory state tracker (2026-02-07).

- **WorldState entity keys don't always match `work_station_id`** — Materials like `tube_rack` and `round_bottom_flask` are keyed in WorldState by their actual entity ID (often a `location_id` string like `"bic_09C_l3_002"`), NOT by the `work_station_id` where they're located. Both `PreconditionChecker` and simulators must resolve entities by searching the `location` property via `_find_entity_at_location()`, not by assuming `entity_id == work_station_id`. See `src/state/preconditions.py:_find_entity_at_location()` and `src/simulators/base.py:_resolve_entity_id()` (2026-02-07).

- **Simulators must resolve material UUIDs from WorldState** — When commands like `start_cc`, `terminate_cc`, and `fraction_consolidation` don't include explicit material IDs, simulators use `_resolve_entity_id(entity_type, work_station_id)` from `BaseSimulator` to look up the actual entity ID from WorldState by searching for entities located at the given work_station_id. This ensures entity update messages contain the correct IDs that BIC-lab-service can map back to DB records. See `cc_simulator.py`, `consolidation_simulator.py`, `evaporation_simulator.py` (2026-02-07).

- **Never add fields to command schemas that aren't in `docs/robots/note.md`** — The `note.md` in BIC-lab-service is the canonical protocol spec. Adding fields like `tube_rack_id` to `SetupTubeRackParams` that aren't in the spec creates protocol drift. Instead, resolve IDs internally via WorldState lookups. Always cross-reference `note.md` before changing message schemas (2026-02-07).

- **Never relax strict enum types to `str` — add missing values to the enum instead** — When encountering validation errors for unknown enum values, the correct fix is to add the missing values to the enum, NOT to change the field type from enum to `str`. Note: in the v0.3 strict alignment (2026-02-10), intermediate robot states (`moving`, `terminating_cc`, `pulling_out_tube_rack`) were removed from `RobotState` since they are not in the ground truth. Simulators now use `RobotState.IDLE` for transit states.

- **Photo simulator must map all actual device_type values** — The `entity_type_map` in `photo_simulator.py` must include all device_type strings that BIC-lab-service sends (e.g., `isco_combiflash_nextgen_300`, `column_chromatography_system`, `rotary_evaporator`), not just shortened aliases. Missing mappings caused "Unknown device_type for photo" warnings (2026-02-07).

- **Test entity IDs must match WorldState keys** — In `test_full_workflow.py`, entity lookups in assertions must use the actual entity IDs (e.g., `sc-001`, `samp-001`, `rack-loc-1`) that were registered in WorldState during setup, not `work_station_id`. WorldState keys materials by their entity ID, not by the work station where they're located (2026-02-07).

- **v0.3 ground truth alignment (2026-02-10)** — Aligned all schemas to `docs/robot_messages_new.py` ground truth. Key changes: `EquipmentState` renamed to `EntityState` (backward alias kept), `PeakGatheringMode` now `StrEnum`, `CCExperimentParams.air_purge_minutes: float` → `air_clean_minutes: int`, removed `solvent_a`/`solvent_b` from `CCExperimentParams`, deleted `TerminateCCExperimentParams` and `experiment_params` field from `TerminateCCParams`, `EvaporationProfiles.updates` → `lower_pressure` (single profile), `EvaporationProfile` fields made required (no `| None`), removed `create_time` from `CapturedImage`, `TaskName.FRACTION_CONSOLIDATION` value changed to `"fraction_consolidation"`, property types tightened to enums (`RobotState`, `EntityState`, `BinState`, `CCExperimentParams`), `CCSystemUpdate.type` now `Literal["column_chromatography_system", "isco_combiflash_nextgen_300"]` without default, added `TypedRobotCommand[P]` generic class with concrete aliases. **Golden rule: `docs/robot_messages_new.py` is the single source of truth for all message schemas.**

- **v0.3 strict alignment — remove all extras (2026-02-10)** — Removed 5 tasks not in ground truth (`stop_evaporation`, `setup_ccs_bins`, `return_ccs_bins`, `return_cartridges`, `return_tube_rack`), 3 intermediate robot states (`moving`, `terminating_cc`, `pulling_out_tube_rack`), 4 extra entity states (`available`, `returned`, `maintenance`, `error`), the `EquipmentState` backward alias, and the entire `CleanupSimulator`. Reduced task count from 13 to 8, test count from ~134 to 108. Simulators now use `RobotState.IDLE` for transit states since the ground truth has no intermediate movement states.
