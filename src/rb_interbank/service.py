"""Local hub + static Inov8 site. Bind to 127.0.0.1; expose via Cloudflare Tunnel."""

from __future__ import annotations

import os
from pathlib import Path

from aiohttp import web

import json

from rb_interbank.hub import InMemoryHub, PeerHub
from rb_interbank.types import Transfer

WEBSITE = Path(__file__).resolve().parents[2] / "website"


def create_app() -> web.Application:
    app = web.Application()
    peers_raw = os.getenv("RB_PEERS", "").strip().strip("'\"")
    if peers_raw:
        app["hub"] = PeerHub(json.loads(peers_raw))
    else:
        app["hub"] = InMemoryHub()
    app.router.add_get("/healthz", _health)
    app.router.add_post("/hub/v1/lookup", _hub_lookup)
    app.router.add_post("/hub/v1/transfers", _hub_register)
    app.router.add_post("/hub/v1/transfers/{transfer_id}/cash-sent", _hub_cash_sent)
    app.router.add_post("/hub/v1/transfers/{transfer_id}/complete", _hub_complete)
    if WEBSITE.is_dir():
        app.router.add_get("/", _index)
        app.router.add_get("/styles.css", _styles)
        assets = WEBSITE / "assets"
        if assets.is_dir():
            app.router.add_static("/assets", assets)
        favicon = assets / "favicon.png"
        if favicon.is_file():
            app.router.add_get("/favicon.ico", _favicon)
    return app


async def _index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(WEBSITE / "index.html")


async def _styles(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEBSITE / "styles.css")


async def _favicon(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEBSITE / "assets" / "favicon.png")


async def _health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "rb-interbank"})


async def _hub_lookup(request: web.Request) -> web.Response:
    body = await request.json()
    payees = await request.app["hub"].lookup(body.get("query") or "", body.get("bank"))
    return web.json_response({"payees": [p.to_dict() for p in payees]})


async def _hub_register(request: web.Request) -> web.Response:
    body = await request.json()
    transfer = await request.app["hub"].register_transfer(Transfer.from_dict(body))
    return web.json_response({"transfer": transfer.to_dict()})


async def _hub_cash_sent(request: web.Request) -> web.Response:
    body = await request.json()
    transfer = await request.app["hub"].mark_cash_sent(
        request.match_info["transfer_id"], str(body.get("dc_txn_id") or "")
    )
    return web.json_response({"transfer": transfer.to_dict()})


async def _hub_complete(request: web.Request) -> web.Response:
    transfer = await request.app["hub"].mark_completed(request.match_info["transfer_id"])
    return web.json_response({"transfer": transfer.to_dict()})


def main() -> None:
    host = os.getenv("RB_BIND", "127.0.0.1")
    port = int(os.getenv("RB_PORT", "8787"))
    web.run_app(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
