"""
Contrôles globaux du trading, fixés dans l'administration et appliqués par le moteur.

Ils s'ajoutent au module de risque, jamais à sa place : un plafond global ne peut que réduire
ce que les réglages du client permettent. Valeurs gardées dans `site_settings`, chaque
modification est inscrite au journal d'audit.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session as DbSession

from app.db.models import SiteSetting

KEY = "trading_controls"


@dataclass(frozen=True)
class Controls:
    # Arrêt d'urgence global : aucun démarrage, aucune nouvelle position, bots arrêtés.
    halted: bool = False
    max_stake: Decimal | None = None
    max_positions: int | None = None
    disabled_symbols: tuple[str, ...] = field(default_factory=tuple)

    def view(self) -> dict[str, object]:
        data = asdict(self)
        data["max_stake"] = None if self.max_stake is None else str(self.max_stake)
        data["disabled_symbols"] = list(self.disabled_symbols)
        return data


def read(db: DbSession) -> Controls:
    row = db.get(SiteSetting, KEY)
    if row is None:
        return Controls()
    raw = json.loads(row.value)
    stake = raw.get("max_stake")
    return Controls(
        halted=bool(raw.get("halted", False)),
        max_stake=None if stake is None else Decimal(str(stake)),
        max_positions=raw.get("max_positions"),
        disabled_symbols=tuple(raw.get("disabled_symbols", ())),
    )


def write(db: DbSession, controls: Controls, by: uuid.UUID) -> None:
    value = json.dumps(controls.view())
    row = db.get(SiteSetting, KEY)
    if row is None:
        db.add(SiteSetting(key=KEY, value=value, updated_by=by))
    else:
        row.value, row.updated_by = value, by


def entry_refusal(
    controls: Controls, *, symbol: str, stake: Decimal, open_positions: int
) -> str | None:
    """Motif de refus d'une nouvelle position, ou None."""
    if controls.halted:
        return "risk.global_halt"
    if symbol in controls.disabled_symbols:
        return "risk.symbol_disabled"
    if controls.max_stake is not None and stake > controls.max_stake:
        return "risk.global_max_stake"
    if controls.max_positions is not None and open_positions >= controls.max_positions:
        return "risk.global_max_positions"
    return None
