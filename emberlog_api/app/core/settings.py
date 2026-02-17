from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    database_url: str
    log_level: str = "INFO"
    enable_file_logging: bool = False
    pool_min_size: int = 1
    pool_max_size: int = 5
    notifier_base_url: str = "http://localhost:8090"
    mqtt_host: str = "mosquitto.pi-rack.com"
    mqtt_port: int = 1883
    mqtt_topic_prefix: str = "emberlog/trunkrecorder"
    mqtt_username: str | None = None
    mqtt_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        
    )


settings = Settings()  # type: ignore[call-arg]
