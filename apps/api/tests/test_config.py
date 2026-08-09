import pytest
from pydantic import ValidationError

from outcomeos_api.config import Settings


@pytest.mark.parametrize("flag", ["demo_auth_enabled", "mock_integrations_enabled"])
def test_demo_features_are_rejected_in_production(flag: str) -> None:
    with pytest.raises(ValidationError, match="forbidden in staging and production"):
        Settings(app_env="production", **{flag: True})  # type: ignore[arg-type]


def test_demo_features_can_be_used_locally() -> None:
    settings = Settings(app_env="development", demo_auth_enabled=True)
    assert settings.demo_auth_enabled is True


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("persistence_backend", "json_sandbox"),
        ("ai_provider", "deterministic_sandbox"),
        ("webhook_sandbox_secret", "change-me-default"),
        ("session_secret", "change-me-default"),
        ("api_key_pepper", "change-me-default"),
    ],
)
def test_non_sandbox_environments_fail_closed(environment: str, name: str, value: str) -> None:
    safe = {
        "app_env": environment,
        "ai_provider": "not_configured",
        "webhook_sandbox_secret": "secure-webhook-value",
        "session_secret": "secure-session-value",
        "api_key_pepper": "secure-api-key-pepper",
        "oidc_issuer": "https://identity.example",
        "oidc_audience": "outcomeos-api",
        "oidc_jwks_url": "https://identity.example/.well-known/jwks.json",
    }
    safe[name] = value
    with pytest.raises(ValidationError):
        Settings(**safe)  # type: ignore[arg-type]
