"""
Sorties dynamiques (q18) : décision pure, sans réseau.

Deriv refuse un stop loss en zone de gain. Deux niveaux donc : un plancher posé chez Deriv,
qui survit à une panne, et un cliquet exécuté par le moteur, qui ne vaut que s'il tourne.
Le niveau de sortie suit le gain le plus haut et ne recule jamais.
"""

from dataclasses import dataclass
from decimal import Decimal

D = Decimal
# Minimum observé en démo pour un stop loss : commission + 0,01 USD.
STOP_MARGIN = D("0.01")


@dataclass(frozen=True)
class ExitParams:
    activation_r: Decimal
    locked_fraction: Decimal


@dataclass(frozen=True)
class PositionView:
    profit: Decimal  # gain net selon Deriv, commission comprise
    peak_profit: Decimal
    commission: Decimal
    risk: Decimal  # 1 R : stop loss initial
    current_stop: Decimal | None
    # Minimum annoncé par Deriv dans un refus : il prime sur l'estimation.
    stop_minimum: Decimal | None = None


@dataclass(frozen=True)
class ExitAction:
    kind: str  # hold, tighten, sell
    stop_loss: Decimal | None = None
    reason: str | None = None


def activation_level(view: PositionView, params: ExitParams) -> Decimal:
    """Jamais avant d'avoir couvert les frais : un gain doit rester un gain une fois encaissé."""
    return max(view.risk * params.activation_r, view.commission * 2 + STOP_MARGIN)


def floor_stop(commission: Decimal) -> Decimal:
    return commission + STOP_MARGIN


def decide(view: PositionView, params: ExitParams) -> ExitAction:
    peak = max(view.peak_profit, view.profit)
    if peak >= activation_level(view, params):
        locked = peak * params.locked_fraction
        if view.profit <= locked:
            return ExitAction("sell", reason="ratchet")
    if view.profit > 0:
        floor = view.stop_minimum or floor_stop(view.commission)
        # Le stop ne s'éloigne jamais : seul un resserrement est envoyé.
        if view.current_stop is not None and floor < view.current_stop:
            return ExitAction("tighten", stop_loss=floor, reason="floor")
    return ExitAction("hold")
