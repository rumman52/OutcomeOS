import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.getenv("INTEGRATION_DATABASE_URL")
    if not url:
        pytest.fail(
            "INTEGRATION_DATABASE_URL is required for the PostgreSQL integration suite",
            pytrace=False,
        )
    return url


@pytest.fixture(scope="module")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


def test_migration_head_and_restricted_role_enforce_rls_and_composite_fk(
    migrated_engine: Engine,
) -> None:
    tenant_a, tenant_b = uuid4(), uuid4()
    contact_b = uuid4()
    role = f"outcomeos_app_{uuid4().hex[:10]}"
    with migrated_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260815_0008"
        connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
        connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
        connection.execute(
            text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"')
        )
        connection.execute(
            text(
                "INSERT INTO tenants (id, created_at, name) "
                "VALUES (:a, now(), 'A'), (:b, now(), 'B')"
            ),
            {"a": tenant_a, "b": tenant_b},
        )
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant_b)}
        )
        connection.execute(
            text(
                "INSERT INTO contacts "
                "(id, created_at, tenant_id, provider, external_id, display_name) "
                "VALUES (:id, now(), :tenant, 'fixture', 'b-contact', 'private')"
            ),
            {"id": contact_b, "tenant": tenant_b},
        )

    try:
        with migrated_engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text(f'SET LOCAL ROLE "{role}"'))
            # With no tenant setting, RLS fails closed.
            assert connection.scalar(text("SELECT count(*) FROM contacts")) == 0
            connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant_a)}
            )
            assert connection.scalar(text("SELECT count(*) FROM contacts")) == 0
            with pytest.raises((DBAPIError, IntegrityError)):
                connection.execute(
                    text(
                        "INSERT INTO orders "
                        "(id, created_at, tenant_id, provider, external_id, amount_minor, "
                        "currency, contact_id, status) VALUES "
                        "(:id, now(), :tenant_a, 'fixture', 'cross', 100, 'USD', "
                        ":contact_b, 'created')"
                    ),
                    {"id": uuid4(), "tenant_a": tenant_a, "contact_b": contact_b},
                )
            transaction.rollback()

        with migrated_engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text(f'SET LOCAL ROLE "{role}"'))
            connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant_b)}
            )
            assert connection.scalar(text("SELECT count(*) FROM contacts")) == 1
            transaction.rollback()
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(text(f'DROP OWNED BY "{role}"'))
            connection.execute(text(f'DROP ROLE IF EXISTS "{role}"'))


def test_tenant_id_is_immutable(migrated_engine: Engine) -> None:
    tenant_a, tenant_b, contact = uuid4(), uuid4(), uuid4()
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text(
                "INSERT INTO tenants (id, created_at, name) "
                "VALUES (:a, now(), 'A2'), (:b, now(), 'B2')"
            ),
            {"a": tenant_a, "b": tenant_b},
        )
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant_a)}
        )
        connection.execute(
            text(
                "INSERT INTO contacts "
                "(id, created_at, tenant_id, provider, external_id, display_name) "
                "VALUES (:id, now(), :tenant, 'fixture', 'immutable', 'private')"
            ),
            {"id": contact, "tenant": tenant_a},
        )
        with pytest.raises(DBAPIError, match="tenant_id is immutable"):
            connection.execute(
                text("UPDATE contacts SET tenant_id=:other WHERE id=:id"),
                {"other": tenant_b, "id": contact},
            )
        transaction.rollback()
