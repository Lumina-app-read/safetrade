"""Données de marché pour le front-end, lues dans Redis, jamais directement chez Deriv."""

import json
import time
from collections import Counter
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.authz import CurrentSession
from app.deps import AppSettings, Db, check_origin
from app.errors import ApiError
from app.market.feed import CANDLE_COUNT, GRANULARITIES
from app.market.store import Data, MarketStore, asset_status

router = APIRouter(prefix="/market", tags=["market"], dependencies=[Depends(check_origin)])

MAX_STREAMS_PER_USER = 5
HEARTBEAT_SECONDS = 15.0
# La session est revalidée à chaque reconnexion du navigateur (EventSource la fait seul).
STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def get_market(request: Request) -> MarketStore:
    store: MarketStore | None = request.app.state.market
    if store is None:
        raise ApiError(503, "market.unavailable")
    return store


Market = Annotated[MarketStore, Depends(get_market)]


def check_symbols(symbols: list[str], allowed: list[str]) -> list[str]:
    if any(symbol not in allowed for symbol in symbols):
        raise ApiError(404, "market.unknown_symbol")
    return symbols


async def asset_views(store: MarketStore, symbols: list[str]) -> list[Data]:
    state = await store.get_assets()
    if state is None:
        return []
    ticks = await store.get_ticks(symbols)
    now = time.time()
    return [
        {
            "symbol": asset["symbol"],
            "name": asset["name"],
            "market": asset["market"],
            "pip_size": asset["pip_size"],
            "status": asset_status(asset, ticks.get(asset["symbol"]), state["updated_at"], now),
            "tick": ticks.get(asset["symbol"]),
        }
        for asset in state["assets"]
        if asset["symbol"] in symbols
    ]


def sse(event: str, data: Data | list[Data]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_events(
    store: MarketStore, symbols: list[str], seconds: float
) -> AsyncIterator[str]:
    """État initial, puis événements. Le serveur ferme : le navigateur se reconnecte."""
    started = time.monotonic()
    beat = started
    ready = False
    async for event in store.listen():
        if not ready:
            # Écoute ouverte avant la lecture : aucun tick perdu entre les deux.
            ready = True
            yield sse("snapshot", await asset_views(store, symbols))
        elif event is not None and event["symbol"] in symbols:
            yield sse(event["type"], event)
        now = time.monotonic()
        if now - started >= seconds:
            return
        if now - beat >= HEARTBEAT_SECONDS:
            beat = now
            yield ": ping\n\n"


@router.get("/assets")
async def assets(settings: AppSettings, _: CurrentSession, store: Market) -> dict[str, object]:
    return {"assets": await asset_views(store, settings.market_symbols)}


@router.get("/candles")
async def candles(
    settings: AppSettings,
    _: CurrentSession,
    store: Market,
    symbol: Annotated[str, Query(max_length=30)],
    granularity: Annotated[int, Query()] = GRANULARITIES[0],
    count: Annotated[int, Query(ge=1, le=CANDLE_COUNT)] = CANDLE_COUNT,
) -> dict[str, object]:
    check_symbols([symbol], settings.market_symbols)
    if granularity not in GRANULARITIES:
        raise ApiError(422, "market.invalid_granularity")
    stored = await store.get_candles(symbol, granularity)
    if stored is None:
        raise ApiError(503, "market.unavailable")
    return {
        "symbol": symbol,
        "granularity": granularity,
        "updated_at": stored["updated_at"],
        "candles": stored["candles"][-count:],
    }


@router.get("/stream")
async def stream(
    request: Request,
    db: Db,
    settings: AppSettings,
    session: CurrentSession,
    store: Market,
    symbols: Annotated[list[str] | None, Query(max_length=20)] = None,
) -> StreamingResponse:
    watched = (
        check_symbols(symbols, settings.market_symbols) if symbols else settings.market_symbols
    )
    user_id = session.user_id
    # Un flux dure plusieurs minutes : il ne garde pas de connexion à la base.
    db.close()
    opened: Counter[object] = request.app.state.market_streams
    if opened[user_id] >= MAX_STREAMS_PER_USER:
        raise ApiError(429, "market.too_many_streams")
    opened[user_id] += 1

    async def body() -> AsyncIterator[str]:
        try:
            async for chunk in stream_events(store, watched, settings.market_stream_seconds):
                yield chunk
        finally:
            opened[user_id] -= 1

    return StreamingResponse(body(), media_type="text/event-stream", headers=STREAM_HEADERS)
