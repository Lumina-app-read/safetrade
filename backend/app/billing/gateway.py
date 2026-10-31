"""
Interface commune de paiement, et Chariow (https://chariow.dev).

Chariow n'a pas de mode de test : toute vente est réelle. Une création de vente n'est jamais
renvoyée, car sa documentation ne prévoit pas de clé d'idempotence.
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx

from app.config import Settings
from app.errors import ApiError

logger = logging.getLogger("safetrade.billing")

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
class Quote:
    """Prix de référence de la formule (table `plans`), en général en USD."""

    amount: Decimal
    currency: str


@dataclass(frozen=True)
class Checkout:
    reference: str
    url: str
    product: str
    # Montant attendu par Chariow pour cette vente, dans la devise du produit.
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class PaymentState:
    """
    `status` : paid, failed, expired ou pending. `amount` et `currency` : devise du produit,
    seule base de contrôle. `payment_*` : ce que le client a payé dans sa devise.
    """

    status: str
    amount: Decimal
    currency: str
    reference: str = ""
    product: str = ""
    payment_amount: Decimal | None = None
    payment_currency: str | None = None


class GatewayUnavailableError(Exception):
    pass


class PaymentGateway(Protocol):
    name: str

    def supports(self, plan: str) -> bool: ...
    async def create_checkout(
        self, plan: str, payer: Payer, order_id: str, return_url: str | None, reference: Quote
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
    tolerance = settings.chariow_price_tolerance_pct
    return {"chariow": ChariowGateway(key, products, tolerance=tolerance)}


class ChariowGateway:
    name = "chariow"

    def __init__(
        self,
        api_key: str,
        products: dict[str, str],
        *,
        tolerance: Decimal = Decimal(10),
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        self._products = products
        self._tolerance = tolerance
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

    def _refuse(self, plan: str, reason: str) -> GatewayUnavailableError:
        logger.error(
            "produit Chariow refusé",
            extra={"event": "billing.product_refused", "plan": plan, "reason": reason},
        )
        return GatewayUnavailableError(reason)

    async def check_product(self, plan: str, reference: Quote) -> None:
        """
        Avant toute vente : le produit vendu doit correspondre à la formule. Chariow donne sa
        valeur en USD (`pricing.tracking`), ce qui compare un prix en CDF à un prix en USD.
        """
        response = await self._send("GET", f"/products/{self._products[plan]}", None)
        if response.status_code >= 300:
            raise GatewayUnavailableError
        product = response.json()["data"]
        pricing = product.get("pricing") or {}
        if product.get("status") != "published":
            raise self._refuse(plan, "not_published")
        if product.get("type") != "license":
            raise self._refuse(plan, "not_license")
        if pricing.get("type") != "one_time" or product.get("has_variant_pricing"):
            raise self._refuse(plan, "pricing_type")
        price = pricing.get("current_price") or {}
        tracking = pricing.get("tracking") or {}
        if price.get("currency") == reference.currency:
            value = Decimal(str(price.get("value", 0)))
        elif tracking.get("currency") == reference.currency:
            value = Decimal(str(tracking.get("value", 0)))
        else:
            # Taux indisponible : impossible de comparer, donc pas de vente.
            raise self._refuse(plan, "no_conversion")
        margin = reference.amount * self._tolerance / 100
        if abs(value - reference.amount) > margin:
            raise self._refuse(plan, "price_mismatch")

    async def create_checkout(
        self, plan: str, payer: Payer, order_id: str, return_url: str | None, reference: Quote
    ) -> Checkout:
        await self.check_product(plan, reference)
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
        amount = purchase.get("amount") or {}
        if amount.get("value") is None or not amount.get("currency"):
            raise self._refuse(plan, "no_amount")
        return Checkout(
            reference=str(purchase["id"]),
            url=str(url),
            product=self._products[plan],
            amount=Decimal(str(amount["value"])),
            currency=str(amount["currency"]),
        )

    async def fetch_payment(self, reference: str) -> PaymentState:
        response = await self._send("GET", f"/sales/{reference}", None)
        if response.status_code >= 300:
            raise GatewayUnavailableError
        sale = response.json()["data"]
        amount = sale.get("amount") or {}
        payment = sale.get("payment") or {}
        paid = payment.get("amount") or {}
        raw = sale.get("status")
        # Vente terminée et paiement confirmé par la passerelle : les deux, sinon rien.
        confirmed = (
            raw in PAID_STATES
            and payment.get("status") == "success"
            and not sale.get("is_access_revoked")
        )
        status = (
            "paid"
            if confirmed
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
            reference=str(sale.get("id", "")),
            product=str((sale.get("product") or {}).get("id", "")),
            payment_amount=Decimal(str(paid["value"])) if paid.get("value") is not None else None,
            payment_currency=paid.get("currency"),
        )
