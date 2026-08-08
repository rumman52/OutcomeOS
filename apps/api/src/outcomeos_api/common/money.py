from __future__ import annotations

from dataclasses import dataclass

from outcomeos_api.domain import DomainError

# ISO 4217 exceptions to the usual two fractional digits. This deliberately
# contains supported settlement currencies rather than guessing from /100.
_EXPONENTS = {"BHD": 3, "JPY": 0, "KWD": 3, "OMR": 3, "TND": 3}


def currency_exponent(currency: str) -> int:
    normalized = currency.upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise DomainError("currency must be an ISO 4217 alpha-3 code")
    return _EXPONENTS.get(normalized, 2)


@dataclass(frozen=True, slots=True)
class Money:
    """An exact amount in ISO 4217 minor units."""

    minor_units: int
    currency: str

    def __post_init__(self) -> None:
        normalized = self.currency.upper()
        currency_exponent(normalized)
        object.__setattr__(self, "currency", normalized)

    def add(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise DomainError("cannot combine different currencies")
        return Money(self.minor_units + other.minor_units, self.currency)

    def decimal_string(self) -> str:
        exponent = currency_exponent(self.currency)
        if exponent == 0:
            return str(self.minor_units)
        sign = "-" if self.minor_units < 0 else ""
        digits = str(abs(self.minor_units)).zfill(exponent + 1)
        return f"{sign}{digits[:-exponent]}.{digits[-exponent:]}"
