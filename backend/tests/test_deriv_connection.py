"""Connexion du compte Deriv (étape 2.3). Deriv est simulé : aucun appel réseau."""

import asyncio
import base64
import json
import logging
import os
import re
import uuid
from collections.abc import Callable, Iterator, Sequence

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.broker.base import AccountKind, RealAccountDisabledError
from app.broker.deriv_rest import DerivAccount, DerivAuthError, DerivRest, DerivUnavailableError
from app.broker.quotas import MemoryQuotaStore, QuotaManager
from app.config import Settings
from app.main import create_app
from tests.conftest import requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"
TOKEN = "pat_secret_token_value_0123456789"
KEY = base64.b64encode(os.urandom(32)).decode()

ACCOUNTS = [
    {"account_id": "ROT1", "balance": "0.00", "currency": "USD", "group": "row",
     "status": "active", "account_type": "real"},
    {"account_id": "DOT2", "balance": "9990.00", "currency": "USD", "group": "row",
     "status": "active", "account_type": "demo"},
]  # fmt: skip


class FakeApi:
    """Transport httpx simulant l'API REST Deriv."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"errors": [{"code": "Unauthorized"}]})
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"url": "wss://demo?otp=x"}, "meta": {}})
        return httpx.Response(200, json={"data": ACCOUNTS, "meta": {}})


def rest_client(api: FakeApi, real_enabled: bool = False) -> DerivRest:
    return DerivRest(
        "app-id",
        QuotaManager(MemoryQuotaStore()),
        real_account_enabled=real_enabled,
        transport=httpx.MockTransport(api),
    )


REAL = DerivAccount("ROT1", AccountKind.REAL, "USD", "0.00", "active")
DEMO = DerivAccount("DOT2", AccountKind.DEMO, "USD", "9990.00", "active")


def test_otp_for_real_account_is_refused_before_any_call() -> None:
    api = FakeApi()
    with pytest.raises(RealAccountDisabledError):
        asyncio.run(rest_client(api).otp_url(TOKEN, REAL, "u"))
    assert api.requests == []


def test_otp_for_demo_account_sends_required_headers() -> None:
    api = FakeApi()
    url = asyncio.run(rest_client(api).otp_url(TOKEN, DEMO, "u"))
    assert url == "wss://demo?otp=x"
    sent = api.requests[0]
    assert sent.url.path.endswith("/accounts/DOT2/otp")
    assert sent.headers["authorization"] == f"Bearer {TOKEN}"
    assert sent.headers["deriv-app-id"] == "app-id"


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_token_raises_auth_error(status: int) -> None:
    api = FakeApi()
    api.status = status
    with pytest.raises(DerivAuthError):
        asyncio.run(rest_client(api).list_accounts(TOKEN, "u"))


def test_server_error_is_unavailable_without_leaking_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    api = FakeApi()
    api.status = 500
    with pytest.raises(DerivUnavailableError):
        asyncio.run(rest_client(api).list_accounts(TOKEN, "u"))
    assert TOKEN not in caplog.text


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def make_client(migrated_engine: Engine, api: FakeApi) -> Iterator[Callable[[], TestClient]]:
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
        deriv=rest_client(api),
    )
    clients: list[TestClient] = []

    def make() -> TestClient:
        client = TestClient(app, headers={"Origin": ORIGIN})
        clients.append(client)
        email = f"deriv-{uuid.uuid4().hex[:10]}@example.com"
        client.post(
            "/auth/register",
            json={"email": email, "password": PASSWORD, "first_name": "D", "accept_risk": True},
        )
        token = re.search(r"token=([\w-]+)", mailer.sent[-1].body)
        assert token
        client.post("/auth/verify-email", json={"token": token.group(1)})
        client.post("/auth/login", json={"email": email, "password": PASSWORD})
        return client

    yield make
    for c in clients:
        c.close()


@requires_db
def test_connect_stores_encrypted_token_and_selects_demo(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    response = client.post("/deriv/connect", json={"token": TOKEN})
    assert response.status_code == 200
    body = response.json()
    assert body["selected"] == {"account_id": "DOT2", "kind": "demo", "currency": "USD"}
    selectable = {a["account_id"]: a["selectable"] for a in body["accounts"]}
    assert selectable == {"ROT1": False, "DOT2": True}

    with migrated_engine.connect() as conn:
        stored: list[str] = list(
            conn.execute(text("SELECT token_encrypted FROM deriv_connections")).scalars()
        )
    assert stored and all(s.startswith("v1.") and TOKEN not in s for s in stored)


@requires_db
def test_token_never_leaves_the_server(
    make_client: Callable[[], TestClient],
    migrated_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    client = make_client()
    responses = [
        client.post("/deriv/connect", json={"token": TOKEN}),
        client.get("/deriv/connection"),
        client.post("/deriv/account", json={"account_id": "DOT2"}),
    ]
    for r in responses:
        assert TOKEN not in r.text and "token_encrypted" not in r.text
    assert TOKEN not in caplog.text
    with migrated_engine.connect() as conn:
        details: Sequence[str] = (
            conn.execute(text("SELECT details::text FROM audit_log")).scalars().all()
        )
    assert all(TOKEN not in d for d in details)


@requires_db
def test_real_account_cannot_be_selected(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    client.post("/deriv/connect", json={"token": TOKEN})
    r = client.post("/deriv/account", json={"account_id": "ROT1"})
    assert (r.status_code, r.json()["error"]) == (403, "deriv.real_disabled")
    assert client.get("/deriv/connection").json()["selected"]["kind"] == "demo"


@requires_db
def test_unknown_account_is_refused(make_client: Callable[[], TestClient]) -> None:
    client = make_client()
    client.post("/deriv/connect", json={"token": TOKEN})
    r = client.post("/deriv/account", json={"account_id": "OTHER"})
    assert (r.status_code, r.json()["error"]) == (404, "deriv.account_unknown")


@requires_db
def test_invalid_token_is_refused_and_attempts_are_limited(
    make_client: Callable[[], TestClient], api: FakeApi
) -> None:
    client = make_client()
    api.status = 401
    for _ in range(5):
        r = client.post("/deriv/connect", json={"token": TOKEN})
        assert (r.status_code, r.json()["error"]) == (400, "deriv.token_invalid")
    r = client.post("/deriv/connect", json={"token": TOKEN})
    assert r.status_code == 429
    assert client.get("/deriv/connection").json() == {"connected": False}


@requires_db
def test_expired_token_is_reported_not_hidden(
    make_client: Callable[[], TestClient], api: FakeApi
) -> None:
    client = make_client()
    client.post("/deriv/connect", json={"token": TOKEN})
    api.status = 401
    body = client.get("/deriv/connection").json()
    assert body["connected"] is True and body["token_valid"] is False


@requires_db
def test_deriv_outage_is_a_clear_error(make_client: Callable[[], TestClient], api: FakeApi) -> None:
    client = make_client()
    api.status = 500
    r = client.post("/deriv/connect", json={"token": TOKEN})
    assert (r.status_code, r.json()["error"]) == (503, "deriv.unavailable")


@requires_db
def test_disconnect_erases_token(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    client.post("/deriv/connect", json={"token": TOKEN})
    me = client.get("/auth/me").json()["user"]["id"]
    assert client.delete("/deriv/connection").status_code == 204
    assert client.get("/deriv/connection").json() == {"connected": False}
    assert client.delete("/deriv/connection").json()["error"] == "deriv.not_connected"
    with migrated_engine.connect() as conn:
        left: int = conn.execute(
            text("SELECT count(*) FROM deriv_connections WHERE user_id = :u"), {"u": me}
        ).scalar_one()
    assert left == 0


@requires_db
def test_connections_are_isolated_between_users(make_client: Callable[[], TestClient]) -> None:
    alice, bob = make_client(), make_client()
    alice.post("/deriv/connect", json={"token": TOKEN})
    assert bob.get("/deriv/connection").json() == {"connected": False}


def test_token_payload_rejects_whitespace(make_client: Callable[[], TestClient]) -> None:
    if os.environ.get("SAFETRADE_TEST_DATABASE_URL") is None:
        pytest.skip("base de test absente")
    client = make_client()
    r = client.post("/deriv/connect", json={"token": "a b" * 10})
    assert r.status_code == 422 and json.loads(r.text)["fields"] == ["token"]
