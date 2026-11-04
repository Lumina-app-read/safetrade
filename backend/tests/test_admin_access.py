"""Seconde connexion de l'administration et abonnements accordés à la main."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.auth import totp
from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.config import Settings
from app.db.models import AuditLog, PaymentOrder, Subscription, User, UserRole
from app.main import create_app
from tests.conftest import requires_db
from tests.test_authz import KEY, ORIGIN, PASSWORD, enable_mfa, enter_admin, signed_up

pytestmark = requires_db


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


def mailer_of(client: TestClient) -> MemoryMailer:
    mailer: MemoryMailer = client.app.state.test_mailer  # type: ignore[attr-defined]
    return mailer


def admin_without_entry(client: TestClient, engine: Engine) -> tuple[str, str]:
    """Super administrateur, double authentification activée, administration encore fermée."""
    email = signed_up(client, engine, UserRole.SUPER_ADMIN)
    secret: str = client.post("/auth/mfa/setup").json()["secret"]
    code = totp.code_at(secret, totp.current_step())
    assert client.post("/auth/mfa/enable", json={"code": code}).status_code == 200
    return email, secret


def enter(client: TestClient, password: str, code: str) -> tuple[int, str | None]:
    response = client.post("/auth/admin/enter", json={"password": password, "code": code})
    return response.status_code, response.json().get("error")


def audit_count(engine: Engine, action: str, result: str) -> int:
    with sessionmaker(engine)() as db:
        return (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == action, AuditLog.result == result)
            )
            or 0
        )


def test_signing_in_does_not_open_the_administration(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    admin_without_entry(client, migrated_engine)
    response = client.get("/admin/me")
    assert (response.status_code, response.json()["error"]) == (403, "admin.reauth_required")
    assert client.get("/admin/users").json()["error"] == "admin.reauth_required"


def test_second_sign_in_opens_it_and_warns_by_email(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    email, secret = admin_without_entry(client, migrated_engine)
    before = audit_count(migrated_engine, "admin.enter", "success")
    enter_admin(client, secret, totp.current_step() + 1)
    me = client.get("/admin/me")
    assert me.status_code == 200
    until = datetime.fromisoformat(me.json()["admin_until"])
    assert timedelta(minutes=55) < until - datetime.now(UTC) <= timedelta(minutes=60)
    sent = mailer_of(client).sent[-1]
    assert (sent.to, sent.template) == (email, "admin_access")
    assert audit_count(migrated_engine, "admin.enter", "success") == before + 1


def test_both_factors_are_required_and_never_told_apart(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    _, secret = admin_without_entry(client, migrated_engine)
    good = totp.code_at(secret, totp.current_step() + 1)
    assert enter(client, "Wrong-Password-1", good) == (401, "admin.reauth_failed")
    assert enter(client, PASSWORD, "000000") == (401, "admin.reauth_failed")
    assert client.get("/admin/me").status_code == 403


def test_recovery_code_and_replayed_code_are_refused(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    email = signed_up(client, migrated_engine, UserRole.SUPER_ADMIN)
    secret: str = client.post("/auth/mfa/setup").json()["secret"]
    step = totp.current_step()
    enabled = client.post("/auth/mfa/enable", json={"code": totp.code_at(secret, step)})
    recovery = enabled.json()["recovery_codes"][0]
    assert enter(client, PASSWORD, recovery)[0] == 422  # six chiffres exigés
    # Le code qui vient d'activer la double authentification ne sert pas une seconde fois.
    assert enter(client, PASSWORD, totp.code_at(secret, step)) == (401, "admin.reauth_failed")
    assert email


def test_three_failures_close_the_session_and_lock(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    email, _ = admin_without_entry(client, migrated_engine)
    assert enter(client, "Wrong-Password-1", "123456")[1] == "admin.reauth_failed"
    assert enter(client, "Wrong-Password-2", "123456")[1] == "admin.reauth_failed"
    assert enter(client, "Wrong-Password-3", "123456") == (401, "admin.locked")
    assert client.get("/auth/me").status_code == 401  # session fermée
    assert mailer_of(client).sent[-1].template == "admin_locked"

    # Reconnexion : l'administration reste bloquée, même avec les bons facteurs.
    assert (
        client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()[
            "mfa_required"
        ]
        is True
    )


def test_lock_survives_a_new_session(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    email, secret = admin_without_entry(client, migrated_engine)
    for _ in range(3):
        enter(client, "Wrong-Password-9", "123456")
    challenge = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "challenge"
    ]
    step = totp.current_step() + 1
    logged = client.post(
        "/auth/login/mfa", json={"challenge": challenge, "code": totp.code_at(secret, step)}
    )
    assert logged.status_code == 200
    assert enter(client, PASSWORD, totp.code_at(secret, step + 1)) == (
        429,
        "auth.too_many_attempts",
    )


def test_client_cannot_enter(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine)
    assert enter(client, PASSWORD, "123456") == (403, "authz.forbidden")


def test_access_ends_when_idle_too_old_or_from_another_browser(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine, UserRole.SUPER_ADMIN)
    enable_mfa(client)
    assert client.get("/admin/me").status_code == 200

    other = client.get("/admin/me", headers={"User-Agent": "autre-navigateur"})
    assert other.json()["error"] == "admin.reauth_required"
    # Fermée pour de bon : revenir au navigateur d'origine ne la rouvre pas.
    assert client.get("/admin/me").status_code == 403


def test_idle_and_absolute_limits(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    for column in ("admin_seen_at", "admin_until"):
        client = make_client()
        email = signed_up(client, migrated_engine, UserRole.SUPER_ADMIN)
        enable_mfa(client)
        assert client.get("/admin/me").status_code == 200
        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE sessions SET {column} = now() - interval '16 minutes' "  # noqa: S608
                    "WHERE user_id = (SELECT id FROM users WHERE email = :e)"
                ),
                {"e": email},
            )
        assert client.get("/admin/me").json()["error"] == "admin.reauth_required"


def test_leaving_closes_the_administration(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine, UserRole.SUPER_ADMIN)
    enable_mfa(client)
    assert client.post("/auth/admin/leave").status_code == 204
    assert client.get("/admin/me").json()["error"] == "admin.reauth_required"
    assert client.get("/auth/me").status_code == 200  # l'espace client reste ouvert


# Abonnements accordés à la main.


def customer(make_client: Callable[[], TestClient], engine: Engine) -> tuple[TestClient, str]:
    client = make_client()
    email = signed_up(client, engine)
    with sessionmaker(engine)() as db:
        user = db.scalars(select(User).where(User.email == email)).one()
        return client, str(user.id)


def boss(make_client: Callable[[], TestClient], engine: Engine, role: UserRole) -> TestClient:
    client = make_client()
    signed_up(client, engine, role)
    enable_mfa(client)
    return client


GRANT = {"plan": "weekly", "note": "Paiement en attente chez Chariow"}


def test_super_admin_grants_and_revokes_access(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client, user_id = customer(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine, UserRole.SUPER_ADMIN)
    url = f"/admin/users/{user_id}/subscriptions"
    before = client.get("/auth/me").json()["user"]
    assert before["subscription_status"] in ("trial", "none")

    granted = admin.post(url, json=GRANT)
    assert granted.status_code == 201, granted.text
    manual = next(h for h in granted.json()["history"] if h["source"] == "manual")
    assert manual["note"] == GRANT["note"]
    assert manual["granted_by"]
    me = client.get("/auth/me").json()["user"]
    assert me["access"] is True

    # Aucune commande ni commission : rien n'a été payé.
    with sessionmaker(migrated_engine)() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(PaymentOrder)
                .where(PaymentOrder.user_id == user_id)
            )
            == 0
        )

    view = admin.get(url).json()
    assert {p["code"] for p in view["plans"]} >= {"weekly", "monthly"}
    assert "trial" not in {p["code"] for p in view["plans"]}

    revoked = admin.post(f"{url}/{manual['id']}/revoke", json={"note": "Paiement refusé"})
    assert revoked.status_code == 200
    gone = next(h for h in revoked.json()["history"] if h["id"] == manual["id"])
    assert gone["revoked_at"]
    assert (
        admin.post(f"{url}/{manual['id']}/revoke", json={"note": "Encore une fois"}).json()["error"]
        == "admin.subscription_revoked"
    )


def test_grants_stack_and_the_last_one_goes_first(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, user_id = customer(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine, UserRole.SUPER_ADMIN)
    url = f"/admin/users/{user_id}/subscriptions"
    first = admin.post(url, json={**GRANT, "days": 3}).json()["history"]
    second = admin.post(url, json={**GRANT, "days": 5}).json()["history"]
    manual = [h for h in second if h["source"] == "manual"]
    later, earlier = manual[0], manual[1]
    assert later["starts_at"] == earlier["ends_at"]
    assert len(first) + 1 == len(second)
    refused = admin.post(f"{url}/{earlier['id']}/revoke", json={"note": "Ordre inversé"})
    assert refused.json()["error"] == "admin.subscription_followed"


def test_grant_rules(make_client: Callable[[], TestClient], migrated_engine: Engine) -> None:
    _, user_id = customer(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine, UserRole.SUPER_ADMIN)
    url = f"/admin/users/{user_id}/subscriptions"
    assert admin.post(url, json={**GRANT, "plan": "trial"}).json()["error"] == "admin.invalid_plan"
    assert admin.post(url, json={**GRANT, "plan": "gold"}).json()["error"] == "admin.invalid_plan"
    assert admin.post(url, json={**GRANT, "note": "ok"}).status_code == 422
    assert admin.post(url, json={**GRANT, "days": 400}).status_code == 422

    # Décision du propriétaire : le super administrateur peut s'accorder un accès.
    me = admin.get("/admin/me").json()["user"]["id"]
    own = admin.post(f"/admin/users/{me}/subscriptions", json=GRANT)
    assert own.status_code == 201
    assert admin.get("/auth/me").json()["user"]["access"] is True


def test_paid_access_is_not_revoked_here(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, user_id = customer(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine, UserRole.SUPER_ADMIN)
    now = datetime.now(UTC)
    with sessionmaker(migrated_engine)() as db:
        row = Subscription(
            user_id=user_id, plan_code="monthly", starts_at=now, ends_at=now + timedelta(days=30)
        )
        db.add(row)
        db.commit()
        paid = str(row.id)
    response = admin.post(
        f"/admin/users/{user_id}/subscriptions/{paid}/revoke", json={"note": "Essai de retrait"}
    )
    assert response.json()["error"] == "admin.subscription_not_manual"


@pytest.mark.parametrize("role", [UserRole.SUPPORT, UserRole.FINANCE])
def test_only_super_admin_grants(
    role: UserRole, make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, user_id = customer(make_client, migrated_engine)
    other = boss(make_client, migrated_engine, role)
    url = f"/admin/users/{user_id}/subscriptions"
    assert other.get(url).status_code == 200  # lecture permise
    assert other.post(url, json=GRANT).json()["error"] == "authz.forbidden"


def test_user_list_shows_access(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine, UserRole.SUPER_ADMIN)
    rows = admin.get("/admin/users").json()["users"]
    assert all({"status", "plan", "ends_at"} <= set(r["access"]) for r in rows)
