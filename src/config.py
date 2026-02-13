"""Mock Robot Server configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class MockSettings(BaseSettings):
    """Mock Robot Server configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MOCK_",
        env_file=".env",
        case_sensitive=False,
    )

    # RabbitMQ connection
    mq_host: str = "localhost"
    mq_port: int = 5672
    mq_user: str = "guest"
    mq_password: str = "guest"  # noqa: S105
    mq_vhost: str = "/"
    mq_connection_timeout: int = 30
    mq_heartbeat: int = 60
    mq_prefetch_count: int = 5

    # MQ topology — single exchange, per-robot routing keys
    mq_exchange: str = "robot.exchange"

    # Timing
    base_delay_multiplier: float = 0.1
    min_delay_seconds: float = 0.5

    # Scenarios
    default_scenario: str = "success"
    failure_rate: float = 0.0
    timeout_rate: float = 0.0

    # Images
    image_base_url: str = "http://minio:9000/bic-robot/captures"

    # Server
    server_name: str = "mock-robot-server"
    robot_id: str = "talos.001"
    log_level: str = "INFO"

    # Long-running task intervals (seconds at 1.0x)
    cc_intermediate_interval: float = 300.0
    re_intermediate_interval: float = 300.0

    # Heartbeat
    heartbeat_interval: float = 2.0  # seconds between heartbeats
