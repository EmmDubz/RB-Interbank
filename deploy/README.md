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

`RB_PEERS` stays empty until DRB and VDRB expose `/rb/v1`. Empty peers = in-memory hub + the public site.

## What this agent could not do from Cursor

Cloudflare Zero Trust hostname/DNS writes. Bank `.env` secrets and deploying the local DRB/VDRB adapter code onto the live bots.
