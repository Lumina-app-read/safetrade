"""
Ticks pour la recherche, entre deux dates précises : lecture seule, point public, jamais d'ordre.

    python -m app.backtest.research.ticks --symbol 1HZ75V --start 2026-07-11 --end 2026-08-01

Chaque page ne garde que les ticks de sa fenêtre : au-delà de son historique, Deriv renvoie ses
derniers prix au lieu d'une page vide (constat du 5 novembre 2026 sur les bougies). Fichier
écrit trié et sans doublon. La date de fin est exclue : jamais un tick du 1er août ou après.
"""

import argparse
import asyncio
import time
from array import array
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.backtest.fetch import _page
from app.broker.deriv import PUBLIC_WS_URL, DerivConnection
from app.broker.quotas import MemoryQuotaStore, QuotaManager

DATA_DIR = Path(".backtest/ticks")
PAGE_SECONDS = 900
PAUSE_SECONDS = 0.5


@dataclass(frozen=True)
class Ticks:
    epoch: "array[int]"
    price: "array[float]"

    def __len__(self) -> int:
        return len(self.epoch)


def path_of(directory: Path, symbol: str) -> Path:
    return directory / f"{symbol}.csv"


def load(path: Path, until: int | None = None) -> Ticks:
    """`until` exclu : la période réservée n'est jamais chargée."""
    ticks = Ticks(array("q"), array("d"))
    for row in path.read_text(encoding="ascii").splitlines():
        epoch_text, _, price = row.partition(",")
        if not price:
            continue
        epoch = int(epoch_text)
        if until is not None and epoch >= until:
            break
        if len(ticks) and epoch <= ticks.epoch[-1]:
            continue
        ticks.epoch.append(epoch)
        ticks.price.append(float(price))
    return ticks


def write(path: Path, rows: list[str], start: int, end: int) -> int:
    kept: dict[int, str] = {}
    for row in rows:
        epoch = int(row.split(",", 1)[0])
        if start <= epoch < end:
            kept[epoch] = row
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        "".join(f"{kept[e]}\n" for e in sorted(kept)), encoding="ascii", newline="\n"
    )
    temporary.replace(path)
    return len(kept)


async def download(symbol: str, start: int, end: int, directory: Path) -> int:
    async def url() -> str:
        return PUBLIC_WS_URL

    directory.mkdir(parents=True, exist_ok=True)
    connection = DerivConnection(
        url, QuotaManager(MemoryQuotaStore()), scope="research", uses_otp=False
    )
    await connection.start()
    await connection.wait_connected(60)
    rows: list[str] = []
    try:
        cursor = start
        while cursor < end:
            stop = min(cursor + PAGE_SECONDS - 1, end - 1)
            page = await _page(connection, symbol, cursor, stop)
            rows += [r for r in page if cursor <= int(r.split(",", 1)[0]) <= stop]
            cursor = stop + 1
            await asyncio.sleep(PAUSE_SECONDS)
    finally:
        await connection.stop()
    return write(path_of(directory, symbol), rows, start, end)


def _date(text: str) -> int:
    return int(datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.backtest.research.ticks")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True, help="AAAA-MM-JJ, UTC, inclus")
    parser.add_argument("--end", required=True, help="AAAA-MM-JJ, UTC, exclu")
    parser.add_argument("--directory", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    started = time.monotonic()
    count = asyncio.run(download(args.symbol, _date(args.start), _date(args.end), args.directory))
    print(f"{args.symbol} : {count} ticks, {time.monotonic() - started:.0f} s", flush=True)


if __name__ == "__main__":
    main()
