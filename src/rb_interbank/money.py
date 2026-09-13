from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN


def dollars_to_cents(amount: str | int | Decimal) -> int:
    if isinstance(amount, int):
        return amount
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return int(value * 100)


def cents_to_dollars(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"
