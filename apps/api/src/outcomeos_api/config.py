import base64
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
    ingress_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "outcomeos-evidence"
    s3_access_key_id: str = "outcomeos"
    s3_secret_access_key: str = "outcomeos-local-only"
    s3_max_object_bytes: int = 10_000_000
    s3_require_tls: bool = True
    integration_keyring: str | None = None
    integration_active_key_id: str | None = None
    integration_secret_overlap_seconds: int = 300
    integration_secret_lifetime_seconds: int = 2_592_000
    integration_endpoint_token_bytes: int = 32
    webhook_max_body_bytes: int = 1_000_000
    webhook_replay_window_seconds: int = 300
    ingestion_job_kind: str = "ingest.canonical_event.v1"
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
        if (
            self.s3_max_object_bytes < 1
            or self.webhook_max_body_bytes < 1
            or self.webhook_replay_window_seconds < 1
            or self.integration_secret_lifetime_seconds < 1
            or self.integration_secret_overlap_seconds < 0
            or self.integration_secret_overlap_seconds >= self.integration_secret_lifetime_seconds
            or self.integration_endpoint_token_bytes < 32
            or not self.ingestion_job_kind
        ):
            raise ValueError("storage limit must be positive and secret overlap cannot be negative")
        if self.app_env in {"staging", "production"} and (
            not self.integration_keyring
            or not self.integration_active_key_id
            or self.s3_access_key_id == "outcomeos"
            or self.s3_secret_access_key == "outcomeos-local-only"  # pragma: allowlist secret
            or (self.s3_require_tls and not self.s3_endpoint_url.startswith("https://"))
        ):
            raise ValueError(
                "managed integration key material, non-default S3 credentials, and TLS storage "
                "are required in staging and production"
            )
        return self

    def parsed_integration_keyring(self) -> dict[str, bytes]:
        """Parse ``key-id:base64-key`` entries and reject ambiguous or weak key material."""
        if not self.integration_keyring or not self.integration_active_key_id:
            raise ValueError("integration keyring is not configured")
        keys: dict[str, bytes] = {}
        try:
            for entry in self.integration_keyring.split(","):
                key_id, encoded = entry.split(":", 1)
                if not key_id or key_id in keys:
                    raise ValueError
                key = base64.b64decode(encoded, validate=True)
                if len(key) != 32:
                    raise ValueError
                keys[key_id] = key
        except (ValueError, TypeError) as error:
            raise ValueError("invalid integration keyring") from error
        if self.integration_active_key_id not in keys:
            raise ValueError("active integration key is unavailable")
        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()
