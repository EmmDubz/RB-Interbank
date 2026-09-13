from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol


MatchReason = Literal["ticker", "alias", "minecraft", "discord", "name"]
AccountKind = Literal["PERSONAL", "BUSINESS", "SUBACCOUNT", "OTHER"]


@dataclass(frozen=True, slots=True)
class Payee:
    """One clickable destination returned from a network search."""

    bank: str
    account: str
    name: str
    account_type: AccountKind = "PERSONAL"
    display_account: str | None = None
    match_reason: MatchReason = "ticker"
    verified: bool = False

    def label(self) -> str:
        shown = self.display_account or self.account
        return f"{self.bank}:{shown} — {self.name}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["display_account"] = self.display_account or strip_bank_prefix(
            self.bank, self.account
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Payee:
        return cls(
            bank=str(data["bank"]).upper(),
            account=str(data["account"]),
            name=str(data.get("name") or data["account"]),
            account_type=data.get("account_type") or "PERSONAL",
            display_account=data.get("display_account"),
            match_reason=data.get("match_reason") or "ticker",
            verified=bool(data.get("verified", False)),
        )


def strip_bank_prefix(bank: str, account: str) -> str:
    prefix = f"{bank}-"
    if account.upper().startswith(prefix.upper()) and len(account) > len(prefix):
        return account[len(prefix) :]
    return account


@dataclass(frozen=True, slots=True)
class Transfer:
    transfer_id: str
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount_cents: int
    memo: str = ""
    dc_txn_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transfer:
        return cls(
            transfer_id=str(data["transfer_id"]),
            from_bank=str(data["from_bank"]).upper(),
            from_account=str(data["from_account"]),
            to_bank=str(data["to_bank"]).upper(),
            to_account=str(data["to_account"]),
            amount_cents=int(data["amount_cents"]),
            memo=str(data.get("memo") or ""),
            dc_txn_id=data.get("dc_txn_id"),
            extra=dict(data.get("extra") or {}),
        )


class LookupHook(Protocol):
    async def __call__(self, query: str) -> list[Payee]: ...


class DebitHook(Protocol):
    async def __call__(self, transfer: Transfer) -> None: ...


class CreditHook(Protocol):
    async def __call__(self, transfer: Transfer) -> None: ...


class DcSender(Protocol):
    """Thin wrap around a bank's existing DemocracyCraft Economy client."""

    async def pay_firm(self, to_firm: str, amount_cents: int, memo: str) -> str:
        """Send RMD from this bank's firm to another firm. Return the DC txn id."""
        ...
