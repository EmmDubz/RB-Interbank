#!/usr/bin/env python3
"""Idempotent live wiring on frodvegasnet. Do not print secrets."""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import subprocess
from pathlib import Path

WEB = Path("/home/matt/services/web")
BOTS = Path("/home/matt/services/bots")
HUB = WEB / "rb-interbank"
HUB_ENV = HUB / ".env"
VDRB = BOTS / "vdrb-bot"
VDRB_ENV = VDRB / ".env"
WEB_COMPOSE = WEB / "docker-compose.yml"
BOTS_COMPOSE = BOTS / "docker-compose.yml"
DB = VDRB / "vdrb.db"
ADMIN = "223903425597800450"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=cwd)


def upsert_env(path: Path, values: dict[str, str]) -> None:
    path.touch(mode=0o600)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    keys = set(values)
    kept = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line and not line.lstrip().startswith("#") else ""
        if key in keys:
            continue
        kept.append(line)
    for key, value in values.items():
        kept.append(f"{key}={value}")
    text = "\n".join(kept).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key] = value
    return out


def ensure_config_rb() -> None:
    path = VDRB / "config.py"
    text = path.read_text(encoding="utf-8")
    if "RB_SECRET" in text:
        print("config.py already has RB_*")
        return
    block = """
# --- RB Interbank (optional dual rail). Empty secret keeps Qash-only wires. ---
RB_BANK = os.getenv("RB_BANK", "VDRB")
RB_TICKER_PREFIX = os.getenv("RB_TICKER_PREFIX", "")
RB_HUB_URL = os.getenv("RB_HUB_URL", "")
RB_SECRET = os.getenv("RB_SECRET", "")
RB_INTERBANK_SRC = os.getenv("RB_INTERBANK_SRC", "/rb_interbank")

"""
    needle = "# --- Accounting ---"
    if needle not in text:
        raise SystemExit("config.py accounting marker missing")
    path.write_text(text.replace(needle, block + needle, 1), encoding="utf-8")
    print("patched config.py")


def ensure_server_mount() -> None:
    path = VDRB / "server.py"
    text = path.read_text(encoding="utf-8")
    if "node.mount(app)" in text:
        print("server.py already mounts interbank")
        return
    needle = "    runner = web.AppRunner(app)"
    insert = """    try:
        import interbank
        node = interbank.get_node()
        if node is not None:
            node.mount(app)
            print("--- RB Interbank mounted at /rb/v1 ---", flush=True)
    except Exception as exc:
        print(f"--- RB Interbank not mounted: {exc} ---", flush=True)

"""
    if needle not in text:
        raise SystemExit("server.py runner marker missing")
    path.write_text(text.replace(needle, insert + needle, 1), encoding="utf-8")
    print("patched server.py")


def ensure_views_button() -> None:
    path = VDRB / "views.py"
    text = path.read_text(encoding="utf-8")
    if "async def rb_interbank" in text:
        print("views.py already has Interbank button")
        return
    needle = '@discord.ui.button(label="External Wire'
    insert = """    @discord.ui.button(label="Interbank (free)", style=discord.ButtonStyle.primary)
    async def rb_interbank(self, interaction: discord.Interaction, button: discord.ui.Button):
        import interbank
        from interbank_views import InterbankSearchModal

        if not interbank.enabled():
            await interaction.response.send_message(
                "RB Interbank is not configured. Use External Wire for Qash.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            InterbankSearchModal(self.bot, self.source_account, self.dashboard_view, self.dashboard_message)
        )

    """
    if needle not in text:
        raise SystemExit("views.py External Wire button missing")
    path.write_text(text.replace(needle, insert + needle, 1), encoding="utf-8")
    print("patched views.py")


def ensure_compose() -> None:
    bots = BOTS_COMPOSE.read_text(encoding="utf-8")
    mount = "/home/matt/services/web/rb-interbank/src:/rb_interbank:ro"
    if mount not in bots:
        bots = bots.replace(
            "      - ./vdrb-bot:/vdrb-bot\n    healthcheck:",
            f"      - ./vdrb-bot:/vdrb-bot\n      - {mount}\n    healthcheck:",
            1,
        )
        BOTS_COMPOSE.write_text(bots, encoding="utf-8")
        print("patched bots compose volume")
    else:
        print("bots compose already mounts rb_interbank")

    web = WEB_COMPOSE.read_text(encoding="utf-8")
    if re.search(r"rb-interbank:[\s\S]*bots_default", web):
        print("web compose already on bots_default")
        return
    old = """    networks:
      - default
      - tunnels_default
    security_opt:
      - no-new-privileges:true
    healthcheck:
      test: [\"CMD-SHELL\", \"python -c \\\"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=3)\\\"\"]
"""
    new = """    networks:
      - default
      - tunnels_default
      - bots_default
    security_opt:
      - no-new-privileges:true
    healthcheck:
      test: [\"CMD-SHELL\", \"python -c \\\"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=3)\\\"\"]
"""
    if old not in web:
        # looser fallback
        if "      - tunnels_default\n    security_opt:" in web:
            web = web.replace(
                "      - tunnels_default\n    security_opt:",
                "      - tunnels_default\n      - bots_default\n    security_opt:",
                1,
            )
        else:
            raise SystemExit("web compose rb-interbank networks block not found")
    else:
        web = web.replace(old, new, 1)
    WEB_COMPOSE.write_text(web, encoding="utf-8")
    print("patched web compose networks")


def ensure_inov_account() -> None:
    con = sqlite3.connect(DB)
    cur = con.cursor()
    row = cur.execute(
        "SELECT ticker FROM accounts WHERE upper(ticker) IN ('INOV','VDRB-INOV')"
    ).fetchone()
    if row:
        print("INOV account exists:", row[0])
        con.close()
        return
    cur.execute(
        """
        INSERT INTO accounts (ticker, name, account_type, owner_user_id, is_public, is_verified, status)
        VALUES ('INOV', 'Inov8 test sink', 'BUSINESS', ?, 1, 1, 'ACTIVE')
        """,
        (ADMIN,),
    )
    con.commit()
    con.close()
    print("created INOV test sink account")


def main() -> None:
    run(["git", "-C", str(HUB), "pull", "--ff-only"])
    run(
        [
            "curl",
            "-fsSL",
            "https://raw.githubusercontent.com/EmmDubz/VDRB/main/interbank.py",
            "-o",
            str(VDRB / "interbank.py"),
        ]
    )
    run(
        [
            "curl",
            "-fsSL",
            "https://raw.githubusercontent.com/EmmDubz/VDRB/main/interbank_views.py",
            "-o",
            str(VDRB / "interbank_views.py"),
        ]
    )
    ensure_config_rb()
    ensure_server_mount()
    ensure_views_button()
    ensure_compose()
    ensure_inov_account()

    vdrb = read_env(VDRB_ENV)
    secret = vdrb.get("RB_SECRET") or secrets.token_urlsafe(48)
    upsert_env(
        VDRB_ENV,
        {
            "RB_BANK": "VDRB",
            "RB_HUB_URL": "http://rb-interbank:8787",
            "RB_SECRET": secret,
            "RB_INTERBANK_SRC": "/rb_interbank",
        },
    )
    peers = json.dumps(
        [{"bank": "VDRB", "url": "http://vdrb-bot:8080/rb/v1", "secret": secret}],
        separators=(",", ":"),
    )
    upsert_env(
        HUB_ENV,
        {
            "RB_BIND": "0.0.0.0",
            "RB_PORT": "8787",
            "RB_PEERS": peers,
        },
    )
    print("wrote VDRB and hub env (secrets not printed)")
    run(["docker", "compose", "up", "-d", "--build", "rb-interbank"], cwd=WEB)
    run(["docker", "compose", "up", "-d", "vdrb-bot"], cwd=BOTS)


if __name__ == "__main__":
    main()
