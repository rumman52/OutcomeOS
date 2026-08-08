"""Framework-independent global value objects."""

from .money import Money, currency_exponent
from .regional import WorkspaceRegion

__all__ = ["Money", "WorkspaceRegion", "currency_exponent"]
