"""Mot de passe oublié, « se souvenir de moi » et reconnaissance du risque."""

import re
import uuid
from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.config import Settings
from app.main import create_app
from tests.conftest import requires_db

pytestmark = requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"
NEW_PASSWORD = "Another-Battery-77"


@pytest.fixture
def mailer() -> MemoryMailer:
    return MemoryMailer()


@pytest.fixture
def client(migrated_engine: Engine, mailer: MemoryMailer) -> Iterator[TestClient]:
    app = create_app(
        Settings(environment="test", session_cookie_secure=False, allowed_origins=[ORIGIN]),
        session_factory=sessionmaker(migrated_engine, expire_on_commit=False),
        mailer=mailer,
        failures=MemoryFailureCounter(),
    )
    with TestClient(app, headers={"Origin": ORIGIN}) as c:
        yield c


def payload(email: str, **extra: object) -> dict[str, object]:
    return {
        "email": email,
        "password": PASSWORD,
        "first_name": "Clo",
        "accept_risk": True,
        **extra,
    }


def verified(client: TestClient, mailer: MemoryMailer) -> str:
    email = f"pw-{uuid.uuid4().hex[:10]}@example.com"
    assert client.post("/auth/register", json=payload(email)).status_code == 202
    token = re.search(r"token=([\w-]+)", mailer.sent[-1].body)
    assert token
    client.post("/auth/verify-email", json={"token": token.group(1)})
    return email


def reset_token(mailer: MemoryMailer) -> str:
    mail = next(m for m in reversed(mailer.sent) if m.template == "reset_password")
    match = re.search(r"token=([\w-]+)", mail.body)
    assert match
    return match.group(1)


def test_registration_requires_risk_acknowledgement(client: TestClient) -> None:
    email = f"risk-{uuid.uuid4().hex[:8]}@example.com"
    refused = client.post("/auth/register", json=payload(email, accept_risk=False))
    assert (refused.status_code, refused.json()["error"]) == (422, "auth.risk_not_accepted")
    missing = client.post(
        "/auth/register", json={"email": email, "password": PASSWORD, "first_name": "A"}
    )
    assert missing.json()["error"] == "auth.risk_not_accepted"


def test_risk_acknowledgement_is_recorded(
    client: TestClient, mailer: MemoryMailer, migrated_engine: Engine
) -> None:
    email = verified(client, mailer)
    with migrated_engine.connect() as conn:
        stored: datetime | None = conn.execute(
            text("SELECT risk_accepted_at FROM users WHERE email = :e"), {"e": email}
        ).scalar_one()
    assert stored is not None


def test_full_password_reset(client: TestClient, mailer: MemoryMailer) -> None:
    email = verified(client, mailer)
    assert (
        client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    )

    assert client.post("/auth/password/forgot", json={"email": email}).status_code == 202
    token = reset_token(mailer)
    done = client.post("/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})
    assert done.status_code == 200

    # Toutes les sessions sont fermées et l'ancien mot de passe ne fonctionne plus.
    assert client.get("/auth/me").status_code == 401
    old = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert old.status_code == 401
    new = client.post("/auth/login", json={"email": email, "password": NEW_PASSWORD})
    assert new.status_code == 200
    assert mailer.sent[-1].template == "password_changed"

    again = client.post("/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})
    assert (again.status_code, again.json()["error"]) == (400, "auth.reset_invalid")


def test_forgot_password_never_reveals_an_account(client: TestClient, mailer: MemoryMailer) -> None:
    known = client.post("/auth/password/forgot", json={"email": verified(client, mailer)})
    sent = len(mailer.sent)
    unknown = client.post(
        "/auth/password/forgot", json={"email": f"nobody-{uuid.uuid4().hex}@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mailer.sent) == sent


def test_new_request_cancels_previous_link(client: TestClient, mailer: MemoryMailer) -> None:
    email = verified(client, mailer)
    client.post("/auth/password/forgot", json={"email": email})
    first = reset_token(mailer)
    client.post("/auth/password/forgot", json={"email": email})
    refused = client.post("/auth/password/reset", json={"token": first, "password": NEW_PASSWORD})
    assert refused.json()["error"] == "auth.reset_invalid"
    latest = reset_token(mailer)
    done = client.post("/auth/password/reset", json={"token": latest, "password": NEW_PASSWORD})
    assert done.status_code == 200


def test_expired_link_is_refused(
    client: TestClient, mailer: MemoryMailer, migrated_engine: Engine
) -> None:
    email = verified(client, mailer)
    client.post("/auth/password/forgot", json={"email": email})
    with migrated_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE password_reset_tokens SET expires_at = now() - interval '1 minute' "
                "WHERE user_id = (SELECT id FROM users WHERE email = :e)"
            ),
            {"e": email},
        )
    r = client.post(
        "/auth/password/reset", json={"token": reset_token(mailer), "password": NEW_PASSWORD}
    )
    assert r.json()["error"] == "auth.reset_invalid"


def test_reset_requires_a_strong_password(client: TestClient, mailer: MemoryMailer) -> None:
    client.post("/auth/password/forgot", json={"email": verified(client, mailer)})
    r = client.post(
        "/auth/password/reset", json={"token": reset_token(mailer), "password": "short"}
    )
    assert (r.status_code, r.json()["error"]) == (422, "auth.password_too_short")


def test_reset_emails_are_limited_per_hour(client: TestClient, mailer: MemoryMailer) -> None:
    email = verified(client, mailer)
    for _ in range(5):
        assert client.post("/auth/password/forgot", json={"email": email}).status_code == 202
    assert sum(m.template == "reset_password" and m.to == email for m in mailer.sent) == 3


def age_session(engine: Engine, email: str, hours: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE sessions SET last_seen_at = now() - make_interval(hours => :h) "
                "WHERE user_id = (SELECT id FROM users WHERE email = :e)"
            ),
            {"h": hours, "e": email},
        )


def test_remembered_session_survives_inactivity(
    client: TestClient, mailer: MemoryMailer, migrated_engine: Engine
) -> None:
    email = verified(client, mailer)
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD, "remember": True})
    max_age = int(re.search(r"Max-Age=(\d+)", r.headers["set-cookie"]).group(1))  # type: ignore[union-attr]
    assert max_age > 29 * 24 * 3600

    age_session(migrated_engine, email, 24)
    assert client.get("/auth/me").status_code == 200
    age_session(migrated_engine, email, 8 * 24)
    assert client.get("/auth/me").status_code == 401


def test_normal_session_stays_short(
    client: TestClient, mailer: MemoryMailer, migrated_engine: Engine
) -> None:
    email = verified(client, mailer)
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    max_age = int(re.search(r"Max-Age=(\d+)", r.headers["set-cookie"]).group(1))  # type: ignore[union-attr]
    assert max_age <= 12 * 3600

    age_session(migrated_engine, email, 1)
    assert client.get("/auth/me").status_code == 401
