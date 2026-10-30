"""Double authentification TOTP, codes de secours et sessions (étape 1.6)."""

import base64
import os
import re
import uuid
from collections.abc import Callable, Iterator, Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.auth import totp
from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.config import Settings
from app.main import create_app
from tests.conftest import requires_db

pytestmark = requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"
KEY = base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def make_client(migrated_engine: Engine) -> Iterator[Callable[[], TestClient]]:
    """Fabrique de clients partageant la même application (plusieurs appareils)."""
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
    for c in clients:
        c.close()


def signed_up(client: TestClient) -> str:
    """Compte vérifié et connecté ; renvoie l'e-mail."""
    email = f"mfa-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "first_name": "Clo", "accept_risk": True},
    )
    mailer: MemoryMailer = client.app.state.test_mailer  # type: ignore[attr-defined]
    token = re.search(r"token=([\w-]+)", mailer.sent[-1].body)
    assert token
    client.post("/auth/verify-email", json={"token": token.group(1)})
    assert (
        client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    )
    return email


def enable_mfa(client: TestClient) -> tuple[str, list[str], int]:
    setup = client.post("/auth/mfa/setup").json()
    secret = setup["secret"]
    step = totp.current_step()
    r = client.post("/auth/mfa/enable", json={"code": totp.code_at(secret, step)})
    assert r.status_code == 200, r.text
    return secret, r.json()["recovery_codes"], step


def test_setup_returns_qr_and_wrong_code_is_refused(make_client: Callable[[], TestClient]) -> None:
    c = make_client()
    signed_up(c)
    setup = c.post("/auth/mfa/setup").json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/SafeTrade:")
    assert setup["qr_svg"].lstrip().startswith("<svg")
    r = c.post("/auth/mfa/enable", json={"code": "000000"})
    assert (r.status_code, r.json()["error"]) == (400, "mfa.invalid_code")
    assert c.get("/auth/me").json()["user"]["mfa_enabled"] is False


def test_secret_is_encrypted_at_rest(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    c = make_client()
    email = signed_up(c)
    secret, codes, _ = enable_mfa(c)
    with migrated_engine.connect() as conn:
        stored: str = conn.execute(
            text("SELECT totp_secret_encrypted FROM users WHERE email = :e"), {"e": email}
        ).scalar_one()
        hashes: Sequence[bytes] = (
            conn.execute(
                text(
                    "SELECT code_hash FROM recovery_codes rc "
                    "JOIN users u ON u.id = rc.user_id WHERE u.email = :e"
                ),
                {"e": email},
            )
            .scalars()
            .all()
        )
    assert stored.startswith("v1.") and secret not in stored
    assert len(hashes) == 10 and all(codes[0].encode() not in h for h in hashes)


def test_login_requires_second_factor_and_rejects_replay(
    make_client: Callable[[], TestClient],
) -> None:
    c = make_client()
    email = signed_up(c)
    secret, _, step = enable_mfa(c)

    phone = make_client()
    r = phone.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.json()["mfa_required"] is True and "set-cookie" not in r.headers
    challenge = r.json()["challenge"]

    # Le code déjà utilisé pour l'activation ne peut pas resservir.
    replay = phone.post(
        "/auth/login/mfa", json={"challenge": challenge, "code": totp.code_at(secret, step)}
    )
    assert (replay.status_code, replay.json()["error"]) == (400, "mfa.invalid_code")

    ok = phone.post(
        "/auth/login/mfa", json={"challenge": challenge, "code": totp.code_at(secret, step + 1)}
    )
    assert ok.status_code == 200 and "st_session" in ok.headers["set-cookie"]
    assert phone.get("/auth/me").json()["user"]["mfa_enabled"] is True

    # Un défi ne sert qu'une fois.
    again = phone.post("/auth/login/mfa", json={"challenge": challenge, "code": "123456"})
    assert again.json()["error"] == "mfa.challenge_invalid"


def test_recovery_code_works_once(make_client: Callable[[], TestClient]) -> None:
    c = make_client()
    email = signed_up(c)
    _, codes, _ = enable_mfa(c)

    for expected in (200, 400):
        other = make_client()
        challenge = other.post("/auth/login", json={"email": email, "password": PASSWORD}).json()[
            "challenge"
        ]
        code = codes[0].lower().replace("-", "")  # saisie tolérante
        r = other.post("/auth/login/mfa", json={"challenge": challenge, "code": code})
        assert r.status_code == expected


def test_challenge_locked_after_max_attempts(make_client: Callable[[], TestClient]) -> None:
    c = make_client()
    email = signed_up(c)
    secret, _, step = enable_mfa(c)
    other = make_client()
    challenge = other.post("/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "challenge"
    ]
    for _ in range(5):
        other.post("/auth/login/mfa", json={"challenge": challenge, "code": "000000"})
    r = other.post(
        "/auth/login/mfa", json={"challenge": challenge, "code": totp.code_at(secret, step + 1)}
    )
    assert r.json()["error"] == "mfa.challenge_invalid"


def test_disable_requires_password_and_code(make_client: Callable[[], TestClient]) -> None:
    c = make_client()
    signed_up(c)
    secret, _, step = enable_mfa(c)
    code = totp.code_at(secret, step + 1)
    bad = c.post("/auth/mfa/disable", json={"password": "wrong-password", "code": code})
    assert bad.json()["error"] == "auth.invalid_credentials"
    assert c.post("/auth/mfa/disable", json={"password": PASSWORD, "code": code}).status_code == 204
    assert c.get("/auth/me").json()["user"]["mfa_enabled"] is False


def test_setup_refused_when_already_enabled(make_client: Callable[[], TestClient]) -> None:
    c = make_client()
    signed_up(c)
    enable_mfa(c)
    assert c.post("/auth/mfa/setup").json()["error"] == "mfa.already_enabled"


def test_list_and_revoke_sessions(make_client: Callable[[], TestClient]) -> None:
    laptop = make_client()
    email = signed_up(laptop)
    phone = make_client()
    phone.post("/auth/login", json={"email": email, "password": PASSWORD})

    listed = laptop.get("/auth/sessions").json()["sessions"]
    assert len(listed) == 2 and sum(s["current"] for s in listed) == 1
    other_id = next(s["id"] for s in listed if not s["current"])
    current_id = next(s["id"] for s in listed if s["current"])

    assert laptop.delete(f"/auth/sessions/{current_id}").json()["error"] == "sessions.use_logout"
    assert laptop.delete(f"/auth/sessions/{other_id}").status_code == 204
    assert phone.get("/auth/me").status_code == 401
    assert laptop.get("/auth/me").status_code == 200


def test_cannot_revoke_someone_elses_session(make_client: Callable[[], TestClient]) -> None:
    alice, bob = make_client(), make_client()
    signed_up(alice)
    signed_up(bob)
    bob_session = bob.get("/auth/sessions").json()["sessions"][0]["id"]
    r = alice.delete(f"/auth/sessions/{bob_session}")
    assert (r.status_code, r.json()["error"]) == (404, "sessions.not_found")
    assert bob.get("/auth/me").status_code == 200


def test_revoke_other_sessions(make_client: Callable[[], TestClient]) -> None:
    main = make_client()
    email = signed_up(main)
    others = [make_client() for _ in range(2)]
    for o in others:
        o.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert main.post("/auth/sessions/revoke-others").json() == {"revoked": 2}
    assert all(o.get("/auth/me").status_code == 401 for o in others)
    assert main.get("/auth/me").status_code == 200
