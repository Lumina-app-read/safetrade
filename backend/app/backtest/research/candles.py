"""
Bougies d'une minute pour la recherche : lecture seule, point public, jamais d'ordre.

    python -m app.backtest.research.candles --end 2026-11-01 --days 365 --symbols frxEURUSD

Deriv renvoie 1 000 bougies par appel. On remonte le temps depuis `--end` jusqu'à ce que
plusieurs pages de suite reviennent vides : un week-end n'arrête donc pas le téléchargement.
"""

import argparse
import asyncio
import logging
import time
from array import array
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.broker.base import BrokerError
from app.broker.deriv import PUBLIC_WS_URL, DerivConnection
from app.broker.quotas import MemoryQuotaStore, QuotaManager

logger = logging.getLogger("safetrade.backtest")

DATA_DIR = Path(".backtest/candles")
MINUTE = 60
PAGE_SECONDS = 1000 * MINUTE
PAUSE_SECONDS = 0.5
RETRY_SECONDS = 15.0
RETRIES = 40
# Trois jours de pages vides : au-delà d'un week-end, l'historique est épuisé.
EMPTY_PAGES_TO_STOP = 5


@dataclass(frozen=True)
class Bars:
    """Colonnes compactes : une année de bougies tient en mémoire dans chaque processus."""

    epoch: "array[int]"
    open: "array[float]"
    high: "array[float]"
    low: "array[float]"
    close: "array[float]"

    def __len__(self) -> int:
        return len(self.epoch)


def path_of(directory: Path, symbol: str) -> Path:
    return directory / f"{symbol}.csv"


def load(path: Path, until: int | None = None) -> Bars:
    """`until` exclu : la phase d'exploration ne charge jamais une bougie de la période de test."""
    bars = Bars(array("q"), array("d"), array("d"), array("d"), array("d"))
    for row in path.read_text(encoding="ascii").splitlines():
        parts = row.split(",")
        if len(parts) != 5:
            continue
        epoch = int(parts[0])
        if until is not None and epoch >= until:
            break
        if len(bars) and epoch <= bars.epoch[-1]:
            continue
        bars.epoch.append(epoch)
        bars.open.append(float(parts[1]))
        bars.high.append(float(parts[2]))
        bars.low.append(float(parts[3]))
        bars.close.append(float(parts[4]))
    return bars


async def _page(connection: DerivConnection, symbol: str, start: int, end: int) -> list[str]:
    for attempt in range(RETRIES):
        try:
            response = await connection.request(
                "ticks_history",
                {
                    "ticks_history": symbol,
                    "style": "candles",
                    "granularity": MINUTE,
                    "start": start,
                    "end": end,
                },
            )
            return [
                f"{c['epoch']},{c['open']},{c['high']},{c['low']},{c['close']}"
                for c in response.get("candles", [])
            ]
        except BrokerError as exc:
            logger.warning("page reportée : %s, essai %s", type(exc).__name__, attempt + 1)
            await asyncio.sleep(RETRY_SECONDS)
    raise RuntimeError(f"historique inaccessible pour {symbol}")


async def fetch_symbol(
    connection: DerivConnection, directory: Path, symbol: str, end: int, days: float
) -> int:
    floor = end - int(days * 86400)
    pages: list[list[str]] = []
    empty = 0
    cursor = end
    while cursor > floor and empty < EMPTY_PAGES_TO_STOP:
        start = max(cursor - PAGE_SECONDS + MINUTE, floor)
        rows = await _page(connection, symbol, start, cursor)
        pages.append(rows)
        empty = 0 if rows else empty + 1
        cursor = start - MINUTE
        await asyncio.sleep(PAUSE_SECONDS)
    # Écriture en une fois, du plus ancien au plus récent : pas de fichier partiel après un arrêt.
    rows = [row for page in reversed(pages) for row in page]
    temporary = path_of(directory, symbol).with_suffix(".tmp")
    temporary.write_text("".join(f"{row}\n" for row in rows), encoding="ascii", newline="\n")
    temporary.replace(path_of(directory, symbol))
    return len(rows)


async def run(symbols: list[str], end: int, days: float, directory: Path) -> None:
    async def url() -> str:
        return PUBLIC_WS_URL

    directory.mkdir(parents=True, exist_ok=True)
    connection = DerivConnection(
        url, QuotaManager(MemoryQuotaStore()), scope="research", uses_otp=False
    )
    await connection.start()
    await connection.wait_connected(60)
    try:
        for symbol in symbols:
            if path_of(directory, symbol).exists():
                print(f"{symbol} : déjà présent", flush=True)
                continue
            started = time.monotonic()
            count = await fetch_symbol(connection, directory, symbol, end, days)
            print(f"{symbol} : {count} bougies, {time.monotonic() - started:.0f} s", flush=True)
    finally:
        await connection.stop()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.backtest.research.candles")
    parser.add_argument("--end", required=True, help="date de fin, AAAA-MM-JJ, en UTC")
    parser.add_argument("--days", type=float, default=365)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--directory", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    end = int(datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())
    asyncio.run(run(args.symbols, end, args.days, args.directory))


if __name__ == "__main__":
    main()
