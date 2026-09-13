# RB Interbank

Free DemocracyCraft interbank rail. Banks keep their own ledgers. Customers
search a name or ticker, see every matching account across member banks, and
click one.

Qash addresses are 14-character routing numbers and a prefunded clearing house.
This is bank + ticker, then real firm-to-firm RMD. No network fee.

## A bank implements three functions

```python
from aiohttp import web
from rb_interbank import InterbankNode, InMemoryHub, Payee

hub = InMemoryHub()  # hosted hub URL in production
node = InterbankNode("DRB", secret="shared-with-hub", hub=hub)

@node.on_lookup
async def lookup(query: str) -> list[Payee]:
    # query may be MDBZ, DRB-MDBZ, a Minecraft name, or a Discord id
    ...

@node.on_debit
async def debit(transfer) -> None:
    # take transfer.amount_cents off transfer.from_account
    # must be idempotent on transfer.transfer_id
    ...

@node.on_credit
async def credit(transfer) -> None:
    # put transfer.amount_cents on transfer.to_account
    # must be idempotent on transfer.transfer_id
    ...

app = web.Application()
node.mount(app)   # POST /rb/v1/lookup|debit|credit
```

That is the whole integration. Search, HMAC, fan-out, and settlement
orchestration live in the package. Non-Python banks implement the same three
routes from [`openapi/rb-interbank.yaml`](openapi/rb-interbank.yaml).

## How a customer pays `DRB-MDBZ`

| They type | What happens |
|---|---|
| Bank `DRB`, account `MDBZ` | Resolver also tries `DRB-MDBZ` |
| `DRB:MDBZ` or `DRB/MDBZ` | Same |
| `DRB-MDBZ` | Exact ticker |
| `Matth` (Minecraft or Discord) | Every opted-in account for that person, at every member bank |

If more than one payee hits, the UI lists them and the customer clicks:

```text
DRB:MDBZ — Matth
VDRB:JDSV — JDSV Ops
```

`node.find("MDBZ")` does the fan-out. `pick_handler(payees)("DRB:MDBZ")`
turns the click back into a `Payee`. Then:

```python
await node.send(from_account="VDRB-OPS", payee=chosen, amount="25.00")
```

The sending bank debits locally, pays the destination **firm** through the
DemocracyCraft Economy API (`POST /api/v1/transfers/to-firm`), and the
receiving bank only credits the customer after that cash is matched. No
prefunded Qash settlement account. Do not put a personal API key in this path.

Pass your existing DC client as `dc_sender` so you do not write a second
Treasury wrapper:

```python
class ExistingDc:
    async def pay_firm(self, to_firm: str, amount_cents: int, memo: str) -> str:
        result = await dc.transfer_to_firm(
            from_account_id=FIRM_ACCOUNT_ID,
            to_firm=to_firm,
            amount=Decimal(amount_cents) / 100,
            memo=memo,
            idempotency_key=memo,
        )
        return str(result["txnId"])

node = InterbankNode("DRB", secret="...", hub=hub, dc_sender=ExistingDc())
```

DRB tickers keep the `DRB-` prefix in the database. The customer never has
to type it. VDRB tickers stay as they are (`JDSV`).

Copy-paste SQL for DRB: [`examples/drb_hooks.py`](examples/drb_hooks.py).
Click UX sketch: [`examples/discord_pick_payee.py`](examples/discord_pick_payee.py).

## Install

```text
pip install -e .[dev]
pytest
```

Founding banks: De Ruyter Bank and Vendeka Redmont Bank.
