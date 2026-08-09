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
    persistence_backend: Literal["postgresql", "json_sandbox"] = "postgresql"
    database_url: str = "postgresql+psycopg://outcomeos:outcomeos@localhost:5432/outcomeos"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "outcomeos-evidence"
    s3_access_key_id: str = "outcomeos"
    s3_secret_access_key: str = "outcomeos-local-only"
    ai_provider: str = "deterministic_sandbox"
    ai_model: str = "deterministic-sandbox-v1"
    ai_api_key: str | None = None
    webhook_sandbox_secret: str = "change-me-local-webhook-secret"
    frontend_origin: str = "http://localhost:3000"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_discovery_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_url: str | None = None
    session_secret: str = "change-me-local-session-secret"
    api_key_pepper: str = "change-me-local-api-key-pepper"

    @model_validator(mode="after")
    def reject_production_demo_features(self) -> "Settings":
        if self.app_env in {"staging", "production"} and (
            self.demo_auth_enabled
            or self.mock_integrations_enabled
            or self.persistence_backend == "json_sandbox"
            or self.ai_provider == "deterministic_sandbox"
            or self.webhook_sandbox_secret.startswith("change-me")
            or self.session_secret.startswith("change-me")
            or self.api_key_pepper.startswith("change-me")
        ):
            raise ValueError(
                "Sandbox persistence, demo authentication, mock integrations, deterministic AI, "
                "and default secrets are forbidden in staging and production"
            )
        if self.app_env in {"staging", "production"} and not (
            self.oidc_issuer
            and self.oidc_audience
            and (self.oidc_jwks_url or self.oidc_discovery_url)
        ):
            raise ValueError("OIDC issuer, audience, and JWKS or discovery are required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
