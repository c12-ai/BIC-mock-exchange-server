"""Timing calculation utilities for task simulation.

Provides randomized delays, duration calculations, and intermediate update intervals
used by task simulators to control pacing.
"""

from __future__ import annotations

import random


def calculate_delay(base_min: float, base_max: float, multiplier: float, min_delay: float = 0.5) -> float:
    """Calculate a randomized delay with multiplier and floor.

    Args:
        base_min: Minimum base delay in seconds.
        base_max: Maximum base delay in seconds.
        multiplier: Speed multiplier applied to the base delay.
        min_delay: Minimum returned delay (floor value).

    Returns:
        Computed delay in seconds, no less than min_delay.
    """
    base = random.uniform(base_min, base_max)  # noqa: S311
    return max(base * multiplier, min_delay)


def calculate_cc_duration(run_minutes: int, multiplier: float) -> float:
    """Calculate column chromatography simulation duration in seconds.

    Converts run_minutes to seconds and applies the speed multiplier.

    Args:
        run_minutes: Expected real-world run time in minutes.
        multiplier: Speed multiplier (e.g., 0.1 for 10x faster).

    Returns:
        Simulation duration in seconds.
    """
    return run_minutes * 60.0 * multiplier


def calculate_evaporation_duration(profiles: dict, multiplier: float) -> float:
    """Calculate evaporation duration from profiles updates or stop trigger.

    v0.3 ground truth uses ``profiles.updates`` list with trigger-based durations.
    Falls back to legacy ``profiles.stop.trigger`` and then 30-minute default.

    Args:
        profiles: Evaporation profiles dictionary.
        multiplier: Speed multiplier applied to the duration.

    Returns:
        Simulation duration in seconds.
    """
    # v0.3: Check updates list for time-based triggers
    updates = profiles.get("updates")
    if updates and isinstance(updates, list):
        for update in updates:
            if isinstance(update, dict):
                trigger = update.get("trigger")
                if trigger and isinstance(trigger, dict):
                    time_sec = trigger.get("time_in_sec")
                    if time_sec is not None:
                        return float(time_sec) * multiplier

    # Legacy: Check stop trigger
    stop = profiles.get("stop")
    if stop and isinstance(stop, dict):
        trigger = stop.get("trigger")
        if trigger and isinstance(trigger, dict):
            time_sec = trigger.get("time_in_sec")
            if time_sec is not None:
                return float(time_sec) * multiplier

    # Default: 30 minutes
    return 30.0 * 60.0 * multiplier


def calculate_intermediate_interval(total_duration: float, min_updates: int = 3) -> float:
    """Calculate interval between intermediate updates, ensuring at least min_updates.

    Divides the total duration evenly to produce min_updates intervals,
    with a minimum of 1 second between updates.

    Args:
        total_duration: Total simulation duration in seconds.
        min_updates: Minimum number of intermediate updates to produce.

    Returns:
        Interval in seconds between updates (at least 1.0).
    """
    if total_duration <= 0:
        return 1.0
    interval = total_duration / (min_updates + 1)
    return max(interval, 1.0)
