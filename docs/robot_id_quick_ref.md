# robot_id Quick Reference

## ✅ DO: Use robot_id for Routing

```python
# Mock Server Configuration
MOCK_ROBOT_ID=talos_001

# Consumer: Listen to commands
queue.bind(exchange, routing_key="talos_001.cmd")

# Producer: Publish results
exchange.publish(message, routing_key="talos_001.result")
```

## ❌ DON'T: Include robot_id in Task Parameters

```json
// ❌ WRONG: robot_id in params
{
  "task_name": "setup_tubes_to_column_machine",
  "params": {
    "work_station_id": "ws-001",
    "robot_id": "talos_001"  // ❌ Don't do this!
  }
}

// ✅ CORRECT: robot_id only in routing key
{
  "task_name": "setup_tubes_to_column_machine",
  "params": {
    "work_station_id": "ws-001"
    // ✅ No robot_id here
  }
}
// Published with routing_key="talos_001.cmd"
```

## Exception: Heartbeat Messages

```json
// ✅ Heartbeat DOES include robot_id in message body
{
  "robot_id": "talos_001",  // ✅ Needed because LabRun binds to #.hb
  "timestamp": "2025-02-06T12:34:56Z",
  "state": "idle"
}
// Published with routing_key="talos_001.hb"
```

## Why?

- **Routing Key** = Transport layer (WHERE to send)
- **Task Params** = Application layer (WHAT to do)
- **robot_id** is routing context, not task data

See [ROBOT_ID_DESIGN.md](../ROBOT_ID_DESIGN.md) for full explanation.
