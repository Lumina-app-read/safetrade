"""Abonnements et Chariow : base réelle, Chariow simulé. Aucune vente réelle n'est créée."""

import asyncio
import hashlib
import hmac
import json
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.billing import notices, service
from app.billing.gateway import (
    ChariowGateway,
    GatewayUnavailableError,
    Payer,
    PaymentState,
    Quote,
    valid_signature,
)
from app.billing.router import reconcile
from app.config import Settings
from app.db.models import PaymentEvent, PaymentOrder, Plan, Subscription, User, UserStatus
from app.errors import ApiError
from app.main import create_app
from tests.conftest import requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"
SECRET = "whsec_test"
PRODUCTS = {"weekly": "prd_w", "monthly": "prd_m", "annual": "prd_a"}
PAYER = Payer("a@example.com", "Ada", "Lovelace", "243970000000", "CD", None)
NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)


def test_signature_uses_the_raw_body() -> None:
    body = b'{"event":"successful.sale"}'
    good = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert valid_signature(body, good, SECRET)
    assert not valid_signature(body + b" ", good, SECRET)
    assert not valid_signature(body, "sha256=00", SECRET)
    assert not valid_signature(body, None, SECRET)


class FakeChariow:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.product: dict[str, Any] = {
            "status": "published",
            "type": "license",
            "has_variant_pricing": False,
            "pricing": {
                "type": "one_time",
                "current_price": {"value": 35000, "currency": "CDF"},
                "tracking": {"currency": "USD", "value": 15.1},
            },
        }
        self.checkout: tuple[int, dict[str, Any]] = (
            201,
            {
                "data": {
                    "step": "payment",
                    "purchase": {"id": "sal_1", "amount": {"value": 35000, "currency": "CDF"}},
                    "payment": {"checkout_url": "https://pay.chariow.test/1"},
                }
            },
        )
        self.sale: dict[str, Any] = {
            "status": "completed",
            "amount": {"value": 35000, "currency": "CDF"},
            "payment": {"status": "success", "amount": {"value": 7600, "currency": "XOF"}},
            "product": {"id": "prd_m"},
        }
        self.down = False
        self.sale_id = "sal_1"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("coupé")
        if "/products/" in request.url.path:
            return httpx.Response(200, json={"data": self.product})
        if request.method == "POST":
            body = json.loads(json.dumps(self.checkout[1]))
            if (body.get("data") or {}).get("purchase"):
                body["data"]["purchase"]["id"] = self.sale_id = f"sal_{uuid.uuid4().hex[:10]}"
            return httpx.Response(self.checkout[0], json=body)
        return httpx.Response(200, json={"data": {"id": self.sale_id, **self.sale}})


REFERENCE = Quote(Decimal(15), "USD")


def gateway(fake: FakeChariow) -> ChariowGateway:
    return ChariowGateway("sk_test", PRODUCTS, transport=httpx.MockTransport(fake))


def test_checkout_sends_order_and_never_a_second_time() -> None:
    fake = FakeChariow()
    result = asyncio.run(gateway(fake).create_checkout("monthly", PAYER, "ord-1", None, REFERENCE))
    assert (result.reference, result.url) == (fake.sale_id, "https://pay.chariow.test/1")
    assert (result.amount, result.currency, result.product) == (Decimal(35000), "CDF", "prd_m")
    sent = json.loads(fake.requests[1].content)
    assert sent["product_id"] == "prd_m"
    assert sent["custom_metadata"] == {"order_id": "ord-1"}
    assert sent["phone"] == {"number": "243970000000", "country_code": "CD"}
    assert fake.requests[1].headers["authorization"] == "Bearer sk_test"
    assert [r.method for r in fake.requests] == ["GET", "POST"]


def test_refused_phone_and_already_purchased_are_clear() -> None:
    fake = FakeChariow()
    fake.checkout = (400, {"message": "x", "errors": {"phone": ["bad"]}})
    with pytest.raises(ApiError) as refused:
        asyncio.run(
            gateway(fake).create_checkout("weekly", PAYER, "o", None, Quote(Decimal(15), "USD"))
        )
    assert refused.value.code == "billing.invalid_phone"
    fake.checkout = (201, {"data": {"step": "already_purchased", "purchase": None}})
    with pytest.raises(ApiError) as bought:
        asyncio.run(
            gateway(fake).create_checkout("weekly", PAYER, "o", None, Quote(Decimal(15), "USD"))
        )
    assert bought.value.code == "billing.checkout_refused"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("completed", "paid"),
        ("settled", "paid"),
        ("failed", "failed"),
        ("abandoned", "expired"),
        ("awaiting_payment", "pending"),
    ],
)
def test_sale_statuses(raw: str, expected: str) -> None:
    fake = FakeChariow()
    fake.sale["status"] = raw
    assert asyncio.run(gateway(fake).fetch_payment("sal_1")).status == expected


def test_network_failure_is_reported() -> None:
    fake = FakeChariow()
    fake.down = True
    with pytest.raises(GatewayUnavailableError):
        asyncio.run(gateway(fake).fetch_payment("sal_1"))


pytestmark_db = requires_db


@pytest.fixture
def factory(migrated_engine: Engine) -> sessionmaker[Any]:
    return sessionmaker(migrated_engine, expire_on_commit=False)


def make_user(factory: sessionmaker[Any]) -> User:
    with factory.begin() as db:
        user = User(email=f"{uuid.uuid4().hex}@example.com", password_hash="x", first_name="Ada")
        db.add(user)
        db.flush()
        return user


def pending_order(factory: sessionmaker[Any], user: User, plan: str = "monthly") -> uuid.UUID:
    with factory.begin() as db:
        order = service.create_order(db, user, db.get_one(Plan, plan), "chariow")
        order.provider_ref = f"sal_{uuid.uuid4().hex[:8]}"
        order.product_ref = "prd_m"
        order.expected_amount = Decimal(35000)
        order.expected_currency = "CDF"
        return order.id


def paid_state(factory: sessionmaker[Any], order_id: uuid.UUID, **changes: Any) -> PaymentState:
    with factory() as db:
        reference = db.get_one(PaymentOrder, order_id).provider_ref or ""
    values: dict[str, Any] = {
        "status": "paid",
        "amount": Decimal(35000),
        "currency": "CDF",
        "reference": reference,
        "product": "prd_m",
        "payment_amount": Decimal(7600),
        "payment_currency": "XOF",
    }
    return PaymentState(**{**values, **changes})


@requires_db
def test_new_account_has_no_access_until_trial(factory: sessionmaker[Any]) -> None:
    user = make_user(factory)
    with factory.begin() as db:
        assert service.access_of(db, user).status == "none"
        service.grant_trial(db, user, NOW)
    with factory() as db:
        inside = service.access_of(db, user, NOW + timedelta(days=2, hours=23))
        assert (inside.status, inside.allowed) == ("trial", True)
        after = service.access_of(db, user, NOW + timedelta(days=3))
        assert (after.status, after.allowed) == ("expired", False)


@requires_db
def test_trial_is_given_only_once(factory: sessionmaker[Any]) -> None:
    user = make_user(factory)
    with factory.begin() as db:
        service.grant_trial(db, user, NOW)
    with factory.begin() as db:
        service.grant_trial(db, user, NOW + timedelta(days=30))
    with factory() as db:
        rows = db.scalars(select(Subscription).where(Subscription.user_id == user.id)).all()
        assert len(rows) == 1
    with pytest.raises(IntegrityError), factory.begin() as db:
        db.add(Subscription(user_id=user.id, plan_code="trial", starts_at=NOW, ends_at=NOW))


@requires_db
def test_suspended_account_has_no_access(factory: sessionmaker[Any]) -> None:
    user = make_user(factory)
    with factory.begin() as db:
        service.grant_trial(db, user)
        db.get_one(User, user.id).status = UserStatus.SUSPENDED
    with factory() as db:
        row = db.get_one(User, user.id)
        assert service.access_of(db, row).status == "suspended"


@requires_db
def test_payment_extends_from_the_current_end_and_only_once(factory: sessionmaker[Any]) -> None:
    user = make_user(factory)
    with factory.begin() as db:
        service.grant_trial(db, user, NOW)
    order_id = pending_order(factory, user)
    state = paid_state(factory, order_id)
    with factory.begin() as db:
        granted = service.settle(db, order_id, state, NOW)
        assert granted is not None
        assert granted.ends_at == NOW + timedelta(days=33)
    with factory.begin() as db:
        assert service.settle(db, order_id, state, NOW) is None
    with factory() as db:
        rows = db.scalars(select(Subscription).where(Subscription.order_id == order_id)).all()
        assert len(rows) == 1
        assert service.access_of(db, user, NOW + timedelta(days=4)).plan == "monthly"


@requires_db
def test_local_currency_payment_is_accepted_on_the_product_currency(
    factory: sessionmaker[Any],
) -> None:
    user = make_user(factory)
    order_id = pending_order(factory, user)
    state = paid_state(factory, order_id)
    with factory.begin() as db:
        assert service.settle(db, order_id, state, NOW) is not None
    with factory() as db:
        order = db.get_one(PaymentOrder, order_id)
        assert (order.status, order.paid_amount, order.paid_currency) == (
            "paid",
            Decimal(7600),
            "XOF",
        )


@requires_db
@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"amount": Decimal(34999)}, "amount_too_low"),
        ({"currency": "USD", "amount": Decimal(35000)}, "wrong_currency"),
        ({"product": "prd_autre"}, "wrong_product"),
        ({"reference": "sal_autre"}, "wrong_sale"),
    ],
)
def test_any_mismatch_grants_nothing(
    factory: sessionmaker[Any], changes: dict[str, Any], reason: str
) -> None:
    user = make_user(factory)
    order_id = pending_order(factory, user)
    state = paid_state(factory, order_id, **changes)
    with factory.begin() as db:
        assert service.mismatch(db.get_one(PaymentOrder, order_id), state) == reason
        assert service.settle(db, order_id, state, NOW) is None
    with factory() as db:
        assert db.get_one(PaymentOrder, order_id).status == "partial"
        assert service.latest(db, user.id) is None


@pytest.mark.parametrize(
    ("change", "allowed"),
    [
        ({}, True),
        ({"status": "draft"}, False),
        ({"type": "downloadable"}, False),
        ({"has_variant_pricing": True}, False),
    ],
)
def test_product_is_checked_before_any_sale(change: dict[str, Any], allowed: bool) -> None:
    fake = FakeChariow()
    fake.product.update(change)
    run = gateway(fake).create_checkout("monthly", PAYER, "o", None, REFERENCE)
    if allowed:
        asyncio.run(run)
    else:
        with pytest.raises(GatewayUnavailableError):
            asyncio.run(run)
        assert [r.method for r in fake.requests] == ["GET"]


@pytest.mark.parametrize(
    ("price", "tracking", "allowed"),
    [
        ({"value": 15, "currency": "USD"}, {"currency": "USD", "value": 15}, True),
        ({"value": 34000, "currency": "CDF"}, {"currency": "USD", "value": 14.8}, True),
        ({"value": 11500, "currency": "CDF"}, {"currency": "USD", "value": 4.98}, False),
        ({"value": 35000, "currency": "CDF"}, {"currency": "CDF", "value": 35000}, False),
    ],
)
def test_product_price_must_match_the_plan(
    price: dict[str, Any], tracking: dict[str, Any], allowed: bool
) -> None:
    fake = FakeChariow()
    fake.product["pricing"].update(current_price=price, tracking=tracking)
    check = gateway(fake).check_product("monthly", REFERENCE)
    if allowed:
        asyncio.run(check)
    else:
        with pytest.raises(GatewayUnavailableError):
            asyncio.run(check)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({}, "paid"),
        ({"payment": {"status": "pending"}}, "pending"),
        ({"payment": None}, "pending"),
        ({"is_access_revoked": True}, "pending"),
    ],
)
def test_completed_sale_needs_a_confirmed_payment(change: dict[str, Any], expected: str) -> None:
    fake = FakeChariow()
    fake.sale.update(change)
    assert asyncio.run(gateway(fake).fetch_payment("sal_1")).status == expected


@requires_db
def test_price_change_does_not_touch_an_open_order(factory: sessionmaker[Any]) -> None:
    user = make_user(factory)
    order_id = pending_order(factory, user)
    with factory.begin() as db:
        plan = db.get_one(Plan, "monthly")
        before = plan.price
        plan.price = Decimal(99)
    with factory() as db:
        assert db.get_one(PaymentOrder, order_id).amount == before
    with factory.begin() as db:
        db.get_one(Plan, "monthly").price = before


@requires_db
def test_events_cannot_be_rewritten(factory: sessionmaker[Any]) -> None:
    with factory.begin() as db:
        db.add(
            PaymentEvent(
                provider="chariow", delivery_id=uuid.uuid4().hex, event="x", reference="sal"
            )
        )
    with pytest.raises(DBAPIError), factory.begin() as db:
        db.execute(text("DELETE FROM payment_events"))


class StubGateway:
    name = "chariow"

    def __init__(self, state: PaymentState | None) -> None:
        self.state = state
        self.reference = ""

    def supports(self, plan: str) -> bool:
        return True

    async def fetch_payment(self, reference: str) -> PaymentState:
        if self.state is None:
            raise GatewayUnavailableError
        return replace(self.state, reference=reference)

    async def create_checkout(self, *_: Any) -> Any:
        raise AssertionError


@requires_db
def test_lost_webhook_is_recovered_by_reconciliation_once(factory: sessionmaker[Any]) -> None:
    user = make_user(factory)
    order_id = pending_order(factory, user)
    mailer = MemoryMailer()
    settings = Settings(environment="test")
    later = datetime.now(UTC) + timedelta(minutes=10)
    stub: Any = StubGateway(paid_state(factory, order_id))
    for _ in range(2):
        asyncio.run(reconcile(factory, stub, mailer, settings, later))
    with factory() as db:
        assert db.get_one(PaymentOrder, order_id).status == "paid"
        rows = db.scalars(select(Subscription).where(Subscription.order_id == order_id)).all()
        assert len(rows) == 1
    assert [m.template for m in mailer.sent if m.to == user.email] == ["payment_received"]


@requires_db
def test_recent_order_is_left_alone_and_old_one_expires(factory: sessionmaker[Any]) -> None:
    user = make_user(factory)
    order_id = pending_order(factory, user)
    stub: Any = StubGateway(PaymentState("pending", Decimal(0), ""))
    mailer = MemoryMailer()
    settings = Settings(environment="test")
    asyncio.run(reconcile(factory, stub, mailer, settings, datetime.now(UTC)))
    with factory() as db:
        assert db.get_one(PaymentOrder, order_id).status == "pending"
    late = datetime.now(UTC) + timedelta(hours=25)
    asyncio.run(reconcile(factory, stub, mailer, settings, late))
    with factory() as db:
        assert db.get_one(PaymentOrder, order_id).status == "expired"


@requires_db
def test_expiry_reminder_is_sent_once(factory: sessionmaker[Any]) -> None:
    user = make_user(factory)
    now = datetime.now(UTC) + timedelta(days=3650)
    with factory.begin() as db:
        db.add(
            Subscription(
                user_id=user.id,
                plan_code="weekly",
                starts_at=now,
                ends_at=now + timedelta(hours=20),
            )
        )
    mailer = MemoryMailer()
    settings = Settings(environment="test")
    notices.remind_expiring(factory, mailer, settings, now)
    notices.remind_expiring(factory, mailer, settings, now)
    assert [m.template for m in mailer.sent if m.to == user.email] == ["subscription_expiring"]


@pytest.fixture
def api(migrated_engine: Engine) -> Iterator[tuple[TestClient, MemoryMailer, FakeChariow, str]]:
    mailer = MemoryMailer()
    fake = FakeChariow()
    app = create_app(
        Settings(
            environment="test",
            session_cookie_secure=False,
            allowed_origins=[ORIGIN],
            chariow_webhook_secret=SECRET,
        ),
        session_factory=sessionmaker(migrated_engine, expire_on_commit=False),
        mailer=mailer,
        failures=MemoryFailureCounter(),
    )
    app.state.gateways = {"chariow": gateway(fake)}
    app.state.fake_chariow = fake
    with TestClient(app, base_url="http://127.0.0.1:18000", headers={"origin": ORIGIN}) as client:
        email = f"bill-{uuid.uuid4().hex[:8]}@example.com"
        client.post(
            "/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "first_name": "Ada",
                "locale": "fr",
                "accept_risk": True,
            },
        )
        token = mailer.sent[-1].body.split("token=")[1].split()[0]
        assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
        client.post("/auth/login", json={"email": email, "password": PASSWORD})
        yield client, mailer, fake, email


BUY = {
    "plan": "monthly",
    "last_name": "Lovelace",
    "phone_number": "243970000000",
    "phone_country": "CD",
}


def fake_of(client: TestClient) -> FakeChariow:
    app: Any = client.app
    fake: FakeChariow = app.state.fake_chariow
    return fake


def pulse(
    client: TestClient, order: str, event: str = "successful.sale", delivery: str | None = None,
    secret: str = SECRET, reference: str | None = None,
) -> httpx.Response:  # fmt: skip
    body = json.dumps(
        {
            "event": event,
            "sale": {
                "id": reference or fake_of(client).sale_id,
                "amount": {"value": 15, "currency": "USD"},
                "custom_metadata": {"order_id": order},
            },
        }
    ).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    response: httpx.Response = client.post(
        "/billing/webhooks/chariow",
        content=body,
        headers={
            "x-chariow-signature": signature,
            "x-pulse-delivery-id": delivery or uuid.uuid4().hex,
            "x-pulse-event": event,
            "origin": "",
        },
    )
    return response


@requires_db
def test_verified_email_opens_the_trial(api: Any) -> None:
    client, _, _, _ = api
    data = client.get("/billing/me").json()
    assert (data["access"]["status"], data["access"]["allowed"]) == ("trial", True)
    assert [p["code"] for p in data["plans"]] == ["weekly", "monthly", "annual"]
    assert data["plans"][1]["providers"] == ["chariow"]
    user = client.get("/auth/me").json()["user"]
    assert (user["subscription"], user["access"]) == ("trial", True)


@requires_db
def test_full_payment_flow_through_webhook(api: Any) -> None:
    client, mailer, _, _ = api
    bought = client.post("/billing/checkout", json=BUY)
    assert bought.status_code == 201
    assert bought.json()["checkout_url"] == "https://pay.chariow.test/1"
    order = bought.json()["order"]
    # Retour du navigateur sans notification : rien n'est activé.
    assert client.get("/billing/me").json()["access"]["plan"] == "trial"
    delivery = uuid.uuid4().hex
    assert pulse(client, order, delivery=delivery).json() == {"status": "processed"}
    assert pulse(client, order, delivery=delivery).json() == {"status": "duplicate"}
    assert pulse(client, order).json() == {"status": "processed"}  # rejeu : nouvel identifiant
    data = client.get("/billing/me").json()
    assert (data["access"]["status"], data["access"]["plan"]) == ("active", "monthly")
    assert data["orders"][0]["status"] == "paid"
    assert sum(m.template == "payment_received" for m in mailer.sent) == 1


@requires_db
def test_forged_pulse_is_refused_and_grants_nothing(api: Any) -> None:
    client, _, _, _ = api
    order = client.post("/billing/checkout", json=BUY).json()["order"]
    response = pulse(client, order, secret="whsec_faux")
    assert (response.status_code, response.json()["error"]) == (401, "billing.bad_signature")
    assert client.get("/billing/me").json()["orders"][0]["status"] == "pending"


@requires_db
def test_pulse_claiming_payment_is_checked_at_chariow(api: Any) -> None:
    client, _, fake, _ = api
    order = client.post("/billing/checkout", json=BUY).json()["order"]
    fake.sale["status"] = "failed"
    pulse(client, order)
    assert client.get("/billing/me").json()["access"]["plan"] == "trial"


@requires_db
def test_chariow_down_during_pulse_lets_it_retry(api: Any) -> None:
    client, _, fake, _ = api
    order = client.post("/billing/checkout", json=BUY).json()["order"]
    fake.down = True
    delivery = uuid.uuid4().hex
    assert pulse(client, order, delivery=delivery).status_code == 503
    fake.down = False
    assert pulse(client, order, delivery=delivery).json() == {"status": "processed"}
    assert client.get("/billing/me").json()["access"]["plan"] == "monthly"


@requires_db
def test_reopened_sale_is_still_credited(api: Any) -> None:
    client, _, _, _ = api
    bought = client.post("/billing/checkout", json=BUY).json()
    pulse(client, bought["order"], event="failed.sale")
    assert client.get("/billing/me").json()["orders"][0]["status"] == "failed"
    pulse(client, bought["order"])
    assert client.get("/billing/me").json()["access"]["plan"] == "monthly"


@requires_db
def test_full_flow_with_payment_in_local_currency(api: Any) -> None:
    client, mailer, _, _ = api
    bought = client.post("/billing/checkout", json=BUY).json()
    assert pulse(client, bought["order"]).json() == {"status": "processed"}
    assert client.get("/billing/me").json()["access"]["status"] == "active"
    receipt = next(m for m in mailer.sent if m.template == "payment_received")
    assert "7600.00 XOF" in receipt.body


@requires_db
def test_failed_sale_and_dashboard_test_pulse(api: Any) -> None:
    client, _, _, _ = api
    order = client.post("/billing/checkout", json=BUY).json()["order"]
    assert pulse(client, order, reference="test_1").json() == {"status": "ignored"}
    pulse(client, order, event="failed.sale")
    assert client.get("/billing/me").json()["orders"][0]["status"] == "failed"


@requires_db
@pytest.mark.parametrize(
    "change",
    [{"phone_number": "12a"}, {"phone_country": "fr"}, {"plan": "trial"}, {"last_name": ""}],
)
def test_checkout_input_is_validated(api: Any, change: dict[str, str]) -> None:
    client, _, fake, _ = api
    assert client.post("/billing/checkout", json={**BUY, **change}).status_code == 422
    assert fake.requests == []


@requires_db
def test_unavailable_provider_closes_the_order(api: Any) -> None:
    client, _, fake, _ = api
    fake.down = True
    response = client.post("/billing/checkout", json=BUY)
    assert (response.status_code, response.json()["error"]) == (503, "billing.provider_unavailable")
    assert client.get("/billing/me").json()["orders"][0]["status"] == "failed"
