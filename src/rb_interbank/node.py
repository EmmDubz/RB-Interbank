from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiohttp import web

from rb_interbank.addressing import (
    display_account,
    normalize_bank,
    ticker_candidates,
)
from rb_interbank.hub import Hub, InMemoryHub
from rb_interbank.money import dollars_to_cents
from rb_interbank.signing import dumps, sign, verify
from rb_interbank.types import CreditHook, DcSender, DebitHook, LookupHook, Payee, Transfer


class InterbankNode:
    """
    Drop this on the bank bot. Implement three hooks. Mount one HTTP route.

    lookup  — given a search string, return matching local payees
    debit   — take money off the sending customer (idempotent on transfer_id)
    credit  — put money on the receiving customer (idempotent on transfer_id)
    """

    def __init__(
        self,
        bank: str,
        *,
        secret: str,
        hub: Hub | None = None,
        ticker_prefix: str | None = None,
        firm_name: str | None = None,
        dc_sender: DcSender | None = None,
    ) -> None:
        self.bank = normalize_bank(bank)
        self.secret = secret
        self.hub = hub
        self.ticker_prefix = ticker_prefix if ticker_prefix is not None else f"{self.bank}-"
        self.firm_name = firm_name or self.bank
        self.dc_sender = dc_sender
        self._lookup: LookupHook | None = None
        self._debit: DebitHook | None = None
        self._credit: CreditHook | None = None
        self._seen_debits: set[str] = set()
        self._seen_credits: set[str] = set()
        if isinstance(hub, InMemoryHub):
            hub.attach(self)

    def on_lookup(self, fn: LookupHook) -> LookupHook:
        self._lookup = fn
        return fn

    def on_debit(self, fn: DebitHook) -> DebitHook:
        self._debit = fn
        return fn

    def on_credit(self, fn: CreditHook) -> CreditHook:
        self._credit = fn
        return fn

    def annotate(self, payee: Payee) -> Payee:
        return Payee(
            bank=self.bank,
            account=payee.account,
            name=payee.name,
            account_type=payee.account_type,
            display_account=payee.display_account
            or display_account(self.bank, payee.account, self.ticker_prefix),
            match_reason=payee.match_reason,
            verified=payee.verified,
        )

    def local_refs(self, query: str) -> list[str]:
        return ticker_candidates(self.bank, query, self.ticker_prefix)

    async def lookup(self, query: str) -> list[Payee]:
        if self._lookup is None:
            raise RuntimeError("Implement @node.on_lookup")
        return [self.annotate(payee) for payee in await self._lookup(query)]

    async def find(self, query: str, bank: str | None = None) -> list[Payee]:
        """Search this bank, or every member bank via the hub."""
        if self.hub is None or (bank and normalize_bank(bank) == self.bank):
            return await self.lookup(query)
        return await self.hub.lookup(query, bank)

    async def debit(self, transfer: Transfer) -> None:
        if self._debit is None:
            raise RuntimeError("Implement @node.on_debit")
        if transfer.transfer_id in self._seen_debits:
            return
        await self._debit(transfer)
        self._seen_debits.add(transfer.transfer_id)

    async def credit(self, transfer: Transfer) -> None:
        if self._credit is None:
            raise RuntimeError("Implement @node.on_credit")
        if transfer.transfer_id in self._seen_credits:
            return
        await self._credit(transfer)
        self._seen_credits.add(transfer.transfer_id)

    async def send(
        self,
        *,
        from_account: str,
        payee: Payee,
        amount: str | int,
        memo: str = "",
    ) -> Transfer:
        if self.hub is None:
            raise RuntimeError("A hub is required to send")
        amount_cents = dollars_to_cents(amount)
        draft = Transfer(
            transfer_id="",
            from_bank=self.bank,
            from_account=from_account,
            to_bank=payee.bank,
            to_account=payee.account,
            amount_cents=amount_cents,
            memo=memo,
        )
        transfer = await self.hub.register_transfer(draft)
        try:
            await self.debit(transfer)
        except Exception:
            raise
        dc_txn_id = transfer.transfer_id
        # Same-bank sends stay on the ledger. Do not pay your own firm.
        if self.dc_sender is not None and normalize_bank(payee.bank) != self.bank:
            dc_txn_id = await self.dc_sender.pay_firm(
                payee.bank, amount_cents, transfer.memo
            )
        return await self.hub.mark_cash_sent(transfer.transfer_id, str(dc_txn_id))

    def mount(self, app: web.Application, prefix: str = "/rb/v1") -> None:
        """Hub calls these. One line in the bank's existing aiohttp server."""
        app.router.add_post(f"{prefix}/lookup", self._handle_lookup)
        app.router.add_post(f"{prefix}/debit", self._handle_debit)
        app.router.add_post(f"{prefix}/credit", self._handle_credit)

    async def _signed_json(self, request: web.Request) -> dict:
        body = await request.read()
        header = request.headers.get("X-RB-Signature", "")
        if not verify(self.secret, body, header):
            raise web.HTTPUnauthorized(text="invalid signature")
        if not body:
            return {}
        import json

        return json.loads(body)

    def _signed_response(self, payload: dict) -> web.Response:
        body = dumps(payload)
        return web.Response(
            body=body,
            content_type="application/json",
            headers={"X-RB-Signature": sign(self.secret, body)},
        )

    async def _handle_lookup(self, request: web.Request) -> web.Response:
        data = await self._signed_json(request)
        payees = await self.lookup(str(data.get("query") or ""))
        return self._signed_response({"payees": [p.to_dict() for p in payees]})

    async def _handle_debit(self, request: web.Request) -> web.Response:
        data = await self._signed_json(request)
        await self.debit(Transfer.from_dict(data["transfer"]))
        return self._signed_response({"ok": True})

    async def _handle_credit(self, request: web.Request) -> web.Response:
        data = await self._signed_json(request)
        await self.credit(Transfer.from_dict(data["transfer"]))
        return self._signed_response({"ok": True})


def pick_handler(
    payees: list[Payee],
) -> Callable[[str], Awaitable[Payee | None]]:
    """
    Helper for UIs: after find() returns several banks, the player clicks one.
    Pass the chosen 'DRB:MDBZ' (or index) back in.
    """

    async def pick(choice: str) -> Payee | None:
        choice = choice.strip()
        if choice.isdigit():
            index = int(choice)
            if 0 <= index < len(payees):
                return payees[index]
        wanted = choice.upper()
        for payee in payees:
            labels = {
                f"{payee.bank}:{payee.account}".upper(),
                f"{payee.bank}:{payee.display_account or payee.account}".upper(),
                payee.account.upper(),
                (payee.display_account or "").upper(),
            }
            if wanted in labels:
                return payee
        return None

    return pick
