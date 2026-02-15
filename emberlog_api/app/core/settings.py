from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    database_url: str
    log_level: str = "INFO"
    enable_file_logging: bool = False
    emberlog_api_key: str = ""
    emberlog_env: str = "prod"
    pool_min_size: int = 1
    pool_max_size: int = 5
    notifier_base_url: str = "http://localhost:8090"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        
    )


settings = Settings()  # type: ignore[call-arg]
