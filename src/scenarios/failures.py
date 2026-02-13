"""Task-specific failure messages for mock scenarios."""

from __future__ import annotations

import random

from src.schemas.commands import TaskType

# Realistic failure messages per task type
FAILURE_MESSAGES: dict[TaskType, list[str]] = {
    TaskType.SETUP_CARTRIDGES: [
        "Gripper malfunction during cartridge pickup",
        "Cartridge not detected at expected storage position",
        "Silica cartridge alignment failure at work station mount point",
        "Sample cartridge barcode scan failed - cartridge may be misplaced",
    ],
    TaskType.SETUP_TUBE_RACK: [
        "Tube rack not detected at storage location",
        "Gripper force sensor exceeded safe threshold during rack pickup",
        "Tube rack alignment failure at work station",
    ],
    TaskType.TAKE_PHOTO: [
        "Camera focus failure - image quality below threshold",
        "Navigation to photo position failed - path obstructed",
        "Device screen not detected at expected position",
    ],
    TaskType.START_CC: [
        "Column chromatography system not responding to start command",
        "Pressure sensor reading abnormal before start - safety check failed",
        "Solvent level insufficient for configured run duration",
        "System equilibration timeout exceeded",
    ],
    TaskType.TERMINATE_CC: [
        "CC system did not acknowledge terminate command within timeout",
        "Emergency stop triggered during termination sequence",
        "Result screen capture failed during termination",
    ],
    TaskType.COLLECT_CC_FRACTIONS: [
        "Round bottom flask not detected at consolidation station",
        "Tube extraction failure at position - tube may be stuck",
        "Flask overflow sensor triggered during consolidation",
    ],
    TaskType.START_EVAPORATION: [
        "Evaporator vacuum pump failed to reach target pressure",
        "Water bath temperature sensor malfunction",
        "Flask rotation motor stalled during ramp-up",
        "Safety interlock triggered - evaporator lid not properly sealed",
    ],
}

# Error codes: 1010-1099 range for task-specific failures
_ERROR_CODE_BASE: dict[TaskType, int] = {
    TaskType.SETUP_CARTRIDGES: 1010,
    TaskType.SETUP_TUBE_RACK: 1020,
    TaskType.TAKE_PHOTO: 1040,
    TaskType.START_CC: 1050,
    TaskType.TERMINATE_CC: 1060,
    TaskType.COLLECT_CC_FRACTIONS: 1070,
    TaskType.START_EVAPORATION: 1080,
}


def get_random_failure(task_type: TaskType) -> tuple[int, str]:
    """Get a random failure code and message for the given task type.

    Returns:
        Tuple of (error_code, error_message).
    """
    messages = FAILURE_MESSAGES.get(task_type, ["Unknown task failure"])
    message = random.choice(messages)  # noqa: S311
    base_code = _ERROR_CODE_BASE.get(task_type, 1090)
    # Add small offset based on message index for variety
    code = base_code + random.randint(0, 9)  # noqa: S311
    return code, message
