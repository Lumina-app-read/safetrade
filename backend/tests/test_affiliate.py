"""Affiliation : base réelle, paiements validés par `settle`. Aucun appel à Chariow."""

import re
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.affiliate import service
from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.billing import service as billing
from app.billing.gateway import Checkout, PaymentState
from app.config import Settings
from app.db.models import (
    Affiliate,
    AffiliateCommission,
    AffiliateProgram,
    AuditLog,
    PaymentOrder,
    Plan,
    Referral,
    Session,
    User,
    UserRole,
)
from app.errors import ApiError
from app.main import create_app
from tests.conftest import requires_db
from tests.test_authz import KEY, ORIGIN, PASSWORD, enable_mfa, signed_up

NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
LETTER = {"message": "Je présente SafeTrade à ma communauté.", "payout_details": "USDT TRC20 TXabc"}


@pytest.mark.parametrize(
    ("first", "second", "same"),
    [
        ("Ada.Love+promo@gmail.com", "adalove@googlemail.com", True),
        ("ada+1@example.com", "ADA@example.com", True),
        ("ada.love@example.com", "adalove@example.com", False),
        ("ada@example.com", "ada@example.org", False),
    ],
)
def test_same_identity(first: str, second: str, same: bool) -> None:
    assert (service.identity(first) == service.identity(second)) is same


def test_fingerprint_hides_the_number_and_depends_on_the_key() -> None:
    one = Settings(environment="test", encryption_key="a" * 44)
    two = Settings(environment="test", encryption_key="b" * 44)
    assert service.fingerprint(one, "243970000000") == service.fingerprint(one, "243970000000")
    assert service.fingerprint(one, "243970000000") != service.fingerprint(two, "243970000000")
    assert b"243970000000" not in service.fingerprint(one, "243970000000")


@pytest.fixture
def factory(migrated_engine: Engine) -> sessionmaker[Any]:
    return sessionmaker(migrated_engine, expire_on_commit=False)


@pytest.fixture
def rules(factory: sessionmaker[Any]) -> Iterator[Callable[..., None]]:
    def change(**values: Any) -> None:
        with factory.begin() as db:
            row = db.get_one(AffiliateProgram, 1)
            for name, value in values.items():
                setattr(row, name, value)

    yield change
    change(rate_pct=Decimal(20), recurring=False, attribution_days=30, hold_days=14)


def make_user(factory: sessionmaker[Any], email: str | None = None) -> User:
    with factory.begin() as db:
        user = User(
            email=email or f"{uuid.uuid4().hex}@example.com", password_hash="x", first_name="Ada"
        )
        db.add(user)
        db.flush()
        return user


def make_affiliate(factory: sessionmaker[Any], status: str = "approved") -> Affiliate:
    owner = make_user(factory)
    with factory.begin() as db:
        row = Affiliate(
            user_id=owner.id,
            status=status,
            code=uuid.uuid4().hex[:8].upper(),
            message="m",
            payout_details="p",
            terms_accepted_at=NOW,
        )
        db.add(row)
        return row


def referred(
    factory: sessionmaker[Any],
    affiliate: Affiliate,
    *,
    ip: str | None = None,
    device: bytes | None = None,
    email: str | None = None,
) -> User:
    user = make_user(factory, email)
    with factory.begin() as db:
        service.attribute(db, user, affiliate, ip, device, NOW)
    return user


def order_for(
    factory: sessionmaker[Any], user: User, plan: str = "monthly", payer: bytes | None = None
) -> uuid.UUID:
    with factory.begin() as db:
        order = billing.create_order(db, user, db.get_one(Plan, plan), "chariow", payer)
        order.provider_ref = f"sal_{uuid.uuid4().hex[:8]}"
        order.product_ref = "prd_m"
        order.expected_amount = order.amount
        order.expected_currency = order.currency
        return order.id


def state_of(factory: sessionmaker[Any], order_id: uuid.UUID, **changes: Any) -> PaymentState:
    with factory() as db:
        order = db.get_one(PaymentOrder, order_id)
        values: dict[str, Any] = {
            "status": "paid",
            "amount": order.amount,
            "currency": order.currency,
            "reference": order.provider_ref,
            "product": "prd_m",
            "payment_amount": Decimal(13800),
            "payment_currency": "XOF",
        }
    return PaymentState(**{**values, **changes})


def pay(
    factory: sessionmaker[Any], user: User, at: datetime = NOW, payer: bytes | None = None
) -> uuid.UUID:
    order_id = order_for(factory, user, payer=payer)
    with factory.begin() as db:
        assert billing.settle(db, order_id, state_of(factory, order_id), at) is not None
    return order_id


def commissions(factory: sessionmaker[Any], affiliate: Affiliate) -> list[AffiliateCommission]:
    with factory() as db:
        return list(
            db.scalars(
                select(AffiliateCommission)
                .where(AffiliateCommission.affiliate_id == affiliate.id)
                .order_by(AffiliateCommission.created_at)
            )
        )


def admin_row(factory: sessionmaker[Any]) -> User:
    return make_user(factory)


@requires_db
def test_program_values_are_those_of_q07(factory: sessionmaker[Any]) -> None:
    with factory() as db:
        row = service.program(db)
        assert (row.rate_pct, row.recurring, row.attribution_days, row.hold_days) == (
            Decimal(20),
            False,
            30,
            14,
        )


@requires_db
def test_commission_follows_only_a_validated_payment(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    order_id = order_for(factory, user)
    with factory.begin() as db:
        wrong = state_of(factory, order_id, amount=Decimal(1))
        assert billing.settle(db, order_id, wrong, NOW) is None
    assert commissions(factory, affiliate) == []

    with factory.begin() as db:
        billing.settle(db, order_id, state_of(factory, order_id), NOW)
    [row] = commissions(factory, affiliate)
    assert (row.amount, row.base_amount, row.rate_pct) == (Decimal(3), Decimal(15), Decimal(20))
    assert (row.status, row.currency) == ("held", "USD")
    assert row.available_at == NOW + timedelta(days=14)
    assert service.state_of(row, NOW) == "held"
    assert service.state_of(row, NOW + timedelta(days=14)) == "available"


@requires_db
def test_replayed_payment_gives_one_commission(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    order_id = pay(factory, user)
    with factory.begin() as db:
        assert billing.settle(db, order_id, state_of(factory, order_id), NOW) is None
    assert len(commissions(factory, affiliate)) == 1


@requires_db
def test_only_the_first_payment_counts_by_default(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    pay(factory, user)
    pay(factory, user, NOW + timedelta(days=30))
    assert len(commissions(factory, affiliate)) == 1


@requires_db
def test_recurring_program_pays_each_payment(
    factory: sessionmaker[Any], rules: Callable[..., None]
) -> None:
    rules(recurring=True)
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    pay(factory, user)
    pay(factory, user, NOW + timedelta(days=60))
    assert len(commissions(factory, affiliate)) == 2


@requires_db
def test_recurring_needs_a_first_payment_inside_the_window(
    factory: sessionmaker[Any], rules: Callable[..., None]
) -> None:
    rules(recurring=True)
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    pay(factory, user, NOW + timedelta(days=31))
    pay(factory, user, NOW + timedelta(days=32))
    assert commissions(factory, affiliate) == []


@requires_db
def test_rate_is_frozen_on_the_commission(
    factory: sessionmaker[Any], rules: Callable[..., None]
) -> None:
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    rules(rate_pct=Decimal("33.33"))
    pay(factory, user)
    rules(rate_pct=Decimal(10))
    [row] = commissions(factory, affiliate)
    assert (row.rate_pct, row.amount) == (Decimal("33.33"), Decimal("4.99"))


@requires_db
def test_payment_outside_the_window_gives_nothing(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    pay(factory, user, NOW + timedelta(days=30, seconds=1))
    assert commissions(factory, affiliate) == []


@requires_db
def test_suspended_affiliate_earns_nothing(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory, "suspended")
    user = referred(factory, affiliate)
    pay(factory, user)
    assert commissions(factory, affiliate) == []


@requires_db
def test_same_phone_as_the_affiliate_cancels_the_commission(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    phone = b"p" * 32
    with factory() as db:
        owner = db.get_one(User, affiliate.user_id)
    order_for(factory, owner, payer=phone)
    user = referred(factory, affiliate)
    pay(factory, user, payer=phone)
    [row] = commissions(factory, affiliate)
    assert (row.status, row.reason) == ("cancelled", "same_payer")
    with factory() as db:
        link = db.scalars(select(Referral).where(Referral.referred_user_id == user.id)).one()
        assert (link.status, link.reason) == ("blocked", "same_payer")


@requires_db
def test_payout_number_equal_to_the_payer_cancels_the_commission(
    factory: sessionmaker[Any],
) -> None:
    affiliate = make_affiliate(factory)
    phone = b"q" * 32
    with factory.begin() as db:
        db.get_one(Affiliate, affiliate.id).payout_hash = phone
    pay(factory, referred(factory, affiliate), payer=phone)
    assert commissions(factory, affiliate)[0].reason == "same_payer"


@requires_db
def test_device_shared_after_signup_cancels_the_commission(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    device = uuid.uuid4().bytes * 2
    with factory.begin() as db:
        for owner in (affiliate.user_id, user.id):
            db.add(
                Session(
                    user_id=owner,
                    token_hash=uuid.uuid4().bytes * 2,
                    expires_at=NOW,
                    device_hash=device,
                )
            )
    pay(factory, user)
    assert commissions(factory, affiliate)[0].reason == "same_device"


@requires_db
def test_same_device_is_blocked_at_signup(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    device = uuid.uuid4().bytes * 2
    with factory.begin() as db:
        db.add(
            Session(
                user_id=affiliate.user_id,
                token_hash=uuid.uuid4().bytes * 2,
                expires_at=NOW,
                device_hash=device,
            )
        )
    user = referred(factory, affiliate, device=device)
    pay(factory, user)
    assert commissions(factory, affiliate) == []


@requires_db
def test_shared_public_address_waits_for_an_administrator(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    with factory.begin() as db:
        db.add(
            Session(
                user_id=affiliate.user_id,
                token_hash=uuid.uuid4().bytes * 2,
                expires_at=NOW,
                ip_address="8.8.8.8",
            )
        )
    user = referred(factory, affiliate, ip="8.8.8.8")
    pay(factory, user)
    [row] = commissions(factory, affiliate)
    after_hold = NOW + timedelta(days=15)
    assert (row.status, row.reason) == ("held", "same_address")
    assert service.state_of(row, after_hold) == "review"
    with factory.begin() as db:
        service.release(db, row.id, admin_row(factory), None)
    [freed] = commissions(factory, affiliate)
    assert service.state_of(freed, NOW) == "held"
    assert service.state_of(freed, after_hold) == "available"


@requires_db
def test_internal_address_proves_nothing(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    with factory.begin() as db:
        db.add(
            Session(
                user_id=affiliate.user_id,
                token_hash=uuid.uuid4().bytes * 2,
                expires_at=NOW,
                ip_address="172.18.0.5",
            )
        )
    user = referred(factory, affiliate, ip="172.18.0.5")
    with factory() as db:
        link = db.scalars(select(Referral).where(Referral.referred_user_id == user.id)).one()
        assert link.status == "active"


@requires_db
def test_referred_user_is_attached_only_once(factory: sessionmaker[Any]) -> None:
    first = make_affiliate(factory)
    second = make_affiliate(factory)
    user = referred(factory, first)
    with pytest.raises(DBAPIError), factory.begin() as db:
        service.attribute(db, user, second, None, None, NOW)


def ready_commission(factory: sessionmaker[Any], affiliate: Affiliate) -> None:
    """Commission dont le délai de rétractation est passé."""
    pay(factory, referred(factory, affiliate))
    with factory.begin() as db:
        for row in db.scalars(
            select(AffiliateCommission).where(
                AffiliateCommission.affiliate_id == affiliate.id,
                AffiliateCommission.status == "held",
            )
        ):
            row.available_at = datetime.now(UTC) - timedelta(seconds=1)


@requires_db
def test_payout_takes_all_available_only_once(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    ready_commission(factory, affiliate)
    ready_commission(factory, affiliate)
    pay(factory, referred(factory, affiliate))  # encore dans le délai de rétractation

    admin = admin_row(factory)
    with factory.begin() as db:
        payout = service.record_payout(
            db, affiliate.id, admin, method="crypto", reference="tx-1", ip=None
        )
    assert (payout.amount, payout.currency, payout.paid_by) == (Decimal(6), "USD", admin.id)
    states = sorted(row.status for row in commissions(factory, affiliate))
    assert states == ["held", "paid", "paid"]

    with pytest.raises(ApiError) as second, factory.begin() as db:
        service.record_payout(db, affiliate.id, admin, method="crypto", reference="tx-2", ip=None)
    assert second.value.code == "affiliate.nothing_to_pay"
    with factory() as db:
        total = service.totals_of(db, [affiliate.id])[affiliate.id]
    assert (total.paid, total.available, total.held) == (Decimal(6), Decimal(0), Decimal(3))
    assert (total.referrals, total.converted) == (3, 3)


@requires_db
def test_payout_needs_an_approved_affiliate(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory, "suspended")
    with pytest.raises(ApiError) as refused, factory.begin() as db:
        service.record_payout(
            db, affiliate.id, admin_row(factory), method="other", reference="abc", ip=None
        )
    assert refused.value.code == "affiliate.invalid_state"


@requires_db
def test_payout_rows_cannot_be_changed(factory: sessionmaker[Any], migrated_engine: Engine) -> None:
    affiliate = make_affiliate(factory)
    ready_commission(factory, affiliate)
    with factory.begin() as db:
        payout = service.record_payout(
            db, affiliate.id, admin_row(factory), method="bank", reference="vir-1", ip=None
        )
    with pytest.raises(DBAPIError), migrated_engine.begin() as conn:
        conn.execute(
            text("UPDATE affiliate_payouts SET amount = 999 WHERE id = :id"), {"id": payout.id}
        )


@requires_db
def test_cancelling_a_commission_removes_it_from_the_balance(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    pay(factory, referred(factory, affiliate))
    [row] = commissions(factory, affiliate)
    admin = admin_row(factory)
    with factory.begin() as db:
        service.cancel(db, row.id, admin, None)
    [cancelled] = commissions(factory, affiliate)
    assert (cancelled.status, cancelled.reason) == ("cancelled", "admin")
    with factory() as db:
        total = service.totals_of(db, [affiliate.id])[affiliate.id]
    assert (total.held, total.converted, total.referrals) == (Decimal(0), 0, 1)
    with pytest.raises(ApiError), factory.begin() as db:
        service.cancel(db, row.id, admin, None)


@requires_db
def test_every_step_is_traced(factory: sessionmaker[Any]) -> None:
    affiliate = make_affiliate(factory)
    user = referred(factory, affiliate)
    pay(factory, user)
    [row] = commissions(factory, affiliate)
    with factory() as db:
        attribution = db.scalars(
            select(AuditLog).where(
                AuditLog.action == "affiliate.attribution", AuditLog.actor_user_id == user.id
            )
        ).one()
        assert attribution.target_id == str(affiliate.id)
        commission = db.scalars(
            select(AuditLog).where(
                AuditLog.action == "affiliate.commission", AuditLog.target_id == str(row.id)
            )
        ).one()
        assert commission.details["amount"] == "3.00"


@pytest.fixture
def make_client(migrated_engine: Engine) -> Iterator[Callable[[], TestClient]]:
    mailer = MemoryMailer()
    app = create_app(
        Settings(
            environment="test",
            session_cookie_secure=False,
            allowed_origins=[ORIGIN],
            encryption_key=KEY,
        ),
        session_factory=sessionmaker(migrated_engine, expire_on_commit=False),
        mailer=mailer,
        failures=MemoryFailureCounter(),
    )
    app.state.test_mailer = mailer
    clients: list[TestClient] = []

    def make() -> TestClient:
        client = TestClient(app, headers={"Origin": ORIGIN})
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


def admin(
    make_client: Callable[[], TestClient], engine: Engine, role: UserRole = UserRole.SUPER_ADMIN
) -> TestClient:
    client = make_client()
    signed_up(client, engine, role)
    enable_mfa(client)
    return client


def applied(client: TestClient) -> str:
    response = client.post("/affiliate/apply", json={**LETTER, "accept_terms": True})
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    return str(client.get("/auth/me").json()["user"]["email"])


def affiliate_id(boss: TestClient, email: str) -> str:
    rows = boss.get("/admin/affiliates").json()["affiliates"]
    return str(next(row["id"] for row in rows if row["email"] == email))


def approved(make_client: Callable[[], TestClient], engine: Engine) -> tuple[TestClient, str, str]:
    """Affilié approuvé par un administrateur : client, code et identifiant."""
    client = make_client()
    signed_up(client, engine)
    email = applied(client)
    boss = admin(make_client, engine)
    key = affiliate_id(boss, email)
    assert boss.post(f"/admin/affiliates/{key}/approve", json={}).status_code == 200
    return client, client.get("/affiliate/me").json()["code"], key


def register(client: TestClient, code: str | None, email: str | None = None) -> Any:
    return client.post(
        "/auth/register",
        json={
            "email": email or f"fil-{uuid.uuid4().hex[:10]}@example.com",
            "password": PASSWORD,
            "first_name": "Bea",
            "accept_risk": True,
            "referral_code": code,
        },
    )


@requires_db
def test_full_path_from_application_to_attached_referral(
    make_client: Callable[[], TestClient], migrated_engine: Engine, factory: sessionmaker[Any]
) -> None:
    client, code, _ = approved(make_client, migrated_engine)
    assert re.fullmatch(r"[A-HJ-NP-Z2-9]{8}", code)
    view = client.get("/affiliate/me").json()
    assert view["status"] == "approved"
    assert view["link"].endswith(f":13000/register?ref={code}")
    assert client.get("/auth/me").json()["user"]["role"] == "affiliate"
    mailer: MemoryMailer = client.app.state.test_mailer  # type: ignore[attr-defined]
    assert code in mailer.sent[-1].body

    assert register(make_client(), code.lower()).status_code == 202
    view = client.get("/affiliate/me").json()
    assert view["totals"]["referrals"] == 1
    assert view["referrals"][0]["name"] == "B***"
    assert view["referrals"][0]["converted"] is False


@requires_db
def test_unknown_code_is_refused_whether_or_not_the_address_exists(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    email = signed_up(client, migrated_engine)
    other = make_client()
    for address in (email, f"new-{uuid.uuid4().hex[:8]}@example.com"):
        response = register(other, "NOPE2222", address)
        assert (response.status_code, response.json()["error"]) == (
            422,
            "affiliate.unknown_code",
        )


@requires_db
def test_empty_code_is_ignored(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    assert register(make_client(), "   ").status_code == 202


@requires_db
def test_existing_account_is_never_attached(
    make_client: Callable[[], TestClient], migrated_engine: Engine, factory: sessionmaker[Any]
) -> None:
    _, code, key = approved(make_client, migrated_engine)
    email = signed_up(make_client(), migrated_engine)
    assert register(make_client(), code, email).status_code == 202
    with factory() as db:
        assert db.scalars(select(Referral).where(Referral.affiliate_id == key)).all() == []


@requires_db
def test_own_browser_is_blocked_and_hidden_from_the_affiliate(
    make_client: Callable[[], TestClient], migrated_engine: Engine, factory: sessionmaker[Any]
) -> None:
    client, code, key = approved(make_client, migrated_engine)
    assert register(client, code).status_code == 202
    with factory() as db:
        link = db.scalars(select(Referral).where(Referral.affiliate_id == key)).one()
        assert (link.status, link.reason) == ("blocked", "same_device")
    view = client.get("/affiliate/me").json()
    assert (view["totals"]["referrals"], view["referrals"]) == (0, [])


@requires_db
def test_alias_of_the_affiliate_is_blocked(
    make_client: Callable[[], TestClient], migrated_engine: Engine, factory: sessionmaker[Any]
) -> None:
    client, code, key = approved(make_client, migrated_engine)
    email = client.get("/auth/me").json()["user"]["email"]
    local, domain = email.split("@")
    assert register(make_client(), code, f"{local}+promo@{domain}").status_code == 202
    with factory() as db:
        link = db.scalars(select(Referral).where(Referral.affiliate_id == key)).one()
        assert (link.status, link.reason) == ("blocked", "same_identity")


@requires_db
def test_suspended_code_stops_working_and_keeps_its_value(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client, code, key = approved(make_client, migrated_engine)
    boss = make_client()
    signed_up(boss, migrated_engine, UserRole.SUPER_ADMIN)
    enable_mfa(boss)
    assert boss.post(f"/admin/affiliates/{key}/suspend", json={"note": "abus"}).status_code == 200
    assert register(make_client(), code).status_code == 422
    view = client.get("/affiliate/me").json()
    assert (view["status"], view["link"]) == ("suspended", None)
    assert client.get("/auth/me").json()["user"]["role"] == "client"
    assert boss.post(f"/admin/affiliates/{key}/approve", json={}).status_code == 200
    assert client.get("/affiliate/me").json()["code"] == code


@requires_db
def test_application_rules(make_client: Callable[[], TestClient], migrated_engine: Engine) -> None:
    client = make_client()
    signed_up(client, migrated_engine)
    refused = client.post("/affiliate/apply", json=LETTER)
    assert (refused.status_code, refused.json()["error"]) == (422, "affiliate.terms_required")
    email = applied(client)
    again = client.post("/affiliate/apply", json={**LETTER, "accept_terms": True})
    assert (again.status_code, again.json()["error"]) == (409, "affiliate.already_applied")

    boss = admin(make_client, migrated_engine)
    key = affiliate_id(boss, email)
    assert boss.post(f"/admin/affiliates/{key}/refuse", json={}).status_code == 200
    assert client.get("/affiliate/me").json()["status"] == "refused"
    assert boss.post(f"/admin/affiliates/{key}/refuse", json={}).status_code == 409
    assert client.post("/affiliate/apply", json={**LETTER, "accept_terms": True}).status_code == 201


@pytest.mark.parametrize(
    "change", [{"message": "court"}, {"payout_details": "x"}, {"message": "m" * 501}]
)
@requires_db
def test_application_input_is_validated(
    make_client: Callable[[], TestClient], migrated_engine: Engine, change: dict[str, str]
) -> None:
    client = make_client()
    signed_up(client, migrated_engine)
    body = {**LETTER, "accept_terms": True, **change}
    assert client.post("/affiliate/apply", json=body).status_code == 422


@requires_db
def test_administrators_cannot_become_affiliates(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    boss = admin(make_client, migrated_engine)
    response = boss.post("/affiliate/apply", json={**LETTER, "accept_terms": True})
    assert (response.status_code, response.json()["error"]) == (403, "affiliate.not_eligible")


@requires_db
def test_least_privilege_on_affiliate_routes(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, _, key = approved(make_client, migrated_engine)
    support = admin(make_client, migrated_engine, UserRole.SUPPORT)
    assert support.get("/admin/affiliates").status_code == 403

    finance = admin(make_client, migrated_engine, UserRole.FINANCE)
    assert finance.get("/admin/affiliates").status_code == 200
    assert finance.post(f"/admin/affiliates/{key}/suspend", json={}).status_code == 403
    rules = {"rate_pct": "10", "recurring": False, "attribution_days": 30, "hold_days": 14}
    assert finance.put("/admin/affiliates/program", json=rules).status_code == 403
    paid = finance.post(
        f"/admin/affiliates/{key}/payouts", json={"method": "crypto", "reference": "tx-9"}
    )
    assert (paid.status_code, paid.json()["error"]) == (409, "affiliate.nothing_to_pay")


@requires_db
def test_payout_amount_never_comes_from_the_request(
    make_client: Callable[[], TestClient], migrated_engine: Engine, factory: sessionmaker[Any]
) -> None:
    affiliate = make_affiliate(factory)
    ready_commission(factory, affiliate)
    finance = admin(make_client, migrated_engine, UserRole.FINANCE)
    paid = finance.post(
        f"/admin/affiliates/{affiliate.id}/payouts",
        json={"method": "mobile_money", "reference": "mm-1", "amount": "9999"},
    )
    assert paid.status_code == 201
    assert paid.json()["payouts"][0]["amount"] == "3.00"
    assert paid.json()["totals"]["paid"] == "3.00"


@requires_db
def test_program_update_is_validated_and_traced(
    make_client: Callable[[], TestClient],
    migrated_engine: Engine,
    factory: sessionmaker[Any],
    rules: Callable[..., None],
) -> None:
    boss = admin(make_client, migrated_engine)
    good = {"rate_pct": "12.50", "recurring": True, "attribution_days": 45, "hold_days": 7}
    assert boss.put("/admin/affiliates/program", json=good).json() == good
    with factory() as db:
        last = db.scalars(
            select(AuditLog)
            .where(AuditLog.action == "affiliate.program")
            .order_by(AuditLog.id.desc())
        ).first()
        assert last is not None
        assert last.details["rate_pct"] == "12.50"
    bad = {**good, "rate_pct": "120"}
    assert boss.put("/admin/affiliates/program", json=bad).status_code == 422
    assert boss.get("/admin/affiliates/program").json() == good


class FakeGateway:
    name = "chariow"

    def supports(self, plan: str) -> bool:
        return True

    async def create_checkout(self, *_: Any) -> Checkout:
        reference = f"sal_{uuid.uuid4().hex[:8]}"
        return Checkout(reference, "https://pay.test/1", "prd_m", Decimal(15), "USD")


@requires_db
def test_checkout_keeps_a_fingerprint_not_the_number(
    make_client: Callable[[], TestClient], migrated_engine: Engine, factory: sessionmaker[Any]
) -> None:
    client = make_client()
    signed_up(client, migrated_engine)
    app: Any = client.app
    app.state.gateways = {"chariow": FakeGateway()}
    phone = "243970000000"
    body = {"plan": "monthly", "last_name": "L", "phone_number": phone, "phone_country": "CD"}
    bought = client.post("/billing/checkout", json=body)
    assert bought.status_code == 201
    with factory() as db:
        order = db.get_one(PaymentOrder, uuid.UUID(bought.json()["order"]))
    assert order.payer_hash == service.fingerprint(app.state.settings, phone)


@requires_db
def test_affiliate_sees_a_waiting_commission_never_the_reason(
    make_client: Callable[[], TestClient], migrated_engine: Engine, factory: sessionmaker[Any]
) -> None:
    client, code, key = approved(make_client, migrated_engine)
    with factory() as db:
        affiliate = db.get_one(Affiliate, uuid.UUID(key))
    user = make_user(factory)
    with factory.begin() as db:
        link = service.attribute(db, user, affiliate, None, None)
        link.status, link.reason = "review", "same_address"
    pay(factory, user, datetime.now(UTC))
    view = client.get("/affiliate/me").json()
    assert view["referrals"][0]["converted"] is True
    [commission] = view["commissions"]
    assert (commission["status"], commission["amount"]) == ("held", "3.00")
    assert commission["plan"] == "monthly"
    assert "reason" not in commission
    assert (view["totals"]["held"], view["totals"]["available"]) == ("3.00", "0")
    assert code not in str(view["commissions"])


@requires_db
def test_another_client_sees_nothing_of_an_affiliate(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    approved(make_client, migrated_engine)
    stranger = make_client()
    signed_up(stranger, migrated_engine)
    view = stranger.get("/affiliate/me").json()
    assert (view["status"], view["code"], view["referrals"]) == ("none", None, [])
