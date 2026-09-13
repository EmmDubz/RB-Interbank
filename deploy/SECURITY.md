# Hub security

## What must never live on frodvegasnet

- Bank Discord bot tokens
- DemocracyCraft BUSINESS / PERSONAL Treasury JWTs
- Customer passwords or Discord OAuth tokens
- Plaintext copies of bank signing secrets in git or the website

Those stay on the bank hosts (DRB Windows/Oracle bot, VDRB Oracle bot). The hub cannot spend RMD.

## What the hub may hold

- Bank code, ticker prefix, callback URL
- A **verifier** for the bank’s signing secret (HMAC of the secret, or the bank’s public key)
- Transfer ids and memos (`RB:{id}`), not customer balances

Generate secrets with `secrets.token_urlsafe(48)`. Show once in the join pack. Store `/etc/rb-interbank/hub.env` at mode `0600`. Do not put usable keys in the database “for convenience.”

## “Only usable when everything is correct”

Practical version, not a puzzle:

1. Cloudflare Tunnel presents a real cert for `interbank.redmontgroup.org`.
2. Requests must carry a valid `X-RB-Signature` (timestamp + HMAC, 5 minute skew).
3. Debit and credit are idempotent on `transfer_id`.
4. Destination credit happens only after the in-game firm payment is matched.
5. Optional later: Ed25519 per bank so the hub stores only public keys.

Do not invent a Shamir split or “type three passwords to decrypt the key” for v1. That fails at 3 a.m. and still leaves a decrypted key in RAM. systemd credentials + tunnel + no DC keys on the hub is the real control.

## Transport

Bind `127.0.0.1`. Cloudflare Tunnel only. No port 8787 on the LAN or Tailscale ACL for the world. Tailscale is for you to SSH, not for banks to call the API.
