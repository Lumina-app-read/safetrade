"""Contrôle d'accès sur chaque route, rôles administrateur et journal d'audit (étape 1.7)."""

import base64
import os
import re
import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import sessionmaker

from app.auth import totp
from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.cli import create_admin
from app.config import Settings
from app.db.models import AuditLog, User, UserRole
from app.main import create_app
from tests.conftest import requires_db

pytestmark = requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"
KEY = base64.b64encode(os.urandom(32)).decode()

# Seules routes accessibles sans session. Toute nouvelle route publique doit être ajoutée
# ici délibérément, sinon le test ci-dessous échoue.
PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("POST", "/auth/register"),
    ("POST", "/auth/verify-email"),
    ("POST", "/auth/login"),
    ("POST", "/auth/login/mfa"),
}


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
        # TestClient.app peut être un adaptateur ASGI : on garde l'application FastAPI.
        client.app_under_test = app
        clients.append(client)
        return client

    yield make
    for c in clients:
        c.close()


def api_routes(client: TestClient) -> list[tuple[str, str]]:
    """
    Toutes les routes de l'API (schéma OpenAPI : interface publique et stable, quelle que
    soit l'organisation interne des routeurs), paramètres de chemin remplacés.
    """
    schema = client.app_under_test.openapi()
    return [
        (method.upper(), re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path))
        for path, operations in schema["paths"].items()
        for method in operations
    ]


def signed_up(client: TestClient, engine: Engine, role: UserRole = UserRole.CLIENT) -> str:
    email = f"authz-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/auth/register", json={"email": email, "password": PASSWORD, "first_name": "A"})
    mailer: MemoryMailer = client.app.state.test_mailer  # type: ignore[attr-defined]
    token = re.search(r"token=([\w-]+)", mailer.sent[-1].body)
    assert token
    client.post("/auth/verify-email", json={"token": token.group(1)})
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET role = :r WHERE email = :e"), {"r": role.value, "e": email}
        )
    assert (
        client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    )
    return email


def enable_mfa(client: TestClient) -> None:
    secret = client.post("/auth/mfa/setup").json()["secret"]
    code = totp.code_at(secret, totp.current_step())
    assert client.post("/auth/mfa/enable", json={"code": code}).status_code == 200


def test_every_private_route_requires_a_session(make_client: Callable[[], TestClient]) -> None:
    client = make_client()
    checked = 0
    for method, path in api_routes(client):
        if (method, path) in PUBLIC_ROUTES:
            continue
        response = client.request(method, path, json={})
        assert response.status_code == 401, f"{method} {path} accessible sans session"
        checked += 1
    assert checked >= 10


def test_client_is_refused_on_every_admin_route(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    email = signed_up(client, migrated_engine)
    admin_routes = [(m, p) for m, p in api_routes(client) if p.startswith("/admin")]
    assert len(admin_routes) >= 3
    for method, path in admin_routes:
        response = client.request(method, path)
        assert (response.status_code, response.json()["error"]) == (403, "authz.forbidden"), path

    with sessionmaker(migrated_engine)() as db:
        user = db.scalars(select(User).where(User.email == email)).one()
        denied = db.scalars(
            select(AuditLog).where(
                AuditLog.actor_user_id == user.id, AuditLog.action == "authz.denied"
            )
        ).all()
    assert len(denied) == len(admin_routes)


def test_admin_without_mfa_is_refused(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine, UserRole.SUPER_ADMIN)
    response = client.get("/admin/me")
    assert (response.status_code, response.json()["error"]) == (403, "authz.mfa_required")
    enable_mfa(client)
    assert client.get("/admin/me").status_code == 200


def test_support_reads_users_but_not_audit(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine, UserRole.SUPPORT)
    enable_mfa(client)
    assert client.get("/admin/me").json()["permissions"] == ["users.read"]

    users = client.get("/admin/users")
    assert users.status_code == 200
    forbidden_keys = {"password_hash", "totp_secret_encrypted", "totp_last_step"}
    assert all(forbidden_keys.isdisjoint(u) for u in users.json()["users"])
    assert client.get("/admin/audit").json()["error"] == "authz.forbidden"


def test_super_admin_reads_audit_and_reading_is_audited(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine, UserRole.SUPER_ADMIN)
    enable_mfa(client)
    entries = client.get("/admin/audit", params={"action": "mfa.enable"}).json()["entries"]
    assert entries and all(e["action"] == "mfa.enable" for e in entries)
    latest = client.get("/admin/audit", params={"limit": 1}).json()["entries"][0]
    assert latest["action"] == "admin.audit.view"


def test_user_search_treats_wildcards_literally(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine, UserRole.SUPER_ADMIN)
    enable_mfa(client)
    assert client.get("/admin/users", params={"q": "%"}).json()["users"] == []
    assert len(client.get("/admin/users", params={"q": "authz-"}).json()["users"]) >= 1


def test_cli_create_admin(migrated_engine: Engine) -> None:
    email = f"cli-{uuid.uuid4().hex[:8]}@example.com"
    with sessionmaker(migrated_engine)() as db:
        user = create_admin(
            db,
            email=email,
            first_name="Ops",
            role=UserRole.SUPPORT,
            password=PASSWORD,
            promote=False,
        )
        assert user.role == UserRole.SUPPORT and user.email_verified_at is not None
        assert user.password_hash.startswith("$argon2id$")
        with pytest.raises(ValueError, match="existe déjà"):
            create_admin(
                db,
                email=email,
                first_name="Ops",
                role=UserRole.SUPPORT,
                password=PASSWORD,
                promote=False,
            )
        promoted = create_admin(
            db,
            email=email.upper(),
            first_name="",
            role=UserRole.SUPER_ADMIN,
            password="",
            promote=True,
        )
        assert promoted.role == UserRole.SUPER_ADMIN
        with pytest.raises(ValueError, match="non administrateur"):
            create_admin(
                db,
                email="x@example.com",
                first_name="X",
                role=UserRole.CLIENT,
                password=PASSWORD,
                promote=False,
            )
