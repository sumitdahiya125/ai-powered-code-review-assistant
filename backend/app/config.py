from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Disable Pydantic's `model_` protected namespace so we can name the
        # ML-model settings naturally.
        protected_namespaces=(),
    )

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/codereview"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    log_level: str = "INFO"

    model_name: str = "microsoft/codebert-base"
    model_device: str = "cpu"
    model_max_tokens: int = 512

    cache_ttl_seconds: int = 3600
    max_code_bytes: int = 200_000

    allowed_origins: str = "http://localhost:5173"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
