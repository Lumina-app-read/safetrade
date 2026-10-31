"""
Interface commune de paiement, et Chariow (https://chariow.dev).

Chariow n'a pas de mode de test : toute vente est réelle. Une création de vente n'est jamais
renvoyée, car sa documentation ne prévoit pas de clé d'idempotence.
"""

import hashlib
import hmac
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx

from app.config import Settings
from app.errors import ApiError

CHARIOW_API = "https://api.chariow.com/v1"
TIMEOUT_SECONDS = 15.0
PAID_STATES = frozenset({"completed", "settled"})


@dataclass(frozen=True)
class Payer:
    email: str
    first_name: str
    last_name: str
    phone_number: str
    phone_country: str
    ip: str | None


@dataclass(frozen=True)
class Checkout:
    reference: str
    url: str


@dataclass(frozen=True)
class PaymentState:
    """`status` : paid, failed, expired ou pending."""

    status: str
    amount: Decimal
    currency: str


class GatewayUnavailableError(Exception):
    pass


class PaymentGateway(Protocol):
    name: str

    def supports(self, plan: str) -> bool: ...
    async def create_checkout(
        self, plan: str, payer: Payer, order_id: str, return_url: str | None
    ) -> Checkout: ...
    async def fetch_payment(self, reference: str) -> PaymentState: ...


def valid_signature(raw_body: bytes, header: str | None, secret: str) -> bool:
    """Seul le corps brut est signé : jamais le JSON relu puis réécrit."""
    if not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header, expected)


def build_gateways(settings: Settings) -> dict[str, PaymentGateway]:
    """Sans clé, aucun fournisseur : le paiement reste désactivé, jamais simulé."""
    key = settings.chariow_api_key.get_secret_value() if settings.chariow_api_key else ""
    if not key:
        return {}
    products = {
        "weekly": settings.chariow_product_weekly or "",
        "monthly": settings.chariow_product_monthly or "",
        "annual": settings.chariow_product_annual or "",
    }
    return {"chariow": ChariowGateway(key, products)}


class ChariowGateway:
    name = "chariow"

    def __init__(
        self,
        api_key: str,
        products: dict[str, str],
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        self._products = products
        self._transport = transport

    def supports(self, plan: str) -> bool:
        return bool(self._products.get(plan))

    async def _send(self, method: str, path: str, body: dict[str, Any] | None) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url=CHARIOW_API, timeout=TIMEOUT_SECONDS, transport=self._transport
        ) as client:
            try:
                return await client.request(method, path, json=body, headers=self._headers)
            except httpx.HTTPError as exc:
                raise GatewayUnavailableError from exc

    async def create_checkout(
        self, plan: str, payer: Payer, order_id: str, return_url: str | None
    ) -> Checkout:
        body: dict[str, Any] = {
            "product_id": self._products[plan],
            "email": payer.email,
            "first_name": payer.first_name[:50],
            "last_name": payer.last_name[:50],
            "phone": {"number": payer.phone_number, "country_code": payer.phone_country},
            "custom_metadata": {"order_id": order_id},
        }
        if return_url:
            body["redirect_url"] = return_url
        if payer.ip:
            body["customer_ip"] = payer.ip
        response = await self._send("POST", "/checkout", body)
        if response.status_code in (400, 422):
            errors = response.json().get("errors") or {}
            code = "billing.invalid_phone" if "phone" in str(errors) else "billing.checkout_refused"
            raise ApiError(422, code)
        if response.status_code >= 300:
            raise GatewayUnavailableError
        data = response.json()["data"]
        url = (data.get("payment") or {}).get("checkout_url")
        purchase = data.get("purchase") or {}
        if data.get("step") != "payment" or not url or not purchase.get("id"):
            # already_purchased : le produit Chariow doit être de type licence, renouvelable.
            raise ApiError(409, "billing.checkout_refused")
        return Checkout(reference=str(purchase["id"]), url=str(url))

    async def fetch_payment(self, reference: str) -> PaymentState:
        response = await self._send("GET", f"/sales/{reference}", None)
        if response.status_code >= 300:
            raise GatewayUnavailableError
        sale = response.json()["data"]
        amount = sale.get("amount") or {}
        raw = sale.get("status")
        status = (
            "paid"
            if raw in PAID_STATES
            else "failed"
            if raw == "failed"
            else "expired"
            if raw == "abandoned"
            else "pending"
        )
        return PaymentState(
            status=status,
            amount=Decimal(str(amount.get("value", 0))),
            currency=str(amount.get("currency", "")),
        )
