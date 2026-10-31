"""Données de marché pour le front-end, lues dans Redis, jamais directement chez Deriv."""

import json
import time
from collections import Counter
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.authz import CurrentSession
from app.config import Settings
from app.deps import AppSettings, Db, check_origin
from app.errors import ApiError
from app.market.feed import CANDLE_COUNT, CANDLE_REFRESH_SECONDS, GRANULARITIES
from app.market.store import Data, MarketStore, asset_status

router = APIRouter(prefix="/market", tags=["market"], dependencies=[Depends(check_origin)])

MAX_STREAMS_PER_USER = 5
MAX_WATCHED_SYMBOLS = 60
HEARTBEAT_SECONDS = 15.0
# La session est revalidée à chaque reconnexion du navigateur (EventSource la fait seul).
STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def get_market(request: Request) -> MarketStore:
    store: MarketStore | None = request.app.state.market
    if store is None:
        raise ApiError(503, "market.unavailable")
    return store


Market = Annotated[MarketStore, Depends(get_market)]


class WatchlistIn(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=MAX_WATCHED_SYMBOLS)


async def catalog_of(store: MarketStore, settings: Settings) -> set[str]:
    """Actifs connus de Deriv ; les actifs par défaut restent valables si le flux est tombé."""
    state = await store.get_assets()
    return {*settings.market_symbols, *(a["symbol"] for a in (state or {}).get("assets", []))}


async def catalog(store: Market, settings: AppSettings) -> set[str]:
    return await catalog_of(store, settings)


Catalog = Annotated[set[str], Depends(catalog)]


def check_symbols(symbols: list[str], allowed: set[str]) -> list[str]:
    if any(symbol not in allowed for symbol in symbols):
        raise ApiError(404, "market.unknown_symbol")
    return symbols


async def asset_views(store: MarketStore, symbols: list[str] | None = None) -> list[Data]:
    """Actifs demandés, ou tout le catalogue."""
    state = await store.get_assets()
    if state is None:
        return []
    wanted = [a["symbol"] for a in state["assets"]] if symbols is None else symbols
    ticks = await store.get_ticks(wanted)
    now = time.time()
    return [
        {
            "symbol": asset["symbol"],
            "name": asset["name"],
            "market": asset["market"],
            "submarket": asset.get("submarket"),
            "pip_size": asset["pip_size"],
            "multipliers": asset.get("multipliers"),
            "status": asset_status(asset, ticks.get(asset["symbol"]), state["updated_at"], now),
            "tick": ticks.get(asset["symbol"]),
        }
        for asset in state["assets"]
        if symbols is None or asset["symbol"] in symbols
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
async def assets(_: CurrentSession, store: Market) -> dict[str, object]:
    return {"assets": await asset_views(store)}


@router.get("/watchlist")
def read_watchlist(settings: AppSettings, session: CurrentSession) -> dict[str, object]:
    """Actifs affichés dans la barre du client, dans l'ordre qu'il a choisi."""
    return {"symbols": session.user.market_watchlist or settings.market_symbols}


@router.put("/watchlist")
def write_watchlist(
    body: WatchlistIn, db: Db, session: CurrentSession, known: Catalog
) -> dict[str, object]:
    symbols = list(dict.fromkeys(check_symbols(body.symbols, known)))
    session.user.market_watchlist = symbols
    db.commit()
    return {"symbols": symbols}


@router.get("/candles")
async def candles(
    _: CurrentSession,
    store: Market,
    known: Catalog,
    symbol: Annotated[str, Query(max_length=30)],
    granularity: Annotated[int, Query()] = GRANULARITIES[0],
    count: Annotated[int, Query(ge=1, le=CANDLE_COUNT)] = CANDLE_COUNT,
) -> dict[str, object]:
    check_symbols([symbol], known)
    if granularity not in GRANULARITIES:
        raise ApiError(422, "market.invalid_granularity")
    # Lire un actif le fait suivre par le flux : ses bougies arrivent dans la seconde.
    await store.demand(symbol)
    stored = await store.get_candles(symbol, granularity)
    updated_at = stored["updated_at"] if stored else 0.0
    return {
        "symbol": symbol,
        "granularity": granularity,
        "updated_at": updated_at,
        # Bougies absentes ou anciennes : le navigateur relit aussitôt.
        "refreshing": time.time() - updated_at > CANDLE_REFRESH_SECONDS[granularity] * 2,
        "candles": stored["candles"][-count:] if stored else [],
    }


@router.get("/stream")
async def stream(
    request: Request,
    db: Db,
    settings: AppSettings,
    session: CurrentSession,
    store: Market,
    known: Catalog,
    symbols: Annotated[list[str] | None, Query(max_length=MAX_WATCHED_SYMBOLS)] = None,
) -> StreamingResponse:
    watched = check_symbols(symbols, known) if symbols else settings.market_symbols
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
