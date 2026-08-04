from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration; unsafe demo features fail closed."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    demo_auth_enabled: bool = False
    mock_integrations_enabled: bool = False

    @model_validator(mode="after")
    def reject_production_demo_features(self) -> "Settings":
        if self.app_env == "production" and (
            self.demo_auth_enabled or self.mock_integrations_enabled
        ):
            raise ValueError(
                "Demo authentication and mock integrations are forbidden in production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
