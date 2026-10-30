"""Faux serveur WebSocket Deriv local : coupures et pannes à la demande, aucun réseau."""

import asyncio
import json
from collections import Counter
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve


class FakeDeriv:
    def __init__(self) -> None:
        self.server: Server | None = None
        self.port = 0
        self.connections: set[ServerConnection] = set()
        self.calls: Counter[str] = Counter()
        self.received: list[dict[str, Any]] = []
        self.opened = 0
        self.tick_subscribers: dict[ServerConnection, Any] = {}
        self.swallow_buy = False  # reçoit l'achat, ne répond jamais
        self.drop_on_buy = False  # reçoit l'achat, coupe la connexion
        self.mute = False  # ne répond plus à rien, sans fermer

    async def __aenter__(self) -> "FakeDeriv":
        self.server = await serve(self._handle, "127.0.0.1", 0)
        self.port = next(iter(self.server.sockets)).getsockname()[1]
        return self

    async def __aexit__(self, *_: object) -> None:
        assert self.server is not None
        self.server.close()
        await self.server.wait_closed()

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    async def drop_all(self) -> None:
        for conn in list(self.connections):
            await conn.close()

    async def push_tick(self, quote: float) -> None:
        for conn, req_id in list(self.tick_subscribers.items()):
            await conn.send(
                json.dumps(
                    {
                        "msg_type": "tick",
                        "req_id": req_id,
                        "subscription": {"id": f"sub-{req_id}"},
                        "tick": {"quote": quote},
                    }
                )
            )

    async def _handle(self, conn: ServerConnection) -> None:
        self.connections.add(conn)
        self.opened += 1
        try:
            async for raw in conn:
                message = json.loads(raw)
                self.received.append(message)
                await self._answer(conn, message)
        finally:
            self.connections.discard(conn)
            self.tick_subscribers.pop(conn, None)

    async def _answer(self, conn: ServerConnection, message: dict[str, Any]) -> None:
        req_id = message.get("req_id")
        if "ping" in message:
            self.calls["ping"] += 1
            if not self.mute:
                await conn.send(json.dumps({"ping": "pong", "req_id": req_id}))
        elif "buy" in message:
            self.calls["buy"] += 1
            if self.drop_on_buy:
                await conn.close()
            elif not self.swallow_buy:
                await conn.send(
                    json.dumps(
                        {
                            "req_id": req_id,
                            "buy": {
                                "contract_id": 42,
                                "buy_price": 1.0,
                                "balance_after": 99.0,
                                "transaction_id": 7,
                                "shortcode": "MULTUP_1HZ75V",
                            },
                        }
                    )
                )
        elif "ticks" in message:
            self.calls["ticks"] += 1
            if message["ticks"] == "BAD":
                error: dict[str, Any] = {"code": "InvalidSymbol", "message": "Symbole inconnu"}
                await conn.send(json.dumps({"req_id": req_id, "error": error}))
                return
            self.tick_subscribers[conn] = req_id
            await conn.send(
                json.dumps(
                    {
                        "req_id": req_id,
                        "subscription": {"id": f"sub-{req_id}"},
                        "tick": {"quote": 100.0},
                    }
                )
            )
        elif "forget" in message:
            self.calls["forget"] += 1
            self.tick_subscribers.pop(conn, None)
            await conn.send(json.dumps({"req_id": req_id, "forget": 1}))
        elif "fail" in message:
            failure = {"code": "Boom", "message": "refusé", "details": {"field": "amount"}}
            await conn.send(json.dumps({"req_id": req_id, "error": failure}))
        elif "slow" in message:
            await asyncio.sleep(0.05 * float(message["slow"]))
            await conn.send(json.dumps({"req_id": req_id, "slow": message["slow"]}))
        elif "ignore" not in message:
            await conn.send(json.dumps({"req_id": req_id, "ok": 1}))
