"""
Téléchargement des ticks historiques pour le banc d'essai : lecture seule, point public, sans
jeton, jamais d'ordre. Reprend là où il s'est arrêté, car le fichier ne fait que grandir.

    python -m app.backtest.fetch --days 7 --symbols stpRNG BOOM500 JD10 1HZ100V RB100 1HZ15V

Deriv renvoie 1 000 ticks au plus par appel, et seule la paire `start` et `end` remonte le temps.
"""

import argparse
import asyncio
import logging
import time
from pathlib import Path

from app.broker.base import BrokerError
from app.broker.deriv import PUBLIC_WS_URL, DerivConnection
from app.broker.quotas import MemoryQuotaStore, QuotaManager

logger = logging.getLogger("safetrade.backtest")

DATA_DIR = Path(".backtest")
PAGE_SECONDS = 900
# Le flux de marché partage ce quota : 130 appels par minute laissent de la marge sous les 176.
PAUSE_SECONDS = 0.45
# Dix minutes de patience : une coupure de réseau ne doit pas perdre le téléchargement.
RETRY_SECONDS = 15.0
RETRIES = 40


def path_of(directory: Path, symbol: str) -> Path:
    return directory / f"{symbol}.csv"


def last_epoch(path: Path) -> int | None:
    """Dernier tick écrit. Une ligne coupée par un arrêt brutal est ignorée à la lecture."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    with path.open("rb") as file:
        file.seek(max(0, path.stat().st_size - 200))
        rows = file.read().decode().strip().splitlines()
    for row in reversed(rows):
        epoch, _, price = row.partition(",")
        if price and epoch.isdigit():
            return int(epoch)
    return None


async def _page(connection: DerivConnection, symbol: str, start: int, end: int) -> list[str]:
    for attempt in range(RETRIES):
        try:
            response = await connection.request(
                "ticks_history",
                {"ticks_history": symbol, "style": "ticks", "start": start, "end": end},
            )
            history = response["history"]
            return [
                f"{epoch},{price}"
                for epoch, price in zip(history["times"], history["prices"], strict=True)
            ]
        except BrokerError as exc:
            # Lecture seule : une nouvelle demande ne présente aucun risque.
            logger.warning("page reportée : %s, essai %s", type(exc).__name__, attempt + 1)
            await asyncio.sleep(RETRY_SECONDS)
    raise RuntimeError(f"historique inaccessible pour {symbol}")


async def fetch_symbol(
    connection: DerivConnection, directory: Path, symbol: str, start: int, end: int
) -> int:
    path = path_of(directory, symbol)
    seen = last_epoch(path)
    cursor = seen + 1 if seen is not None else start
    written = 0
    with path.open("a", encoding="ascii", newline="\n") as file:
        while cursor < end:
            stop = min(cursor + PAGE_SECONDS, end)
            rows = await _page(connection, symbol, cursor, stop)
            file.write("".join(f"{row}\n" for row in rows))
            file.flush()
            written += len(rows)
            cursor = stop + 1
            await asyncio.sleep(PAUSE_SECONDS)
    return written


async def run(symbols: list[str], days: float, directory: Path) -> None:
    async def url() -> str:
        return PUBLIC_WS_URL

    directory.mkdir(exist_ok=True)
    end = int(time.time())
    start = end - int(days * 86400)
    connection = DerivConnection(
        url, QuotaManager(MemoryQuotaStore()), scope="backtest", uses_otp=False
    )
    await connection.start()
    await connection.wait_connected(60)
    try:
        for symbol in symbols:
            count = await fetch_symbol(connection, directory, symbol, start, end)
            print(f"{symbol} : {count} ticks ajoutés", flush=True)
    finally:
        await connection.stop()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.backtest.fetch")
    parser.add_argument("--days", type=float, default=7)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--directory", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    asyncio.run(run(args.symbols, args.days, args.directory))


if __name__ == "__main__":
    main()
