from __future__ import annotations

import re

_SPACE = re.compile(r"[\s_]+")
_BANK_ACCOUNT = re.compile(
    r"^(?:(?P<bank>[A-Za-z]{2,8})[:/])?(?P<account>[A-Za-z0-9-]{1,24})$"
)


def normalize_bank(code: str) -> str:
    return (code or "").strip().upper()


def normalize_query(raw: str) -> str:
    return _SPACE.sub("", (raw or "").strip())


def parse_address(raw: str) -> tuple[str | None, str]:
    """
    Split 'DRB:MDBZ', 'DRB/MDBZ', 'DRB-MDBZ', or 'MDBZ'.

    The bank is only inferred from a colon/slash, never from a hyphen —
    DRB-MDBZ is a ticker, not bank DRB + account MDBZ, until the caller
    says the selected bank is DRB.
    """
    text = normalize_query(raw)
    if not text:
        return None, ""
    match = _BANK_ACCOUNT.match(text)
    if not match:
        return None, text
    bank = match.group("bank")
    account = match.group("account")
    return (normalize_bank(bank) if bank else None), account.upper()


def ticker_candidates(bank: str, account: str, prefix: str | None = None) -> list[str]:
    """
    DRB + MDBZ + prefix 'DRB-' → ['DRB-MDBZ', 'MDBZ']
    DRB + DRB-MDBZ             → ['DRB-MDBZ', 'MDBZ']
    VDRB + JDSV                → ['JDSV']
    """
    bank = normalize_bank(bank)
    account = normalize_query(account).upper()
    if not account:
        return []

    prefix = prefix if prefix is not None else f"{bank}-"
    out: list[str] = []

    def add(value: str) -> None:
        if value and value.upper() not in {item.upper() for item in out}:
            out.append(value)

    add(account)
    if prefix:
        if account.upper().startswith(prefix.upper()):
            add(account[len(prefix) :])
        else:
            add(f"{prefix}{account}")
    return out


def display_account(bank: str, canonical: str, prefix: str | None = None) -> str:
    bank = normalize_bank(bank)
    prefix = prefix if prefix is not None else f"{bank}-"
    if prefix and canonical.upper().startswith(prefix.upper()):
        return canonical[len(prefix) :]
    return canonical
