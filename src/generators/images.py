"""Image URL and CapturedImage generation for mock results.

Generates deterministic mock image URLs with timestamps for device screen captures.
"""

from __future__ import annotations

from src.generators.entity_updates import generate_robot_timestamp
from src.schemas.results import CapturedImage


def generate_image_url(base_url: str, work_station: str, device_id: str, component: str) -> str:
    """Generate a mock image URL with timestamp in spec format."""
    timestamp = generate_robot_timestamp()
    return f"{base_url}/{work_station}/{device_id}/{component}/{timestamp}.jpg"


def generate_captured_images(
    base_url: str,
    work_station: str,
    device_id: str,
    device_type: str,
    components: list[str] | str,
) -> list[CapturedImage]:
    """Generate CapturedImage list for one or multiple components."""
    if isinstance(components, str):
        components = [components]
    return [
        CapturedImage(
            work_station=work_station,
            device_id=device_id,
            device_type=device_type,
            component=component,
            url=generate_image_url(base_url, work_station, device_id, component),
            create_time=generate_robot_timestamp(),
        )
        for component in components
    ]
