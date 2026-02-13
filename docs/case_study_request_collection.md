# Case Study: Robot Skill Request & Response Collection

> Aligned with **v0.3 Skill-level Runtime Service** specification and
> ground truth schemas: `docs/prd_robots/robot_messages_new.py`,
> `app/data/schemas/messages.py`, `alembic/versions/0002_seed_test_data.py`.
>
> **Notes:**
> - `robot_id` is NOT included in request params — it is specified via the MQ routing key (e.g., `talos.001.cmd`).
> - The command envelope uses `task_type` (not `task_name`). See `RobotCommand` in ground truth.
> - `end_state` / `post_run_state` are NOT part of MQ command params — they are handled by the service layer.
> - Response `updates` are `EntityUpdate[]` discriminated union — actual updates may vary at runtime.
> - Response `images` are `CapturedImage[]` type.
> - Success code is `200`.
> - All identifiers below match the ground truth enums and seed data.

---

## Identifier Reference (Ground Truth)

| Category                  | Ground Truth Value          | Notes                               |
| ------------------------- | --------------------------- | ----------------------------------- |
| Robot ID                  | `talos.001`                 | String PK, also MQ routing prefix   |
| CC Work Station           | `ws_bic_09_fh_001`          | `WorkStation.WS_BIC_09_FH_001`      |
| RE Work Station           | `ws_bic_09_fh_002`          | `WorkStation.WS_BIC_09_FH_002`      |
| CC Machine device_id      | `cc-isco-300p_001`          | `DeviceID.CC_ISCO_300P_001`         |
| CC Machine device_type    | `cc-isco-300p`              | `DeviceType.CC_ISCO_300P`           |
| CCS Ext Module device_id  | `cc-aux-c12-gen1_001`       | `DeviceID.CC_AUX_C12_GEN1_001`      |
| Evaporator device_id      | `re-buchi-r180_001`         | `DeviceID.RE_BUCHI_R180_001`        |
| Evaporator device_type    | `re-buchi-r180`             | `DeviceType.RE_BUCHI_R180`          |
| Vacuum Pump device_id     | `pp-vacuubrand-pc3001_001`  | `DeviceID.PP_VACUUBRAND_PC3001_001` |
| Silica Cartridge Type     | `silica_40g`                | `CCSiliconCartridgeType` enum       |
| Sample Cartridge Type     | `sample_40g`                | `CCSampleCartridgeType` enum        |
| Sample Cartridge Location | `bic_09B_l3_002`            | `CCSampleCartridgeLocation` enum    |

---

## 1. setup_cartridges

Retrieve and mount silica + sample cartridges at a CC work station.
**Wire task_type:** **`setup_tubes_to_column_machine`**

### Request

```json
{
    "task_id": "task-setup-cartridges-001",
    "task_type": "setup_tubes_to_column_machine",
    "params": {
        "silica_cartridge_type": "silica_40g",
        "sample_cartridge_location": "bic_09B_l3_002",
        "sample_cartridge_type": "sample_40g",
        "sample_cartridge_id": "sample_40g_001",
        "work_station": "ws_bic_09_fh_001"
    }
}
```

> **v0.3 changes from PDF draft:**
> - Removed `silica_cartridge_location_id` — robot handles silica pickup autonomously.
> - Removed `silica_cartridge_id` — silica cartridges have no special identity.
> - Removed `sample_cartridge_location_id` — replaced by `sample_cartridge_location`.
> - Field `work_station_id` → `work_station` (matches ground truth schema).
> - Cartridge type values normalized: `sepaflash_40g` → `silica_40g`, `ilok_40g` → `sample_40g`.

### Example Response

```json
{
    "code": 200,
    "msg": "success",
    "task_id": "task-setup-cartridges-001",
    "updates": [
        {
            "type": "robot",
            "id": "talos.001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "idle",
                "description": ""
            }
        },
        {
            "type": "silica_cartridge",
            "id": "silica_40g_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "inuse",
                "description": ""
            }
        },
        {
            "type": "sample_cartridge",
            "id": "sample_40g_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "inuse",
                "description": ""
            }
        },
        {
            "type": "ccs_ext_module",
            "id": "cc-aux-c12-gen1_001",
            "properties": {
                "state": "using",
                "description": ""
            }
        }
    ]
}
```

> **Response notes:**
> - Cartridge `state` uses `ConsumableState`: `unused` → `inuse` → `used`.
> - CCS ext module `state` uses `DeviceState`: `idle` / `using` / `unavailable`.
> - All Properties models include a `description` field (default `""`).

---

## 2. setup_tube_rack

Retrieve and mount a tube rack at a CC work station.

**Wire task_type:** `setup_tube_rack`

### Request

```json
{
    "task_id": "task-setup-tube-rack-001",
    "task_type": "setup_tube_rack",
    "params": {
        "work_station": "ws_bic_09_fh_001"
    }
}
```

> **v0.3 changes from PDF draft:**
> - Removed `tube_rack_location_id` — robot handles tube rack pickup autonomously.
> - Removed `end_state` — handled by service layer (default: `idle`).
> - Field `work_station_id` → `work_station`.

### Example Response

```json
{
    "code": 200,
    "task_id": "task-setup-tube-rack-001",
    "msg": "success",
    "updates": [
        {
            "type": "robot",
            "id": "talos.001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "working",
                "description": "wait_for_screen_manipulation"
            }
        },
        {
            "type": "tube_rack",
            "id": "tube_rack_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "inuse",
                "description": "mounted"
            }
        }
    ]
}
```

> **Response notes:**
> - Robot `state` uses `RobotState`: `idle` / `working` / `charging` / `disconnected`.
>   The robot-specific posture (e.g., `wait_for_screen_manipulation`) goes into `description`.
> - Tube rack `state` uses `ToolState`: `available` / `inuse` / `contaminated`.

---

## 3. start_column_chromatography

Configure CC parameters via screen manipulation and initiate the chromatography process.

**Wire task_type:** `start_column_chromatography`

### Request

```json
{
    "task_id": "task-start-cc-001",
    "task_type": "start_column_chromatography",
    "params": {
        "work_station": "ws_bic_09_fh_001",
        "device_id": "cc-isco-300p_001",
        "device_type": "cc-isco-300p",
        "experiment_params": {
            "silicone_cartridge": "silica_40g",
            "peak_gathering_mode": "peak",
            "air_purge_minutes": 3.0,
            "run_minutes": 30,
            "need_equilibration": true,
            "solvent_a": "pet_ether",
            "solvent_b": "ethyl_acetate",
            "gradients": [],
            "left_rack": "16x150",
            "right_rack": null
        }
    }
}
```

> **v0.3 changes from PDF draft:**
> - Removed `end_state` — handled by service layer.
> - `silicone_column` → `silicone_cartridge` (uses `CCSiliconCartridgeType` enum values like `silica_40g`).
> - Added `gradients` field (default `[]`).
> - All device IDs/types use normalized naming.

### Example Response

```json
{
    "code": 200,
    "task_id": "task-start-cc-001",
    "msg": "success",
    "updates": [
        {
            "type": "robot",
            "id": "talos.001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "working",
                "description": "watch_column_machine_screen"
            }
        },
        {
            "type": "column_chromatography_machine",
            "id": "cc-isco-300p_001",
            "properties": {
                "state": "using",
                "experiment_params": {
                    "silicone_cartridge": "silica_40g",
                    "peak_gathering_mode": "peak",
                    "air_purge_minutes": 3.0,
                    "run_minutes": 30,
                    "need_equilibration": true,
                    "solvent_a": "pet_ether",
                    "solvent_b": "ethyl_acetate",
                    "gradients": [],
                    "left_rack": "16x150",
                    "right_rack": null
                },
                "start_timestamp": "2025-01-13_01-17-25.312",
                "description": ""
            }
        },
        {
            "type": "silica_cartridge",
            "id": "silica_40g_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "inuse",
                "description": ""
            }
        },
        {
            "type": "sample_cartridge",
            "id": "sample_40g_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "inuse",
                "description": ""
            }
        },
        {
            "type": "tube_rack",
            "id": "tube_rack_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "inuse",
                "description": ""
            }
        },
        {
            "type": "ccs_ext_module",
            "id": "cc-aux-c12-gen1_001",
            "properties": {
                "state": "using",
                "description": ""
            }
        },
        {
            "type": "column_chromatography_machine",
            "id": "cc-isco-300p_001",
            "properties": {
                "state": "using",
                "description": ""
            }
        }
    ]
}
```

> **Response notes:**
> - CC machine update type is `column_chromatography_machine` (canonical) or `isco_combiflash_nextgen_300` (device-alias). Both accepted by discriminated union.
> - CC machine `state` uses `DeviceState`: `idle` / `using` / `unavailable`.

---

## 4. take_photo

Navigate to a station and capture photos of device components.

**Wire task_type:** `take_photo`

### Request (CC Screen Photo)

```json
{
    "task_id": "task-take-photo-cc-001",
    "task_type": "take_photo",
    "params": {
        "work_station": "ws_bic_09_fh_001",
        "device_id": "cc-isco-300p_001",
        "device_type": "cc-isco-300p",
        "components": ["screen"]
    }
}
```

### Request (Evaporator Round Bottom Flask Photo)

```json
{
    "task_id": "task-take-photo-re-001",
    "task_type": "take_photo",
    "params": {
        "work_station": "ws_bic_09_fh_002",
        "device_id": "re-buchi-r180_001",
        "device_type": "re-buchi-r180",
        "components": ["screen"]
    }
}
```

> **v0.3 changes from PDF draft:**
> - Removed `end_state` — handled by service layer.
> - `work_station_id` → `work_station`.
> - `components` uses `DeviceComponent` enum — currently only `"screen"` is supported.
>   `"round_bottom_flask"` is not yet in the `DeviceComponent` enum.

### Example Response

```json
{
    "code": 200,
    "task_id": "task-take-photo-re-001",
    "msg": "success",
    "updates": [],
    "images": [
        {
            "work_station": "ws_bic_09_fh_002",
            "device_id": "re-buchi-r180_001",
            "device_type": "re-buchi-r180",
            "component": "screen",
            "url": "http://minio:9000/photos/re-buchi-r180_001_screen_20260204.jpg",
            "create_time": "2026-02-04_16:18:39.234"
        }
    ]
}
```

> **Response notes:**
> - `CapturedImage` uses `work_station` (not `work_station_id`), matching the ground truth schema.

---

## 5. terminate_column_chromatography

Stop the running CC process, perform air purge, and capture the result screen.

**Wire task_type:** `terminate_column_chromatography`

### Request

```json
{
    "task_id": "task-terminate-cc-001",
    "task_type": "terminate_column_chromatography",
    "params": {
        "work_station": "ws_bic_09_fh_001",
        "device_id": "cc-isco-300p_001",
        "device_type": "cc-isco-300p",
        "experiment_params": {
            "air_purge_minutes": 1.2
        }
    }
}
```

> **v0.3 changes from PDF draft:**
> - Removed `end_state` — handled by service layer.
> - `experiment_params` contains only `air_purge_minutes` for terminate (other fields use defaults).

### Example Response

```json
{
    "code": 200,
    "task_id": "task-terminate-cc-001",
    "msg": "success",
    "updates": [
        {
            "type": "robot",
            "id": "talos.001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "idle",
                "description": ""
            }
        },
        {
            "type": "column_chromatography_machine",
            "id": "cc-isco-300p_001",
            "properties": {
                "state": "idle",
                "description": ""
            }
        },
        {
            "type": "silica_cartridge",
            "id": "silica_40g_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "used",
                "description": ""
            }
        },
        {
            "type": "sample_cartridge",
            "id": "sample_40g_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "used",
                "description": ""
            }
        },
        {
            "type": "tube_rack",
            "id": "tube_rack_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "contaminated",
                "description": "used"
            }
        },
        {
            "type": "ccs_ext_module",
            "id": "cc-aux-c12-gen1_001",
            "properties": {
                "state": "using",
                "description": "cartridges still mounted"
            }
        }
    ]
}
```

> **Response notes:**
> - Tube rack transitions to `contaminated` (`ToolState`) after CC completes.
> - CCS ext module remains `using` — cartridges haven't been removed yet.

---

## 6. collect_column_chromatography_fractions

Pull out tube rack, collect target fractions into a round-bottom flask, discard waste tubes, close waste bin lids, and grab the flask.

**Wire task_type:** `collect_column_chromatography_fractions`

### Request

```json
{
    "task_id": "task-collect-fractions-001",
    "task_type": "collect_column_chromatography_fractions",
    "params": {
        "work_station": "ws_bic_09_fh_001",
        "device_id": "cc-isco-300p_001",
        "device_type": "cc-isco-300p",
        "collect_config": [0, 0, 0, 1, 1, 1, 1, 0, 0, 0]
    }
}
```

> **v0.3 changes from PDF draft:**
> - Removed `end_state` — handled by service layer.

### Example Response

```json
{
    "code": 200,
    "task_id": "task-collect-fractions-001",
    "msg": "success",
    "updates": [
        {
            "type": "robot",
            "id": "talos.001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "working",
                "description": "moving_with_round_bottom_flask"
            }
        },
        {
            "type": "tube_rack",
            "id": "tube_rack_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": "contaminated",
                "description": "pulled_out, ready_for_recovery"
            }
        },
        {
            "type": "round_bottom_flask",
            "id": "rbf_001",
            "properties": {
                "location": "ws_bic_09_fh_001",
                "state": {
                    "content_state": "fill",
                    "has_lid": false,
                    "lid_state": null,
                    "substance": {
                        "name": "water",
                        "zh_name": "水",
                        "unit": "ml",
                        "amount": 10.0
                    }
                },
                "description": ""
            }
        },
        {
            "type": "pcc_left_chute",
            "id": "pcc_left_chute_001",
            "properties": {
                "state": "using",
                "description": "",
                "pulled_out_mm": 12,
                "pulled_out_rate": 0.02,
                "closed": false,
                "front_waste_bin": {
                    "content_state": "fill",
                    "has_lid": true,
                    "lid_state": "closed",
                    "substance": null
                },
                "back_waste_bin": {
                    "content_state": "fill",
                    "has_lid": true,
                    "lid_state": "closed",
                    "substance": null
                }
            }
        },
        {
            "type": "pcc_right_chute",
            "id": "pcc_right_chute_001",
            "properties": {
                "state": "using",
                "description": "",
                "pulled_out_mm": 0.464,
                "pulled_out_rate": 0.8,
                "closed": false,
                "front_waste_bin": {
                    "content_state": "fill",
                    "has_lid": true,
                    "lid_state": "closed",
                    "substance": null
                },
                "back_waste_bin": {
                    "content_state": "fill",
                    "has_lid": true,
                    "lid_state": "closed",
                    "substance": null
                }
            }
        }
    ]
}
```

> **Response notes:**
> - PCC chute properties now include `state` (`DeviceState`) and `description` fields per v0.3.
> - Waste bin fields are `ContainerState | null` objects (not plain strings like the PDF draft).
> - Round bottom flask `state` is a `ContainerState` structured object (per `RoundBottomFlaskProperties`).

---

## 7. start_evaporation

Mount flask on evaporator, configure vacuum pump and rotation, start evaporation process.

**Prerequisite:** Robot must be holding a round-bottom flask (`working` state with `moving_with_round_bottom_flask` description).

**Wire task_type:** `start_evaporation`

### Request

```json
{
    "task_id": "task-start-evaporation-001",
    "task_type": "start_evaporation",
    "params": {
        "work_station": "ws_bic_09_fh_002",
        "device_id": "re-buchi-r180_001",
        "device_type": "re-buchi-r180",
        "profiles": {
            "start": {
                "lower_height": 60.5,
                "rpm": 60,
                "target_temperature": 40,
                "target_pressure": 660
            },
            "updates": [
                {
                    "lower_height": 60.5,
                    "rpm": 60,
                    "target_temperature": 40,
                    "target_pressure": 240,
                    "trigger": {
                        "type": "time_from_start",
                        "time_in_sec": 600
                    }
                }
            ]
        }
    }
}
```

> **v0.3 changes from PDF draft:**
> - Removed `post_run_state` — handled by service layer.
> - Removed `stop` key from profiles — not in ground truth `EvaporationProfiles`.
> - Removed `reduce_bumping` key — not in ground truth `EvaporationProfiles`.
> - `EvaporationProfiles` has exactly two fields: `start` (required) + `updates` (list, default `[]`).
> - Each `EvaporationProfile` in `updates` requires all physical fields (`lower_height`, `rpm`, `target_temperature`, `target_pressure`) plus optional `trigger`.

### Example Response

```json
{
    "code": 200,
    "task_id": "task-start-evaporation-001",
    "msg": "success",
    "updates": [
        {
            "type": "robot",
            "id": "talos.001",
            "properties": {
                "location": "ws_bic_09_fh_002",
                "state": "working",
                "description": "observe_evaporation"
            }
        },
        {
            "type": "round_bottom_flask",
            "id": "rbf_001",
            "properties": {
                "location": "ws_bic_09_fh_002",
                "state": {
                    "content_state": "fill",
                    "has_lid": false,
                    "lid_state": null,
                    "substance": null
                },
                "description": "evaporating"
            }
        },
        {
            "type": "evaporator",
            "id": "re-buchi-r180_001",
            "properties": {
                "state": "using",
                "description": "",
                "lower_height": 60.5,
                "rpm": 60,
                "target_temperature": 40,
                "current_temperature": 36,
                "target_pressure": 660,
                "current_pressure": 659
            }
        }
    ]
}
```

> **Response notes:**
> - Evaporator uses `state: DeviceState` (not `running: bool`). Changed in v0.3.
> - Evaporator `id` uses ground truth device_id `re-buchi-r180_001`.
> - Round bottom flask `state` is a `ContainerState` object; supplementary info goes into `description`.

---

## Appendix: Entity Update Type Reference

All responses use `EntityUpdate` discriminated union. Possible `type` values:

| Type                            | Properties Model             | State Enum        | Description                              |
| ------------------------------- | ---------------------------- | ----------------- | ---------------------------------------- |
| `robot`                         | `RobotProperties`            | `RobotState`      | Robot location & state                   |
| `silica_cartridge`              | `CartridgeProperties`        | `ConsumableState` | Silica cartridge location/state          |
| `sample_cartridge`              | `CartridgeProperties`        | `ConsumableState` | Sample cartridge location/state          |
| `tube_rack`                     | `TubeRackProperties`         | `ToolState`       | Tube rack location/state                 |
| `round_bottom_flask`            | `RoundBottomFlaskProperties` | `ContainerState`  | Flask location/state (structured object) |
| `ccs_ext_module`                | `CCSExtModuleProperties`     | `DeviceState`     | CC external module state                 |
| `column_chromatography_machine` | `CCMachineProperties`        | `DeviceState`     | CC machine state + experiment params     |
| `isco_combiflash_nextgen_300`   | `CCMachineProperties`        | `DeviceState`     | Alias for CC machine (device-specific)   |
| `evaporator`                    | `EvaporatorProperties`       | `DeviceState`     | Evaporator state + running params        |
| `pcc_left_chute`                | `PCCChuteProperties`         | `DeviceState`     | Left PCC chute state                     |
| `pcc_right_chute`               | `PCCChuteProperties`         | `DeviceState`     | Right PCC chute state                    |

### State Enum Quick Reference

| Enum              | Values                                                             | Used By                                        |
| ----------------- | ------------------------------------------------------------------ | ---------------------------------------------- |
| `RobotState`      | `idle`, `working`, `charging`, `disconnected`                      | Robot                                          |
| `DeviceState`     | `idle`, `using`, `unavailable`                                     | CC machine, evaporator, ext module, PCC chutes |
| `ConsumableState` | `unused`, `inuse`, `used`                                          | Silica & sample cartridges                     |
| `ToolState`       | `available`, `inuse`, `contaminated`                               | Tube rack                                      |
| `ContainerState`  | (structured: `content_state`, `has_lid`, `lid_state`, `substance`) | Round bottom flask, PCC waste bins             |

## Appendix: Full CC Workflow Sequence

A typical column chromatography + evaporation workflow:

```
1. setup_cartridges (setup_tubes_to_column_machine) → Mount silica & sample cartridges
2. setup_tube_rack                                   → Mount tube rack
3. start_column_chromatography                       → Configure & start CC
4. take_photo                                        → Periodic monitoring during CC run
5. terminate_column_chromatography                   → Stop CC, air purge, capture results
6. collect_column_chromatography_fractions            → Collect fractions into flask
7. start_evaporation                                 → Mount flask & start evaporation
```

## Appendix: TODO Skills (Not Yet Implemented)

| Skill               | Description                            |
| ------------------- | -------------------------------------- |
| `stop_evaporation`  | Stop evaporation, remove flask         |
| `setup_ccs_bins`    | Mount waste bins at CC fume hood       |
| `return_ccs_bins`   | Return used bins to waste area         |
| `return_cartridges` | Disassemble and return used cartridges |
| `return_tube_rack`  | Return used tube rack to waste area    |
