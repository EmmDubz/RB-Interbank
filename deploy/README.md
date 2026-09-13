# Deploy on frodvegasnet

Oracle (`150.230.117.88`) already serves `redmontgroup.org` and `vdrb.redmontgroup.org` with nginx + Let’s Encrypt. That box is **not** on this Tailscale tailnet. `frodvegasnet` is. Do not publish the Tailscale IP.

Matt has no passwordless sudo. The live stack is Docker Compose under `/home/matt/services`. The hub follows that, not `/opt` + a system unit.

## DNS

Use names, not IPs:

| Host | Purpose |
|---|---|
| `inov8.redmontgroup.org` | This site |
| `interbank.redmontgroup.org` | Hub API (same process for now) |

A `cloudflare_tunnel` container is already running from `/home/matt/services/tunnels` (token in that compose `.env`). Add two **Public Hostnames** on that existing tunnel in Cloudflare Zero Trust:

| Public hostname | Type | URL |
|---|---|---|
| `inov8.redmontgroup.org` | HTTP | `http://rb-interbank:8787` |
| `interbank.redmontgroup.org` | HTTP | `http://rb-interbank:8787` |

The hub container joins `tunnels_default` so cloudflared can resolve `rb-interbank`. Also add proxied CNAMEs in the `redmontgroup.org` zone if Zero Trust does not create them.

Do not point hostnames at `127.0.0.1` from inside the tunnel container — that is the tunnel container itself.

## App

```bash
git clone https://github.com/EmmDubz/RB-Interbank.git /home/matt/services/web/rb-interbank
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# write /home/matt/services/web/rb-interbank/.env (mode 0600)
# add the rb-interbank service to /home/matt/services/web/docker-compose.yml
cd /home/matt/services/web && docker compose up -d --build rb-interbank
```

Host publish is `127.0.0.1:8787` only. Inside the container the app binds `0.0.0.0:8787`.

## Env

**Each bank** (VDRB live `.env` already has these):

| Variable | Meaning |
|---|---|
| `RB_BANK` | `VDRB` or `DRB` |
| `RB_SECRET` | HMAC secret. Same value as that bank’s entry in hub `RB_PEERS`. |
| `RB_HUB_URL` | Where the bank calls the hub. Live VDRB uses `http://rb-interbank:8787` on the docker network. Off-box banks use `https://interbank.redmontgroup.org`. |
| `RB_INTERBANK_SRC` | Folder that contains the `rb_interbank` package. Live VDRB: `/rb_interbank`. |
| `RB_TICKER_PREFIX` | DRB only: `DRB-`. Leave empty on VDRB. |

Leave `RB_SECRET` empty to hide the Interbank button.

**Hub** (`/home/matt/services/web/rb-interbank/.env`):

```text
RB_PEERS=[{"bank":"VDRB","url":"http://vdrb-bot:8080/rb/v1","secret":"<same as VDRB RB_SECRET>"}]
```

Add DRB to that JSON when DRB’s `/rb/v1` is reachable. Same-box banks can use docker DNS. Off-box banks need a public `https://…/rb/v1`.

## What this agent could not do from Cursor

Cloudflare Zero Trust hostname/DNS writes. Bank `.env` secrets and deploying the local DRB/VDRB adapter code onto the live bots.
