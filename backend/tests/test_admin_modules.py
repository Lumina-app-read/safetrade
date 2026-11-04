"""Modules de l'administration : fiche, actions de compte, équipe, formules, paiements, risque."""

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.config import Settings
from app.db.models import SiteSetting, User, UserRole
from app.main import create_app
from app.trading import controls
from app.trading import router as trading_router
from tests.conftest import requires_db
from tests.test_authz import KEY, ORIGIN, PASSWORD, enable_mfa, signed_up

pytestmark = requires_db

NOTE = {"note": "Contrôle de l'administration"}


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


@pytest.fixture(autouse=True)
def clean_controls(migrated_engine: Engine) -> Iterator[None]:
    yield
    with sessionmaker(migrated_engine).begin() as db:
        row = db.get(SiteSetting, controls.KEY)
        if row is not None:
            db.delete(row)


def account(make_client: Callable[[], TestClient], engine: Engine) -> tuple[TestClient, str, str]:
    client = make_client()
    email = signed_up(client, engine)
    with sessionmaker(engine)() as db:
        user_id = str(db.scalars(select(User.id).where(User.email == email)).one())
    return client, email, user_id


def boss(
    make_client: Callable[[], TestClient], engine: Engine, role: UserRole = UserRole.SUPER_ADMIN
) -> TestClient:
    client = make_client()
    signed_up(client, engine, role)
    enable_mfa(client)
    return client


def test_user_sheet_is_complete_and_holds_no_secret(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, email, user_id = account(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine)
    sheet = admin.get(f"/admin/users/{user_id}")
    assert sheet.status_code == 200
    data: dict[str, Any] = sheet.json()
    assert set(data) == {"profile", "access", "history", "trading", "payments", "affiliation"}
    assert data["profile"]["email"] == email
    assert data["profile"]["open_sessions"] >= 1
    assert data["trading"]["deriv"] is None
    text = sheet.text
    for secret in ("password_hash", "totp_secret", "token_encrypted", PASSWORD):
        assert secret not in text


def test_support_reads_the_sheet_without_payments_or_actions(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, _, user_id = account(make_client, migrated_engine)
    support = boss(make_client, migrated_engine, UserRole.SUPPORT)
    assert support.get(f"/admin/users/{user_id}").json()["payments"] is None
    refused = support.post(f"/admin/users/{user_id}/suspend", json=NOTE)
    assert refused.json()["error"] == "authz.forbidden"


def test_suspension_closes_sessions_and_access(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client, email, user_id = account(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine)
    suspended = admin.post(f"/admin/users/{user_id}/suspend", json=NOTE)
    assert suspended.status_code == 200
    assert suspended.json()["access"]["status"] == "suspended"
    assert client.get("/auth/me").status_code in (401, 403)
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.json()["error"] == "auth.account_suspended"
    assert admin.post(f"/admin/users/{user_id}/suspend", json=NOTE).json()["error"] == (
        "admin.already_suspended"
    )

    assert admin.post(f"/admin/users/{user_id}/reactivate", json=NOTE).status_code == 200
    assert (
        client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    )


def test_account_actions_need_a_reason_and_spare_super_admins(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, _, user_id = account(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine)
    assert admin.post(f"/admin/users/{user_id}/suspend", json={"note": "ok"}).status_code == 422
    me = admin.get("/admin/me").json()["user"]["id"]
    assert (
        admin.post(f"/admin/users/{me}/suspend", json=NOTE).json()["error"] == "admin.self_action"
    )
    other = boss(make_client, migrated_engine)
    other_id = other.get("/admin/me").json()["user"]["id"]
    assert admin.post(f"/admin/users/{other_id}/suspend", json=NOTE).json()["error"] == (
        "admin.protected_account"
    )


def test_revoking_sessions_signs_the_user_out(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client, _, user_id = account(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine)
    response = admin.post(f"/admin/users/{user_id}/sessions/revoke", json=NOTE)
    assert response.json()["profile"]["open_sessions"] == 0
    assert client.get("/auth/me").status_code == 401


def test_team_promotes_and_demotes(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, email, user_id = account(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine)
    promoted = admin.put(f"/admin/team/{user_id}", json={"role": "support", **NOTE})
    assert promoted.json()["role"] == "support"
    assert email in {m["email"] for m in admin.get("/admin/team").json()["members"]}
    assert admin.put(f"/admin/team/{user_id}", json={"role": "client", **NOTE}).status_code == 200
    me = admin.get("/admin/me").json()["user"]["id"]
    assert admin.put(f"/admin/team/{me}", json={"role": "client", **NOTE}).json()["error"] == (
        "admin.self_action"
    )


def test_only_super_admin_manages_the_team(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    finance = boss(make_client, migrated_engine, UserRole.FINANCE)
    assert finance.get("/admin/team").json()["error"] == "authz.forbidden"


def test_plan_changes_are_recorded_and_bounded(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine)
    before = {p["code"]: p for p in admin.get("/admin/plans").json()["plans"]}
    days = before["weekly"]["duration_days"]
    changed = admin.put("/admin/plans/weekly", json={"duration_days": days + 1, **NOTE})
    assert changed.json()["duration_days"] == days + 1
    history = admin.get("/admin/plans").json()["changes"]
    assert history[0]["plan"] == "weekly"
    assert history[0]["details"]["before"]["duration_days"] == days
    admin.put("/admin/plans/weekly", json={"duration_days": days, **NOTE})

    assert admin.put("/admin/plans/trial", json={"price": "5", **NOTE}).json()["error"] == (
        "admin.trial_is_free"
    )
    assert admin.put("/admin/plans/weekly", json={"price": "-1", **NOTE}).status_code == 422
    assert admin.put("/admin/plans/gold", json=NOTE).json()["error"] == "admin.plan_not_found"
    same = admin.put("/admin/plans/weekly", json={"duration_days": days, **NOTE})
    assert same.json()["error"] == "admin.nothing_changed"


def test_payments_list_and_check_without_provider(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine)
    listed = admin.get("/admin/payments")
    assert listed.status_code == 200
    assert isinstance(listed.json()["orders"], list)
    missing = admin.post(f"/admin/payments/{uuid.uuid4()}/check")
    assert missing.json()["error"] == "admin.order_not_found"


def test_trading_controls_and_global_halt(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine)
    assert admin.get("/admin/trading").json()["controls"]["halted"] is False
    limits = {"max_stake": "5", "max_positions": 2, "disabled_symbols": ["R_100", "R_100"]}
    saved = admin.put("/admin/trading/controls", json={**limits, **NOTE}).json()["controls"]
    assert (saved["max_stake"], saved["max_positions"]) == ("5", 2)
    assert saved["disabled_symbols"] == ["R_100"]
    assert (
        admin.put("/admin/trading/controls", json={"max_stake": "500", **NOTE}).status_code == 422
    )

    halted = admin.put("/admin/trading/halt", json={"halted": True, **NOTE}).json()["controls"]
    assert halted["halted"] is True
    assert halted["disabled_symbols"] == ["R_100"]  # l'arrêt garde les plafonds
    assert admin.get("/admin/stats").json()["halted"] is True

    # Démarrage refusé côté serveur, avant même la lecture du marché.
    with sessionmaker(migrated_engine)() as db:
        assert trading_router._global_refusal(db, "1HZ100V") == "risk.global_halt"

    admin.put("/admin/trading/halt", json={"halted": False, **NOTE})
    assert admin.get("/admin/trading").json()["controls"]["halted"] is False


def test_trading_module_is_super_admin_only(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    support = boss(make_client, migrated_engine, UserRole.SUPPORT)
    assert support.get("/admin/trading").json()["error"] == "authz.forbidden"
    assert support.put("/admin/trading/halt", json={"halted": True, **NOTE}).json()["error"] == (
        "authz.forbidden"
    )


def test_stats_hide_revenue_without_payment_permission(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine)
    assert "revenue_30d" in admin.get("/admin/stats").json()
    support = boss(make_client, migrated_engine, UserRole.SUPPORT)
    figures = support.get("/admin/stats").json()
    assert "revenue_30d" not in figures
    assert {"users", "new_users_7d", "trials", "subscribers", "bots"} <= set(figures)


def test_audit_shows_the_author_and_filters_by_prefix(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    _, _, user_id = account(make_client, migrated_engine)
    admin = boss(make_client, migrated_engine)
    admin.post(f"/admin/users/{user_id}/sessions/revoke", json=NOTE)
    me = admin.get("/admin/me").json()["user"]["email"]
    entries = admin.get("/admin/audit", params={"action": "admin.", "actor": me}).json()["entries"]
    assert entries
    assert all(e["action"].startswith("admin.") and e["actor_email"] == me for e in entries)
    older = admin.get("/admin/audit", params={"before": entries[0]["id"]}).json()["entries"]
    assert all(e["id"] < entries[0]["id"] for e in older)
