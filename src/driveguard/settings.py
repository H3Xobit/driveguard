"""Runtime settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://dg:dg@localhost:35432/driveguard"
    mqtt_broker: str = "localhost"
    mqtt_port: int = 31883
    mqtt_topic: str = "driveguard/telemetry/#"
    dg_log_level: str = "INFO"
    dg_seed: int = 42
    dg_offline_llm: int = 1
    dg_mqtt_consumer: int = 0
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    risk_warn: float = 0.55
    risk_fault: float = 0.78
    window_size: int = 32
    service_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
