"""
Module de risque : fonctions pures, sans réseau. Tout ordre passe ici avant envoi.

Plages et plafonds : section 7, corrigée par q04 (mise minimale de 1 USD). Le plafond
administrateur réduit la plage client ; il deviendra modifiable à l'étape 5.5.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

D = Decimal

# Champ : (minimum, maximum retenu).
RANGES: dict[str, tuple[Decimal, Decimal]] = {
    "stake": (D("1"), D("50")),
    "multiplier": (D("1"), D("1000")),
    "capital_pct": (D("1"), D("25")),
    "max_positions": (D("1"), D("3")),
    "stop_loss_pct": (D("10"), D("100")),
    "session_target_pct": (D("0.5"), D("10")),
    "session_loss_pct": (D("0.5"), D("10")),
    "daily_target_pct": (D("0.5"), D("20")),
    "daily_loss_pct": (D("0.5"), D("10")),
    "max_consecutive_losses": (D("2"), D("10")),
    "pause_minutes": (D("5"), D("240")),
    "activation_r": (D("0.1"), D("10")),
    "locked_fraction": (D("0.1"), D("0.95")),
}
REAL_MAX_STAKE = D("10")
# Un stop loss n'est pas garanti au centime. Mesuré en démo : jusqu'à 12 % au-delà du niveau
# (0,03 sur 0,25 ; 0,05 sur 0,50), sur quelques contrats. Marge prudente, à revoir sur un
# grand échantillon.
SLIPPAGE_MARGIN = D("0.15")

# Défauts démo de la section 7. `multiplier`, `activation_r` et `locked_fraction` sont
# provisoires : non calibrés tant que le backtest ne les a pas validés (q18).
DEFAULTS: dict[str, Any] = {
    "stake": D("1"),
    "multiplier": 100,
    "capital_pct": D("20"),
    "max_positions": 1,
    "stop_loss_pct": D("50"),
    "session_target_pct": D("2"),
    "session_loss_pct": D("2"),
    "daily_target_pct": D("5"),
    "daily_loss_pct": D("5"),
    "max_consecutive_losses": 3,
    "pause_minutes": 15,
    "activation_r": D("1"),
    "locked_fraction": D("0.5"),
}


class RiskParams(Protocol):
    stake: Decimal
    multiplier: int
    capital_pct: Decimal
    max_positions: int
    stop_loss_pct: Decimal
    session_target_pct: Decimal
    session_loss_pct: Decimal
    daily_target_pct: Decimal
    daily_loss_pct: Decimal
    max_consecutive_losses: int
    pause_minutes: int
    activation_r: Decimal
    locked_fraction: Decimal


def out_of_range(values: dict[str, Any], *, real: bool = False) -> list[str]:
    """Champs hors plage. Un champ absent est refusé : aucune limite implicite."""
    bad = []
    for field, (low, high) in RANGES.items():
        value = values.get(field)
        if value is None:
            bad.append(field)
            continue
        ceiling = REAL_MAX_STAKE if real and field == "stake" else high
        if not low <= D(str(value)) <= ceiling:
            bad.append(field)
    return bad


def stop_amount(params: RiskParams) -> Decimal:
    return (params.stake * params.stop_loss_pct / 100).quantize(D("0.01"))


def worst_case_loss(stop_loss: Decimal) -> Decimal:
    """Perte à prévoir pour un stop donné, glissement compris."""
    return (stop_loss * (1 + SLIPPAGE_MARGIN)).quantize(D("0.01"))


@dataclass(frozen=True)
class OrderCheck:
    params: RiskParams
    stake: Decimal
    stop_loss: Decimal | None
    balance: Decimal
    start_balance: Decimal
    open_exposure: Decimal
    open_positions: int
    pending_orders: int
    session_net: Decimal
    day_net: Decimal
    day_start_balance: Decimal
    consecutive_losses: int
    paused_until: datetime | None
    now: datetime
    market_refusal: str | None
    account_kind: str
    real_enabled: bool
    symbol_allowed: bool
    connected: bool


def _limit(balance: Decimal, pct: Decimal) -> Decimal:
    return balance * pct / 100


def session_outcome(check: OrderCheck) -> str | None:
    """Limite atteinte : la perte passe avant l'objectif, la journée avant la session."""
    p = check.params
    if check.day_net <= -_limit(check.day_start_balance, p.daily_loss_pct):
        return "risk.daily_loss_limit"
    if check.session_net <= -_limit(check.start_balance, p.session_loss_pct):
        return "risk.session_loss_limit"
    if check.day_net >= _limit(check.day_start_balance, p.daily_target_pct):
        return "risk.daily_target"
    if check.session_net >= _limit(check.start_balance, p.session_target_pct):
        return "risk.session_target"
    return None


def order_refusal(check: OrderCheck) -> str | None:
    """Premier motif de refus, ou None. Chaque contrôle reste indépendant de l'interface."""
    p = check.params
    if check.account_kind != "demo" and not check.real_enabled:
        return "risk.real_account_disabled"
    if not check.connected:
        return "risk.not_connected"
    if not check.symbol_allowed:
        return "risk.symbol_not_allowed"
    if check.market_refusal:
        return check.market_refusal
    if check.pending_orders > 0:
        return "risk.order_pending"
    if check.paused_until is not None and check.now < check.paused_until:
        return "risk.paused"
    if check.consecutive_losses >= p.max_consecutive_losses:
        return "risk.consecutive_losses"
    outcome = session_outcome(check)
    if outcome:
        return outcome
    if check.open_positions >= p.max_positions:
        return "risk.max_positions"
    if check.stop_loss is None or check.stop_loss <= 0:
        return "risk.stop_loss_required"
    if check.stop_loss > check.stake:
        return "risk.stop_loss_above_stake"
    # Mise fixée par les paramètres : aucune martingale, aucune hausse après une perte.
    if check.stake != p.stake:
        return "risk.stake_changed"
    low, high = RANGES["stake"]
    if not low <= check.stake <= (REAL_MAX_STAKE if check.account_kind == "real" else high):
        return "risk.stake_out_of_range"
    if check.stake > check.balance:
        return "risk.insufficient_balance"
    if check.open_exposure + check.stake > _limit(check.balance, p.capital_pct):
        return "risk.capital_exposure"
    # Cette position, stoppée avec glissement, ne doit pas franchir une limite de perte.
    session_room = check.session_net + _limit(check.start_balance, p.session_loss_pct)
    day_room = check.day_net + _limit(check.day_start_balance, p.daily_loss_pct)
    if worst_case_loss(check.stop_loss) > min(session_room, day_room):
        return "risk.loss_room"
    return None


def proposal_refusal(proposal: dict[str, Any], stake: Decimal, stop_loss: Decimal) -> str | None:
    """Contrôle de ce que Deriv propose réellement, juste avant l'achat."""
    if proposal.get("commission") is None or proposal.get("ask_price") is None:
        return "risk.proposal_incomplete"
    if D(str(proposal["ask_price"])) > stake:
        return "risk.price_above_stake"
    bounds = (proposal.get("validation_params") or {}).get("stop_loss") or {}
    minimum, maximum = bounds.get("min"), bounds.get("max")
    if minimum is not None and stop_loss < D(str(minimum)):
        return "risk.stop_below_minimum"
    if maximum is not None and stop_loss > D(str(maximum)):
        return "risk.stop_above_maximum"
    return None
