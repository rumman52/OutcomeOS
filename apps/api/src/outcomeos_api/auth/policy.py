from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    OPERATOR = "operator"
    MARKETER = "marketer"
    ANALYST = "analyst"
    FINANCE = "finance"
    DISPUTE_REVIEWER = "dispute_reviewer"
    EXTERNAL_PARTNER = "external_partner"
    READ_ONLY = "read_only"


class Permission(StrEnum):
    WORKSPACE_MANAGE = "workspace:manage"
    MEMBERSHIP_MANAGE = "membership:manage"
    API_KEY_MANAGE = "api_key:manage"
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    FINANCE_READ = "finance:read"
    FINANCE_WRITE = "finance:write"
    DISPUTE_REVIEW = "dispute:review"


_POLICY: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMINISTRATOR: frozenset(Permission),
    Role.OPERATOR: frozenset({Permission.DATA_READ, Permission.DATA_WRITE}),
    Role.MARKETER: frozenset({Permission.DATA_READ, Permission.DATA_WRITE}),
    Role.ANALYST: frozenset({Permission.DATA_READ, Permission.FINANCE_READ}),
    Role.FINANCE: frozenset(
        {Permission.DATA_READ, Permission.FINANCE_READ, Permission.FINANCE_WRITE}
    ),
    Role.DISPUTE_REVIEWER: frozenset(
        {Permission.DATA_READ, Permission.FINANCE_READ, Permission.DISPUTE_REVIEW}
    ),
    Role.EXTERNAL_PARTNER: frozenset({Permission.DATA_READ}),
    Role.READ_ONLY: frozenset({Permission.DATA_READ}),
}


def authorize(role: Role, permission: Permission) -> bool:
    """Deny by default: only an explicitly mapped permission is authorized."""
    return permission in _POLICY.get(role, frozenset())
