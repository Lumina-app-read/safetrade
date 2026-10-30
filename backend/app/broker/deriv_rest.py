"""
API REST Deriv : comptes et OTP. Le jeton n'est jamais journalisé.

`otp_url` est l'unique point d'accès aux connexions authentifiées : le refus du compte
réel y est appliqué, et un jeton donne pourtant accès aux comptes démo ET réel.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.broker.base import AccountKind, BrokerError
from app.broker.deriv import ensure_account_allowed
from app.broker.quotas import Quota, QuotaManager

logger = logging.getLogger("safetrade.deriv")

BASE_URL = "https://api.derivws.com"
TIMEOUT = 15.0


class DerivAuthError(BrokerError):
    """Jeton refusé par Deriv : invalide, expiré ou révoqué."""


class DerivUnavailableError(BrokerError):
    pass


@dataclass(frozen=True)
class DerivAccount:
    account_id: str
    kind: AccountKind
    currency: str
    balance: str
    status: str


class DerivRest:
    def __init__(
        self,
        app_id: str,
        quotas: QuotaManager,
        *,
        real_account_enabled: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._app_id = app_id
        self._quotas = quotas
        self._real_account_enabled = real_account_enabled
        self._transport = transport

    async def _call(self, method: str, path: str, token: str, scope: str) -> dict[str, Any]:
        await self._quotas.wait(Quota.REST_IP, "server")
        await self._quotas.wait(Quota.REST_USER, scope)
        headers = {"Authorization": f"Bearer {token}", "Deriv-App-ID": self._app_id}
        try:
            async with httpx.AsyncClient(
                base_url=BASE_URL, timeout=TIMEOUT, transport=self._transport
            ) as client:
                response = await client.request(method, path, headers=headers)
        except httpx.HTTPError as exc:
            # Seul le type d'erreur est journalisé : l'exception peut citer la requête.
            logger.warning("appel REST Deriv en échec : %s", type(exc).__name__)
            raise DerivUnavailableError from None
        if response.status_code in (401, 403):
            raise DerivAuthError
        if response.status_code != 200:
            logger.warning("appel REST Deriv : HTTP %s", response.status_code)
            raise DerivUnavailableError
        payload: dict[str, Any] = response.json()
        return payload

    async def list_accounts(self, token: str, scope: str) -> list[DerivAccount]:
        payload = await self._call("GET", "/trading/v1/options/accounts", token, scope)
        return [
            DerivAccount(
                account_id=str(row["account_id"]),
                kind=AccountKind(row["account_type"]),
                currency=str(row["currency"]),
                balance=str(row["balance"]),
                status=str(row["status"]),
            )
            for row in payload["data"]
        ]

    async def otp_url(self, token: str, account: DerivAccount, scope: str) -> str:
        """Adresse WebSocket à usage unique, valable 120 s. Compte réel refusé (phase 8)."""
        ensure_account_allowed(account.kind, self._real_account_enabled)
        path = f"/trading/v1/options/accounts/{account.account_id}/otp"
        payload = await self._call("POST", path, token, scope)
        return str(payload["data"]["url"])
