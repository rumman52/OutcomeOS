from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration; unsafe demo features fail closed."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "demo", "test", "staging", "production"] = "development"
    demo_auth_enabled: bool = False
    mock_integrations_enabled: bool = False
    database_url: str = "sqlite:///./outcomeos.db"
    demo_otp_expose: bool = False

    @model_validator(mode="after")
    def reject_production_demo_features(self) -> "Settings":
        if self.app_env == "production" and (
            self.demo_auth_enabled or self.mock_integrations_enabled or self.demo_otp_expose
        ):
            raise ValueError(
                "Demo authentication and mock integrations are forbidden in production"
            )
        return self

    @property
    def can_expose_otp(self) -> bool:
        return self.demo_otp_expose and self.app_env in {"development", "demo"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
