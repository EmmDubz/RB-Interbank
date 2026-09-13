# Deploy on frodvegasnet

Oracle (`150.230.117.88`) already serves `redmontgroup.org` and `vdrb.redmontgroup.org` with nginx + Let’s Encrypt. That box is **not** on this Tailscale tailnet. `frodvegasnet` (`100.108.123.23`) is. Do not publish the Tailscale IP.

## DNS

Use names, not IPs:

| Host | Purpose |
|---|---|
| `inov8.redmontgroup.org` | This site |
| `interbank.redmontgroup.org` | Hub API (same process for now) |

In Cloudflare (or wherever `redmontgroup.org` is hosted), add two **CNAME** records to the tunnel hostname `TUNNEL_ID.cfargotunnel.com`. Proxy on (orange cloud) if the zone is on Cloudflare.

## Cloudflare Tunnel

The origin binds `127.0.0.1:8787`. Nothing else should listen publicly.

```bash
cloudflared tunnel login
cloudflared tunnel create inov8
cloudflared tunnel route dns inov8 inov8.redmontgroup.org
cloudflared tunnel route dns inov8 interbank.redmontgroup.org
# edit deploy/cloudflared-config.yml with the tunnel id
sudo cp deploy/cloudflared-config.yml /etc/cloudflared/config.yml
sudo systemctl enable --now cloudflared
```

You do **not** need to open ports on the Linux firewall or Oracle security list for this app.

## App

```bash
sudo useradd -r -s /usr/sbin/nologin rbinterbank
sudo git clone https://github.com/EmmDubz/RB-Interbank.git /opt/rb-interbank
sudo python3 -m venv /opt/rb-interbank/.venv
sudo /opt/rb-interbank/.venv/bin/pip install -e /opt/rb-interbank
sudo mkdir -p /etc/rb-interbank /opt/rb-interbank/data
sudo cp /opt/rb-interbank/deploy/hub.env.example /etc/rb-interbank/hub.env
sudo chmod 600 /etc/rb-interbank/hub.env
sudo cp /opt/rb-interbank/deploy/rb-interbank.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rb-interbank
```

## What this agent could not do from Cursor

Tailscale SSH from this Windows user is denied by tailnet policy (`matth` is not an allowed SSH user on `frodvegasnet`). Approve SSH for this machine, or run the commands above on the box yourself.
