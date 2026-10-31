"""Inscription, vérification d'e-mail, connexion, sessions et brute force (étape 1.5)."""

import logging
import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import sessionmaker

from app.auth import service
from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.config import Settings
from app.db.models import AuditLog, Session, User
from app.errors import ApiError
from app.main import create_app
from tests.conftest import requires_db

pytestmark = requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"


@pytest.fixture
def mailer() -> MemoryMailer:
    return MemoryMailer()


@pytest.fixture
def client(migrated_engine: Engine, mailer: MemoryMailer) -> Iterator[TestClient]:
    settings = Settings(environment="test", session_cookie_secure=False, allowed_origins=[ORIGIN])
    app = create_app(
        settings,
        session_factory=sessionmaker(migrated_engine, expire_on_commit=False),
        mailer=mailer,
        failures=MemoryFailureCounter(),
    )
    with TestClient(app, headers={"Origin": ORIGIN}) as c:
        yield c


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def register(client: TestClient, email: str, password: str = PASSWORD, locale: str = "fr") -> None:
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Clovis",
            "locale": locale,
            "accept_risk": True,
        },
    )
    assert r.status_code == 202, r.text


def verification_token(mailer: MemoryMailer, email: str) -> str:
    mail = next(m for m in reversed(mailer.sent) if m.to == email and m.template == "verify_email")
    match = re.search(r"token=([\w-]+)", mail.body)
    assert match
    return match.group(1)


def verified_user(client: TestClient, mailer: MemoryMailer) -> str:
    email = unique_email()
    register(client, email)
    assert (
        client.post(
            "/auth/verify-email", json={"token": verification_token(mailer, email)}
        ).status_code
        == 200
    )
    return email


def test_full_flow_register_verify_login_me_logout(
    client: TestClient, mailer: MemoryMailer
) -> None:
    email = verified_user(client, mailer)

    r = client.post("/auth/login", json={"email": email.upper(), "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == email
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie

    assert client.get("/auth/me").json()["user"]["first_name"] == "Clovis"
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_password_is_hashed_with_argon2id(client: TestClient, migrated_engine: Engine) -> None:
    email = unique_email()
    register(client, email)
    with migrated_engine.connect() as conn:
        stored: str = conn.execute(
            text("SELECT password_hash FROM users WHERE email = :e"), {"e": email}
        ).scalar_one()
    assert stored.startswith("$argon2id$") and PASSWORD not in stored


def test_session_token_stored_only_as_hash(
    client: TestClient, mailer: MemoryMailer, migrated_engine: Engine
) -> None:
    email = verified_user(client, mailer)
    client.post("/auth/login", json={"email": email, "password": PASSWORD})
    token = client.cookies.get("st_session")
    assert token
    with sessionmaker(migrated_engine)() as db:
        hashes = db.scalars(select(Session.token_hash)).all()
    assert all(token.encode() not in h for h in hashes)


def test_unverified_email_cannot_log_in(client: TestClient) -> None:
    email = unique_email()
    register(client, email)
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert (r.status_code, r.json()["error"]) == (403, "auth.email_not_verified")


def test_wrong_password_and_unknown_email_look_identical(
    client: TestClient, mailer: MemoryMailer
) -> None:
    email = verified_user(client, mailer)
    wrong = client.post("/auth/login", json={"email": email, "password": "not-the-password"})
    unknown = client.post("/auth/login", json={"email": unique_email(), "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"error": "auth.invalid_credentials"}


def test_lockout_after_repeated_failures(client: TestClient, mailer: MemoryMailer) -> None:
    email = verified_user(client, mailer)
    for _ in range(5):
        assert (
            client.post(
                "/auth/login", json={"email": email, "password": "bad-password-x"}
            ).status_code
            == 401
        )
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert (r.status_code, r.json()["error"]) == (429, "auth.too_many_attempts")
    assert int(r.headers["retry-after"]) > 0


def test_duplicate_registration_sends_a_new_link_while_unconfirmed(
    client: TestClient, mailer: MemoryMailer
) -> None:
    email = unique_email()
    register(client, email)
    register(client, email.upper())
    assert [m.template for m in mailer.sent if m.to == email] == [
        "verify_email",
        "verify_email",
    ]


@pytest.mark.parametrize(
    ("password", "code"),
    [("short", "auth.password_too_short"), ("aaaaaaaaaaaa", "auth.password_too_weak")],
)
def test_weak_passwords_rejected(client: TestClient, password: str, code: str) -> None:
    r = client.post(
        "/auth/register",
        json={
            "email": unique_email(),
            "password": password,
            "first_name": "A",
            "accept_risk": True,
        },
    )
    assert (r.status_code, r.json()["error"]) == (422, code)


def test_validation_errors_never_echo_input(client: TestClient) -> None:
    r = client.post("/auth/login", json={"email": "not-an-email", "password": "secret-value-123"})
    assert r.status_code == 422
    assert r.json() == {"error": "validation.invalid", "fields": ["email"]}
    assert "secret-value-123" not in r.text


def test_verification_token_single_use(client: TestClient, mailer: MemoryMailer) -> None:
    email = unique_email()
    register(client, email)
    token = verification_token(mailer, email)
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    r = client.post("/auth/verify-email", json={"token": token})
    assert (r.status_code, r.json()["error"]) == (400, "auth.verification_invalid")


def test_foreign_origin_rejected(client: TestClient) -> None:
    r = client.post(
        "/auth/login",
        json={"email": unique_email(), "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert (r.status_code, r.json()["error"]) == (403, "auth.origin_forbidden")


def test_emails_follow_user_language(client: TestClient, mailer: MemoryMailer) -> None:
    email = unique_email()
    register(client, email, locale="en")
    mail = mailer.sent[-1]
    assert mail.subject.startswith("Confirm") and "/en/verify-email?token=" in mail.body


def test_audit_records_without_secrets(
    client: TestClient, mailer: MemoryMailer, migrated_engine: Engine
) -> None:
    email = verified_user(client, mailer)
    client.post("/auth/login", json={"email": email, "password": "bad-password-x"})
    client.post("/auth/login", json={"email": email, "password": PASSWORD})
    with sessionmaker(migrated_engine)() as db:
        user = db.scalars(select(User).where(User.email == email)).one()
        rows = db.scalars(
            select(AuditLog).where(AuditLog.actor_user_id == user.id).order_by(AuditLog.id)
        ).all()
    assert [(r.action, r.result) for r in rows] == [
        ("auth.register", "success"),
        ("auth.verify_email", "success"),
        ("auth.login", "failure"),
        ("auth.login", "success"),
    ]
    assert all(PASSWORD not in str(r.details) for r in rows)


def test_no_secret_in_logs(
    client: TestClient, mailer: MemoryMailer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    email = verified_user(client, mailer)
    client.post("/auth/login", json={"email": email, "password": PASSWORD})
    token = client.cookies.get("st_session")
    assert token and token not in caplog.text and PASSWORD not in caplog.text


def test_ip_limit_ignores_shared_internal_addresses(migrated_engine: Engine) -> None:
    """Une adresse interne (conteneur front-end) ne déclenche jamais le blocage par IP."""
    failures = MemoryFailureCounter()
    settings = Settings(environment="test", login_max_failures_per_ip=1)

    def attempt(email: str, ip: str) -> str:
        with sessionmaker(migrated_engine)() as db, pytest.raises(ApiError) as exc:
            service.login(
                db,
                failures,
                settings,
                email=email,
                password="wrong-password",
                ip=ip,
                user_agent=None,
            )
        return exc.value.code

    # Adresse interne partagée : jamais comptée, seuls les compteurs par e-mail jouent.
    assert {attempt(unique_email(), "172.18.0.5") for _ in range(3)} == {"auth.invalid_credentials"}
    assert failures.count("login:ip:172.18.0.5") == 0
    # Adresse publique : bloquée dès le seuil atteint.
    assert attempt(unique_email(), "93.184.216.34") == "auth.invalid_credentials"
    assert attempt(unique_email(), "93.184.216.34") == "auth.too_many_attempts"
