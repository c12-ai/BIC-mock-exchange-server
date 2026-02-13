"""Tests for WorldState class."""

from __future__ import annotations

from src.schemas.results import (
    CCSExtModuleUpdate,
    CCSystemUpdate,
    EvaporatorUpdate,
    PCCLeftChuteUpdate,
    RobotUpdate,
    SilicaCartridgeUpdate,
)
from src.state.world_state import WorldState


def test_world_state_starts_empty() -> None:
    """Verify WorldState initializes with no entities."""
    ws = WorldState()
    assert ws.get_entity("robot", "test-robot") is None
    assert not ws.has_entity("robot", "test-robot")
    assert ws.get_entities_by_type("robot") == {}


def test_apply_updates_stores_entities() -> None:
    """Verify apply_updates stores entity properties."""
    ws = WorldState()

    updates = [
        RobotUpdate(
            type="robot",
            id="robot-1",
            properties={"location": "ws-1", "state": "idle"},
        ),
        SilicaCartridgeUpdate(
            type="silica_cartridge",
            id="sc-1",
            properties={"location": "ws-1", "state": "mounted"},
        ),
    ]

    ws.apply_updates(updates)

    robot = ws.get_entity("robot", "robot-1")
    assert robot is not None
    assert robot["location"] == "ws-1"
    assert robot["state"] == "idle"

    cartridge = ws.get_entity("silica_cartridge", "sc-1")
    assert cartridge is not None
    assert cartridge["location"] == "ws-1"
    assert cartridge["state"] == "mounted"


def test_apply_updates_overwrites_existing_entity() -> None:
    """Verify that subsequent updates overwrite previous entity state."""
    ws = WorldState()

    # First update
    ws.apply_updates(
        [
            RobotUpdate(
                type="robot",
                id="robot-1",
                properties={"location": "ws-1", "state": "idle"},
            ),
        ]
    )

    # Second update overwrites
    ws.apply_updates(
        [
            RobotUpdate(
                type="robot",
                id="robot-1",
                properties={"location": "ws-2", "state": "idle"},
            ),
        ]
    )

    robot = ws.get_entity("robot", "robot-1")
    assert robot is not None
    assert robot["location"] == "ws-2"
    assert robot["state"] == "idle"


def test_has_entity() -> None:
    """Verify has_entity returns correct boolean."""
    ws = WorldState()

    assert not ws.has_entity("robot", "robot-1")

    ws.apply_updates(
        [
            RobotUpdate(
                type="robot",
                id="robot-1",
                properties={"location": "ws-1", "state": "idle"},
            ),
        ]
    )

    assert ws.has_entity("robot", "robot-1")
    assert not ws.has_entity("robot", "robot-2")


def test_get_entities_by_type() -> None:
    """Verify get_entities_by_type returns all matching entities."""
    ws = WorldState()

    updates = [
        RobotUpdate(type="robot", id="robot-1", properties={"location": "ws-1", "state": "idle"}),
        RobotUpdate(type="robot", id="robot-2", properties={"location": "ws-2", "state": "idle"}),
        SilicaCartridgeUpdate(type="silica_cartridge", id="sc-1", properties={"location": "ws-1", "state": "mounted"}),
    ]

    ws.apply_updates(updates)

    robots = ws.get_entities_by_type("robot")
    assert len(robots) == 2
    assert "robot-1" in robots
    assert "robot-2" in robots
    assert robots["robot-1"]["state"] == "idle"
    assert robots["robot-2"]["state"] == "idle"

    cartridges = ws.get_entities_by_type("silica_cartridge")
    assert len(cartridges) == 1
    assert "sc-1" in cartridges


def test_get_robot_state_convenience_method() -> None:
    """Verify get_robot_state is a convenience wrapper for get_entity."""
    ws = WorldState()

    assert ws.get_robot_state("robot-1") is None

    ws.apply_updates(
        [
            RobotUpdate(
                type="robot",
                id="robot-1",
                properties={"location": "ws-1", "state": "idle"},
            ),
        ]
    )

    robot = ws.get_robot_state("robot-1")
    assert robot is not None
    assert robot["location"] == "ws-1"
    assert robot["state"] == "idle"


def test_reset_clears_all_entities() -> None:
    """Verify reset clears all tracked entities."""
    ws = WorldState()

    updates = [
        RobotUpdate(type="robot", id="robot-1", properties={"location": "ws-1", "state": "idle"}),
        SilicaCartridgeUpdate(type="silica_cartridge", id="sc-1", properties={"location": "ws-1", "state": "mounted"}),
        CCSExtModuleUpdate(type="ccs_ext_module", id="ext-ws-1", properties={"state": "using"}),
    ]

    ws.apply_updates(updates)
    assert ws.has_entity("robot", "robot-1")
    assert ws.has_entity("silica_cartridge", "sc-1")
    assert ws.has_entity("ccs_ext_module", "ext-ws-1")

    ws.reset()

    assert not ws.has_entity("robot", "robot-1")
    assert not ws.has_entity("silica_cartridge", "sc-1")
    assert not ws.has_entity("ccs_ext_module", "ext-ws-1")
    assert ws.get_entities_by_type("robot") == {}


def test_apply_updates_with_complex_entities() -> None:
    """Verify complex entity types (evaporator, cc_system, chutes) are stored correctly."""
    ws = WorldState()

    updates = [
        EvaporatorUpdate(
            type="evaporator",
            id="evap-1",
            properties={
                "running": True,
                "lower_height": 50.0,
                "rpm": 120,
                "target_temperature": 60.0,
                "current_temperature": 45.0,
                "target_pressure": 100.0,
                "current_pressure": 500.0,
            },
        ),
        CCSystemUpdate(
            type="column_chromatography_machine",
            id="cc-1",
            properties={
                "state": "running",
                "experiment_params": {
                    "silicone_cartridge": "silica_40g",
                    "peak_gathering_mode": "all",
                    "air_clean_minutes": 5,
                    "run_minutes": 30,
                    "need_equilibration": True,
                },
                "start_timestamp": "2025-01-15T10:00:00Z",
            },
        ),
        PCCLeftChuteUpdate(
            type="pcc_left_chute",
            id="pcc-left-ws-1",
            properties={
                "pulled_out_mm": 100.0,
                "pulled_out_rate": 5.0,
                "closed": False,
                "front_waste_bin": {"content_state": "empty", "has_lid": False, "lid_state": None, "substance": None},
                "back_waste_bin": None,
            },
        ),
    ]

    ws.apply_updates(updates)

    evaporator = ws.get_entity("evaporator", "evap-1")
    assert evaporator is not None
    assert evaporator["state"] == "idle"
    assert evaporator["current_temperature"] == 45.0

    cc_system = ws.get_entity("column_chromatography_machine", "cc-1")
    assert cc_system is not None
    assert cc_system["state"] == "running"
    assert cc_system["experiment_params"]["run_minutes"] == 30

    chute = ws.get_entity("pcc_left_chute", "pcc-left-ws-1")
    assert chute is not None
    assert chute["front_waste_bin"] == {"content_state": "empty", "has_lid": False, "lid_state": None, "substance": None}
    assert chute["back_waste_bin"] is None


def test_world_state_thread_safety() -> None:
    """Verify WorldState can be accessed concurrently (basic smoke test)."""
    import threading

    ws = WorldState()

    def update_robot(robot_id: str) -> None:
        for i in range(10):
            ws.apply_updates(
                [
                    RobotUpdate(
                        type="robot",
                        id=robot_id,
                        properties={"location": f"ws-{i}", "state": "idle"},
                    ),
                ]
            )

    threads = [threading.Thread(target=update_robot, args=(f"robot-{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All robots should exist
    for i in range(5):
        assert ws.has_entity("robot", f"robot-{i}")
