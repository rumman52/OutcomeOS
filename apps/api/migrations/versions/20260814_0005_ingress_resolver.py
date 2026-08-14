"""Expose only the material required to authenticate public ingress.

Revision ID: 20260814_0005
Revises: 20260814_0004
"""

from alembic import op

revision = "20260814_0005"
down_revision = "20260814_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP FUNCTION public.resolve_integration_endpoint(bytea)")
    op.execute(
        """
        CREATE FUNCTION public.resolve_integration_endpoint(token_digest bytea)
        RETURNS TABLE (
          tenant_id uuid, endpoint_id uuid, provider varchar,
          version integer, key_id varchar, nonce bytea, ciphertext bytea,
          not_before timestamptz, expires_at timestamptz
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT e.tenant_id, e.id, e.provider, s.version, s.key_id, s.nonce,
                 s.ciphertext, s.not_before, s.expires_at
          FROM public.integration_endpoints e
          JOIN public.integration_secret_versions s
            ON s.tenant_id=e.tenant_id AND s.endpoint_id=e.id
          WHERE e.public_token_digest=token_digest AND e.status='active'
            AND e.revoked_at IS NULL AND s.retired_at IS NULL
            AND s.not_before <= now() AND s.expires_at > now()
          ORDER BY s.version DESC
          LIMIT 2
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.resolve_integration_endpoint(bytea) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.resolve_integration_endpoint(bytea) TO outcomeos_ingress"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION public.resolve_integration_endpoint(bytea)")
    op.execute(
        """
        CREATE FUNCTION public.resolve_integration_endpoint(token_digest bytea)
        RETURNS TABLE (tenant_id uuid, endpoint_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
          SELECT e.tenant_id, e.id FROM public.integration_endpoints e
          WHERE e.public_token_digest=token_digest AND e.status='active'
            AND e.revoked_at IS NULL
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.resolve_integration_endpoint(bytea) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.resolve_integration_endpoint(bytea) TO outcomeos_ingress"
    )
