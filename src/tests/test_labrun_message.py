#!/usr/bin/env python3
"""
Test script to simulate LabRun sending a setup_cartridges command.
This helps debug the parameter validation issue.
"""

import asyncio
import json

import aio_pika
from loguru import logger


async def send_test_message():
    """Send a test message mimicking LabRun's format."""

    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(
        host="localhost",
        port=5672,
        login="guest",
        password="guest",
    )

    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            "bic_exchange",
            type=aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        # Test message (matching your input params)
        message_data = {
            "task_id": "90af1d88-139b-4b6f-881d-4c9d8a68e9a7",
            "task_type": "setup_tubes_to_column_machine",
            "params": {
                "work_station": "00000000-0000-4000-a000-000000000010",
                "sample_cartridge_id": "00000000-0000-4000-a000-000000000070",
                "sample_cartridge_location": "bic_09B_l3_001",
                "sample_cartridge_type": "ilok_40g",
                "silica_cartridge_type": "sepaflash_40g",
            },
        }

        # Convert to JSON
        message_body = json.dumps(message_data).encode()

        logger.info("Sending test message to talos_001.cmd")
        logger.info("Message data: {}", json.dumps(message_data, indent=2))

        # Publish to the command queue
        message = aio_pika.Message(
            body=message_body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await exchange.publish(
            message,
            routing_key="talos_001.cmd",
        )

        logger.success("Message sent successfully!")

        # Wait a bit for the consumer to process it
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(send_test_message())
