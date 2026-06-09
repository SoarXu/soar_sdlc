from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "SOAR SDLC API"
    app_env: str = "local"
    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = 1440
    database_url: str = "mysql+pymysql://root:root123@localhost:3306/intellective_bio_sdlc?charset=utf8mb4"
    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.backend_cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
