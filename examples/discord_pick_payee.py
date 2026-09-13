"""Search → list every matching bank account → click one.

This is the UX, not a dependency. Paste the idea into the bank's existing
discord.py views. No extra packages required.
"""

from rb_interbank import pick_handler

# 1. Customer types "MDBZ" or "Matth" in a modal.
# 2. payees = await node.find(query)
# 3. If several, show a button per payee:
#       DRB:MDBZ — Matth
#       VDRB:JDSV — JDSV Ops
# 4. Click runs pick_handler(payees)("DRB:MDBZ")
# 5. Confirm amount, then await node.send(from_account=..., payee=chosen, amount=...)


async def choose(node, query: str, clicked: str | None = None):
    payees = await node.find(query)
    if not payees:
        return None, []
    if len(payees) == 1 and clicked is None:
        return payees[0], payees
    if clicked is None:
        return None, payees
    return await pick_handler(payees)(clicked), payees
