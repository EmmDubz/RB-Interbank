"""VDRB starting point — tickers have no house prefix."""

from rb_interbank import InterbankNode, Payee


def attach_vdrb(node: InterbankNode, db_fetch_all) -> None:
    @node.on_lookup
    async def lookup(query: str) -> list[Payee]:
        rows = db_fetch_all(
            """
            SELECT a.ticker, a.name, a.account_type, a.is_verified
            FROM accounts a
            LEFT JOIN user_minecraft_links m ON m.user_id = a.owner_user_id
            WHERE a.status = 'ACTIVE'
              AND (
                    upper(a.ticker) = upper(?)
                 OR lower(m.minecraft_username) = lower(?)
                 OR a.owner_user_id = ?
              )
            """,
            (query, query, query),
        )
        return [
            Payee(
                bank="VDRB",
                account=row["ticker"],
                name=row["name"],
                account_type=row.get("account_type") or "PERSONAL",
                match_reason="ticker",
                verified=bool(row.get("is_verified")),
            )
            for row in rows
        ]
