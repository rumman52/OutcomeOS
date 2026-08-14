"""Add the least-privilege public ingress endpoint resolver.

Revision ID: 20260814_0004
Revises: 20260814_0003
"""

from alembic import op

revision = "20260814_0004"
down_revision = "20260814_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE ROLE outcomeos_ingress NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
    )
    op.execute(
        """
        CREATE FUNCTION public.resolve_integration_endpoint(token_digest bytea)
        RETURNS TABLE (tenant_id uuid, endpoint_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT e.tenant_id, e.id
          FROM public.integration_endpoints AS e
          WHERE e.public_token_digest = token_digest
            AND e.status = 'active' AND e.revoked_at IS NULL
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.resolve_integration_endpoint(bytea) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.resolve_integration_endpoint(bytea) TO outcomeos_ingress"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.resolve_integration_endpoint(bytea)")
    op.execute("DROP ROLE IF EXISTS outcomeos_ingress")
