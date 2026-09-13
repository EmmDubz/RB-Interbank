from rb_interbank import InMemoryHub, InterbankNode, Payee, pick_handler


class FakeDc:
    def __init__(self) -> None:
        self.payments: list[tuple[str, int, str]] = []

    async def pay_firm(self, to_firm: str, amount_cents: int, memo: str) -> str:
        self.payments.append((to_firm, amount_cents, memo))
        return "dc_1"


async def test_search_then_click_then_send():
    hub = InMemoryHub()
    dc = FakeDc()
    drb = InterbankNode("DRB", secret="s", hub=hub)
    vdrb = InterbankNode("VDRB", secret="s", hub=hub, ticker_prefix="", dc_sender=dc)

    ledgers = {
        "DRB-MDBZ": 10_000,
        "JDSV": 5_000,
    }

    @drb.on_lookup
    async def drb_lookup(query: str) -> list[Payee]:
        for ref in drb.local_refs(query):
            if ref.upper() == "DRB-MDBZ":
                return [
                    Payee(
                        bank="DRB",
                        account="DRB-MDBZ",
                        name="Matth",
                        match_reason="alias" if query.upper() == "MDBZ" else "ticker",
                    )
                ]
        if query.lower() == "matth":
            return [
                Payee(
                    bank="DRB",
                    account="DRB-MDBZ",
                    name="Matth",
                    match_reason="minecraft",
                    verified=True,
                )
            ]
        return []

    @drb.on_debit
    async def drb_debit(transfer) -> None:
        ledgers[transfer.from_account] -= transfer.amount_cents

    @drb.on_credit
    async def drb_credit(transfer) -> None:
        ledgers[transfer.to_account] += transfer.amount_cents

    @vdrb.on_lookup
    async def vdrb_lookup(query: str) -> list[Payee]:
        if query.upper() == "JDSV":
            return [Payee(bank="VDRB", account="JDSV", name="JDSV Ops")]
        return []

    @vdrb.on_debit
    async def vdrb_debit(transfer) -> None:
        ledgers[transfer.from_account] -= transfer.amount_cents

    @vdrb.on_credit
    async def vdrb_credit(transfer) -> None:
        ledgers[transfer.to_account] += transfer.amount_cents

    by_short = await vdrb.find("MDBZ")
    assert [p.account for p in by_short] == ["DRB-MDBZ"]
    assert by_short[0].display_account == "MDBZ"
    assert by_short[0].label().startswith("DRB:MDBZ")

    by_user = await vdrb.find("matth")
    assert by_user[0].match_reason == "minecraft"

    chosen = await pick_handler(by_short)("DRB:MDBZ")
    assert chosen is not None

    transfer = await vdrb.send(
        from_account="JDSV",
        payee=chosen,
        amount="25.00",
        memo="lunch",
    )
    assert transfer.to_account == "DRB-MDBZ"
    assert ledgers["JDSV"] == 2_500
    assert ledgers["DRB-MDBZ"] == 12_500
    assert dc.payments[0][0] == "DRB"


async def test_same_bank_send_skips_firm_payment():
    hub = InMemoryHub()
    dc = FakeDc()
    vdrb = InterbankNode("VDRB", secret="s", hub=hub, ticker_prefix="", dc_sender=dc)
    ledgers = {"JDSV": 5_000, "INOV": 0}

    @vdrb.on_lookup
    async def lookup(query: str) -> list[Payee]:
        if query.upper() == "INOV":
            return [Payee(bank="VDRB", account="INOV", name="Inov8 test")]
        return []

    @vdrb.on_debit
    async def debit(transfer) -> None:
        ledgers[transfer.from_account] -= transfer.amount_cents

    @vdrb.on_credit
    async def credit(transfer) -> None:
        ledgers[transfer.to_account] += transfer.amount_cents

    payee = (await vdrb.find("INOV"))[0]
    await vdrb.send(from_account="JDSV", payee=payee, amount=100, memo="TEST")
    assert ledgers["JDSV"] == 4_900
    assert ledgers["INOV"] == 100
    assert dc.payments == []
