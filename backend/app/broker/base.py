"""
Interface de broker : le moteur ne connaît que ce contrat, Deriv reste un détail remplaçable.

Sécurité des ordres, portée par la forme même de l'interface :
- `buy` ne prend qu'un identifiant de proposition, jamais de paramètres de contrat ;
- une issue incertaine lève `OrderOutcomeUnknownError` : l'appelant doit lire l'état réel
  (`statement`, `portfolio`) avant toute autre tentative.
"""

import enum
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

Message = dict[str, Any]
MessageHandler = Callable[[Message], Awaitable[None]]


class AccountKind(enum.StrEnum):
    PUBLIC = "public"
    DEMO = "demo"
    REAL = "real"


class BrokerError(Exception):
    pass


class ConnectionLostError(BrokerError):
    """La connexion est tombée. Pour un achat, voir `OrderOutcomeUnknownError`."""


class RequestTimeoutError(BrokerError):
    pass


class RealAccountDisabledError(BrokerError):
    """Règle absolue : aucun accès au compte réel sans activation explicite (phase 8)."""


class ApiRejectedError(BrokerError):
    """Refus explicite du broker : l'ordre n'a pas été exécuté."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}


class RateLimitedError(ApiRejectedError):
    """Deriv demande de ralentir : attendre avant de réessayer, sans jamais insister."""


class OrderOutcomeUnknownError(BrokerError):
    """
    L'ordre a été envoyé mais sa réponse manque : il a pu être exécuté ou non.
    Ne jamais le renvoyer : consulter d'abord `statement`.
    """

    def __init__(self, proposal_id: str, sent_at: float) -> None:
        super().__init__(f"issue inconnue pour la proposition {proposal_id}")
        self.proposal_id = proposal_id
        self.sent_at = sent_at


@dataclass(frozen=True)
class Purchase:
    contract_id: int
    buy_price: float
    balance_after: float
    transaction_id: int
    shortcode: str


class Subscription(Protocol):
    async def cancel(self) -> None: ...


class Broker(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def request(self, call: str, payload: Message) -> Message: ...
    async def subscribe(
        self, call: str, payload: Message, handler: MessageHandler
    ) -> Subscription: ...
    async def buy(self, proposal_id: str, max_price: float) -> Purchase: ...
