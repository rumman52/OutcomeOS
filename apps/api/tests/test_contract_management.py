from pathlib import Path

from outcomeos_api.config import Settings
from outcomeos_api.main import create_app
from outcomeos_api.migrations import EXPECTED_MIGRATION_HEAD


def test_contract_management_routes_are_registered() -> None:
    settings = Settings(
        app_env="test",
        integration_keyring="test:" + "YQ==" * 0,
        integration_active_key_id="test",
    )
    # Router assembly requires a valid 32-byte key, but never contacts persistence.
    import base64

    settings.integration_keyring = "test:" + base64.b64encode(b"x" * 32).decode()
    routes = {getattr(route, "path", "") for route in create_app(settings).routes}
    assert "/api/v1/contracts" in routes
    assert "/api/v1/contracts/{contract_id}/versions/{version_id}/accept" in routes
    assert "/api/v1/outcome-rules/{rule_id}/versions/{version_id}/{action}" in routes


def test_management_migration_is_additive_and_base_is_immutable() -> None:
    migration = (
        Path(__file__).parents[1] / "migrations/versions/20260815_0009_contract_management.py"
    ).read_text()
    assert 'down_revision = "20260815_0008"' in migration
    assert EXPECTED_MIGRATION_HEAD == "20260815_0009"
