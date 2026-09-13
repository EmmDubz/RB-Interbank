"""Copy-paste starting point for De Ruyter Bank.

DRB tickers look like DRB-MDBZ. Customers can type MDBZ, DRB-MDBZ,
DRB:MDBZ, or a Minecraft / Discord name. The node expands those.
"""

from __future__ import annotations

from rb_interbank import InterbankNode, Payee


def attach_drb(node: InterbankNode, db_fetch_all) -> None:
    @node.on_lookup
    async def lookup(query: str) -> list[Payee]:
        found: list[Payee] = []
        seen: set[str] = set()

        def add(row, reason) -> None:
            ticker = row["ticker"]
            if ticker in seen:
                return
            seen.add(ticker)
            found.append(
                Payee(
                    bank="DRB",
                    account=ticker,
                    name=row["name"],
                    account_type=row.get("account_type") or "PERSONAL",
                    match_reason=reason,
                    verified=bool(row.get("is_verified")),
                )
            )

        for ticker in node.local_refs(query):
            row = db_fetch_all(
                "SELECT ticker, name, account_type, is_verified, status "
                "FROM accounts WHERE upper(ticker)=upper(?) AND status='ACTIVE'",
                (ticker,),
            )
            if row:
                add(row[0], "alias" if ticker.upper() != query.upper() else "ticker")

        people = db_fetch_all(
            """
            SELECT a.ticker, a.name, a.account_type, a.is_verified, a.status
            FROM accounts a
            LEFT JOIN user_minecraft_links m ON m.user_id = a.owner_user_id
            WHERE a.status = 'ACTIVE'
              AND (
                    lower(m.minecraft_username) = lower(?)
                 OR a.owner_user_id = ?
                 OR lower(a.name) LIKE lower(?)
              )
            """,
            (query, query, f"%{query}%"),
        )
        for row in people:
            add(row, "minecraft")
        return found

    @node.on_debit
    async def debit(transfer) -> None:
        # wrap in the same transaction you use for internal transfers
        db_fetch_all(
            "UPDATE accounts SET balance = balance - ? WHERE ticker = ? AND balance >= ?",
            (transfer.amount_cents, transfer.from_account, transfer.amount_cents),
        )

    @node.on_credit
    async def credit(transfer) -> None:
        db_fetch_all(
            "UPDATE accounts SET balance = balance + ? WHERE ticker = ?",
            (transfer.amount_cents, transfer.to_account),
        )
