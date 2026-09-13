from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from rb_interbank.addressing import normalize_bank, parse_address
from rb_interbank.types import Payee, Transfer


class Hub(Protocol):
    async def lookup(self, query: str, bank: str | None = None) -> list[Payee]: ...

    async def register_transfer(self, transfer: Transfer) -> Transfer: ...

    async def mark_cash_sent(self, transfer_id: str, dc_txn_id: str) -> Transfer: ...

    async def mark_completed(self, transfer_id: str) -> Transfer: ...


class InMemoryHub:
    """
    Local hub for tests and a two-bank demo in one process.
    Production uses RemoteHub against the hosted RB service.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, object] = {}
        self._transfers: dict[str, Transfer] = {}

    def attach(self, node: object) -> None:
        bank = normalize_bank(getattr(node, "bank"))
        self._nodes[bank] = node

    async def lookup(self, query: str, bank: str | None = None) -> list[Payee]:
        parsed_bank, account = parse_address(query)
        target = normalize_bank(bank or parsed_bank or "")
        search = account or query
        banks = [target] if target else list(self._nodes)
        found: list[Payee] = []
        seen: set[tuple[str, str]] = set()
        for code in banks:
            node = self._nodes.get(code)
            if node is None:
                continue
            for payee in await node.lookup(search):
                key = (payee.bank, payee.account.upper())
                if key in seen:
                    continue
                seen.add(key)
                found.append(payee)
        return found

    async def register_transfer(self, transfer: Transfer) -> Transfer:
        transfer_id = transfer.transfer_id or f"rb_{uuid4().hex[:16]}"
        stored = Transfer(
            transfer_id=transfer_id,
            from_bank=transfer.from_bank,
            from_account=transfer.from_account,
            to_bank=transfer.to_bank,
            to_account=transfer.to_account,
            amount_cents=transfer.amount_cents,
            memo=transfer.memo or f"RB:{transfer_id}",
            dc_txn_id=transfer.dc_txn_id,
            extra=transfer.extra,
        )
        self._transfers[stored.transfer_id] = stored
        return stored

    async def mark_cash_sent(self, transfer_id: str, dc_txn_id: str) -> Transfer:
        current = self._transfers[transfer_id]
        updated = Transfer(
            transfer_id=current.transfer_id,
            from_bank=current.from_bank,
            from_account=current.from_account,
            to_bank=current.to_bank,
            to_account=current.to_account,
            amount_cents=current.amount_cents,
            memo=current.memo,
            dc_txn_id=dc_txn_id,
            extra=current.extra,
        )
        self._transfers[transfer_id] = updated
        dest = self._nodes.get(updated.to_bank)
        if dest is not None:
            await dest.credit(updated)
            return await self.mark_completed(transfer_id)
        return updated

    async def mark_completed(self, transfer_id: str) -> Transfer:
        return self._transfers[transfer_id]


class PeerHub(InMemoryHub):
    """Hosted hub: fan-out lookup/credit to each bank's /rb/v1 routes."""

    def __init__(self, peers: list[dict[str, str]]) -> None:
        super().__init__()
        self.peers = {normalize_bank(p["bank"]): p for p in peers}

    async def lookup(self, query: str, bank: str | None = None) -> list[Payee]:
        parsed_bank, account = parse_address(query)
        target = normalize_bank(bank or parsed_bank or "")
        search = account or query
        codes = [target] if target and target in self.peers else list(self.peers)
        found: list[Payee] = []
        seen: set[tuple[str, str]] = set()
        for code in codes:
            for payee in await self._call_bank(code, "/lookup", {"query": search}):
                key = (payee.bank, payee.account.upper())
                if key in seen:
                    continue
                seen.add(key)
                found.append(payee)
        return found

    async def mark_cash_sent(self, transfer_id: str, dc_txn_id: str) -> Transfer:
        updated = await super().mark_cash_sent(transfer_id, dc_txn_id)
        await self._call_bank(
            updated.to_bank,
            "/credit",
            {"transfer": updated.to_dict()},
            as_payees=False,
        )
        return updated

    async def _call_bank(
        self, bank: str, path: str, payload: dict, as_payees: bool = True
    ) -> list[Payee]:
        from aiohttp import ClientSession

        from rb_interbank.signing import dumps, sign

        peer = self.peers.get(normalize_bank(bank))
        if not peer:
            return []
        body = dumps(payload)
        headers = {
            "Content-Type": "application/json",
            "X-RB-Signature": sign(peer["secret"], body),
        }
        async with ClientSession() as session:
            async with session.post(f"{peer['url'].rstrip('/')}{path}", data=body, headers=headers) as resp:
                data = await resp.json()
        if not as_payees:
            return []
        return [Payee.from_dict(row) for row in data.get("payees") or []]


class RemoteHub:
    """Bank-side client for the hosted hub."""

    def __init__(self, base_url: str, secret: str, bank: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.bank = normalize_bank(bank)

    async def _post(self, path: str, payload: dict) -> dict:
        from aiohttp import ClientSession

        from rb_interbank.signing import dumps, sign

        body = dumps(payload)
        headers = {
            "Content-Type": "application/json",
            "X-RB-Signature": sign(self.secret, body),
            "X-RB-Bank": self.bank,
        }
        async with ClientSession() as session:
            async with session.post(f"{self.base_url}{path}", data=body, headers=headers) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    raise RuntimeError(data.get("error") or resp.reason)
                return data

    async def lookup(self, query: str, bank: str | None = None) -> list[Payee]:
        data = await self._post("/hub/v1/lookup", {"query": query, "bank": bank})
        return [Payee.from_dict(row) for row in data.get("payees") or []]

    async def register_transfer(self, transfer: Transfer) -> Transfer:
        data = await self._post("/hub/v1/transfers", transfer.to_dict())
        return Transfer.from_dict(data["transfer"])

    async def mark_cash_sent(self, transfer_id: str, dc_txn_id: str) -> Transfer:
        data = await self._post(
            f"/hub/v1/transfers/{transfer_id}/cash-sent",
            {"dc_txn_id": dc_txn_id},
        )
        return Transfer.from_dict(data["transfer"])

    async def mark_completed(self, transfer_id: str) -> Transfer:
        data = await self._post(f"/hub/v1/transfers/{transfer_id}/complete", {})
        return Transfer.from_dict(data["transfer"])
