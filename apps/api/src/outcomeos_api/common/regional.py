from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from outcomeos_api.domain import DomainError


@dataclass(frozen=True, slots=True)
class WorkspaceRegion:
    country: str
    locale: str
    timezone: str
    default_currency: str

    def __post_init__(self) -> None:
        country = self.country.upper()
        currency = self.default_currency.upper()
        if len(country) != 2 or not country.isalpha():
            raise DomainError("country must be ISO 3166-1 alpha-2")
        if not self.locale or "_" in self.locale:
            raise DomainError("locale must be a BCP 47 language tag")
        if len(currency) != 3 or not currency.isalpha():
            raise DomainError("default currency must be ISO 4217 alpha-3")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise DomainError("timezone must be an IANA timezone") from exc
        object.__setattr__(self, "country", country)
        object.__setattr__(self, "default_currency", currency)
