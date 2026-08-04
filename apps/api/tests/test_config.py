import pytest
from pydantic import ValidationError

from outcomeos_api.config import Settings


@pytest.mark.parametrize("flag", ["demo_auth_enabled", "mock_integrations_enabled"])
def test_demo_features_are_rejected_in_production(flag: str) -> None:
    with pytest.raises(ValidationError, match="forbidden in production"):
        Settings(app_env="production", **{flag: True})  # type: ignore[arg-type]


def test_demo_features_can_be_used_locally() -> None:
    settings = Settings(app_env="development", demo_auth_enabled=True)
    assert settings.demo_auth_enabled is True
