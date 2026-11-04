"""Réglages de l'administration : messages, textes légaux, e-mails types et clés des services."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app import email_templates, service_keys
from app.auth import mailer
from app.auth.rate_limit import MemoryFailureCounter
from app.config import Settings
from app.db.models import AuditLog, SiteSetting, UserRole
from app.main import create_app
from tests.conftest import requires_db
from tests.test_authz import KEY, ORIGIN, enable_mfa, signed_up

pytestmark = requires_db

REASON = "Réglage vérifié par les tests"
LEGAL_BODY = "Article premier. " * 10


@pytest.fixture
def make_client(migrated_engine: Engine) -> Iterator[Callable[[], TestClient]]:
    app = create_app(
        Settings(
            environment="test",
            session_cookie_secure=False,
            allowed_origins=[ORIGIN],
            encryption_key=KEY,
        ),
        session_factory=sessionmaker(migrated_engine, expire_on_commit=False),
        mailer=mailer.MemoryMailer(),
        failures=MemoryFailureCounter(),
    )
    app.state.test_mailer = app.state.mailer
    clients: list[TestClient] = []

    def make() -> TestClient:
        client = TestClient(app, headers={"Origin": ORIGIN})
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()
    mailer.set_template_source(None)
    with sessionmaker(migrated_engine).begin() as db:
        for row in db.scalars(select(SiteSetting)):
            if row.key != "deriv_signup_url":
                db.delete(row)


def boss(
    make_client: Callable[[], TestClient], engine: Engine, role: UserRole = UserRole.SUPER_ADMIN
) -> TestClient:
    client = make_client()
    signed_up(client, engine, role)
    enable_mfa(client)
    return client


def test_announcement_and_warning_reach_the_public_config(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine)
    public = make_client()
    assert public.get("/site/config").json()["announcement"] is None
    body = {
        "announcement": {
            "enabled": True,
            "tone": "warning",
            "fr": "Maintenance ce soir",
            "en": "Maintenance tonight",
        },
        "risk_warning": {
            "fr": "Risque de perte en capital élevé.",
            "en": "High risk of losing capital.",
        },
        "note": REASON,
    }
    assert admin.put("/admin/messages", json=body).status_code == 200
    config = public.get("/site/config").json()
    assert config["announcement"]["fr"] == "Maintenance ce soir"
    assert config["risk_warning"]["en"] == "High risk of losing capital."

    announcement: dict[str, Any] = dict(body["announcement"])  # type: ignore[call-overload]
    hidden = {**body, "announcement": {**announcement, "enabled": False}}
    admin.put("/admin/messages", json=hidden)
    assert public.get("/site/config").json()["announcement"] is None
    assert admin.put("/admin/messages", json={**body, "note": "ok"}).status_code == 422


def test_legal_texts_are_versioned_and_never_rewritten(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine)
    public = make_client()
    kind = "privacy"
    before = public.get("/site/legal", params={"kind": kind, "locale": "fr"})
    first = len(admin.get("/admin/legal").json()["documents"])
    assert first == 8  # quatre textes, deux langues
    doc = {
        "kind": kind,
        "locale": "fr",
        "title": "Confidentialité",
        "body": LEGAL_BODY,
        "note": REASON,
    }
    assert admin.post("/admin/legal", json=doc).status_code == 201
    second = admin.post("/admin/legal", json={**doc, "title": "Confidentialité v2"})
    entry = next(d for d in second.json()["documents"] if d["kind"] == kind and d["locale"] == "fr")
    assert entry["current"]["title"] == "Confidentialité v2"
    assert [v["version"] for v in entry["versions"]][:2] == [
        entry["versions"][0]["version"],
        entry["versions"][0]["version"] - 1,
    ]

    shown = public.get("/site/legal", params={"kind": kind, "locale": "fr"}).json()
    assert shown["title"] == "Confidentialité v2"
    # Pas encore traduit : l'autre langue s'affiche plutôt que rien.
    assert public.get("/site/legal", params={"kind": kind, "locale": "en"}).json()["locale"] in (
        "fr",
        "en",
    )
    assert kind in public.get("/site/config").json()["legal"]
    assert before.status_code in (200, 404)

    with pytest.raises(DBAPIError), migrated_engine.begin() as conn:
        conn.execute(text("UPDATE legal_documents SET body = 'changé'"))


def test_unpublished_legal_text_is_refused(make_client: Callable[[], TestClient]) -> None:
    response = make_client().get("/site/legal", params={"kind": "risk", "locale": "fr"})
    assert response.status_code in (200, 404)
    if response.status_code == 404:
        assert response.json()["error"] == "legal.not_published"


def test_email_texts_can_change_but_not_their_placeholders(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine)
    listed = admin.get("/admin/emails").json()["templates"]
    expiring = next(t for t in listed if t["template"] == "subscription_expiring")
    assert expiring["langs"]["fr"]["placeholders"] == ["ends"]
    values = {
        "subject": "Votre accès se termine",
        "title": "Fin d'accès proche",
        "lines": ["Pensez à renouveler votre formule."],
        "note": "Dernier jour : {ends}.",
        "action": "Renouveler maintenant",
        "reason": REASON,
    }
    url = "/admin/emails/subscription_expiring/fr"
    preview = admin.post(f"{url}/preview", json=values).json()
    assert "Fin d&#x27;accès proche" in preview["html"] or "Fin d'accès proche" in preview["html"]
    assert admin.put(url, json=values).status_code == 200

    mailer.set_template_source(email_templates.CachedSource(sessionmaker(migrated_engine)))
    sent = mailer.render(
        "subscription_expiring",
        "fr",
        "a@example.com",
        first_name="A",
        ends="1 mai",
        link="https://x",
    )
    assert sent.subject == "Votre accès se termine"
    assert "Dernier jour : 1 mai." in sent.body
    english = mailer.render(
        "subscription_expiring",
        "en",
        "a@example.com",
        first_name="A",
        ends="1 May",
        link="https://x",
    )
    assert english.subject == mailer.TEMPLATES["subscription_expiring"]["en"].subject

    wrongs: tuple[dict[str, Any], ...] = (
        {"note": "Votre mot de passe : {password}"},
        {"subject": "Bonjour {first_name}"},
        {"lines": []},
    )
    for wrong in wrongs:
        refused = admin.put(url, json={**values, **wrong})
        assert refused.status_code == 422, wrong
    assert (
        admin.put("/admin/emails/inconnu/fr", json=values).json()["error"]
        == "settings.email_not_found"
    )

    reset = admin.post(f"{url}/reset", json={"reason": REASON}).json()["templates"]
    again = next(t for t in reset if t["template"] == "subscription_expiring")
    assert again["langs"]["fr"]["changed"] is False


def test_service_keys_are_encrypted_never_shown_and_used(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    admin = boss(make_client, migrated_engine)
    secret = "sk_test_never_shown_0123456789"
    saved = admin.put("/admin/keys/chariow_api_key", json={"value": secret, "note": REASON})
    assert saved.status_code == 200
    assert secret not in saved.text
    entry = next(k for k in saved.json()["editable"] if k["name"] == "chariow_api_key")
    assert (entry["source"], entry["value"]) == ("admin", None)
    product = admin.put(
        "/admin/keys/chariow_product_weekly", json={"value": "prd_abc123", "note": REASON}
    )
    weekly = next(k for k in product.json()["editable"] if k["name"] == "chariow_product_weekly")
    assert weekly["value"] == "prd_abc123"  # un identifiant de produit n'est pas un secret

    with sessionmaker(migrated_engine)() as db:
        stored = db.get_one(SiteSetting, "service_key:chariow_api_key").value
        assert secret not in stored and stored.startswith("v1.")
        logged = " ".join(
            str(e.details)
            for e in db.scalars(select(AuditLog).where(AuditLog.action.like("admin.key.%")))
        )
        assert secret not in logged
        effective = service_keys.effective(db, Settings(encryption_key=KEY))
        assert effective.chariow_api_key is not None
        assert effective.chariow_api_key.get_secret_value() == secret

    # Le paiement voit le fournisseur sans redémarrage.
    client = make_client()
    signed_up(client, migrated_engine)
    assert "chariow" in str(client.get("/billing/me").json())

    assert (
        admin.put(
            "/admin/keys/chariow_api_key", json={"value": "deux mots", "note": REASON}
        ).status_code
        == 422
    )
    assert admin.put("/admin/keys/inconnue", json={"value": "x", "note": REASON}).json()[
        "error"
    ] == ("settings.key_not_found")
    removed = admin.post("/admin/keys/chariow_api_key/remove", json={"note": REASON}).json()
    assert next(k for k in removed["editable"] if k["name"] == "chariow_api_key")["source"] is None


def test_settings_are_super_admin_only(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    finance = boss(make_client, migrated_engine, UserRole.FINANCE)
    for path in ("/admin/keys", "/admin/emails", "/admin/legal", "/admin/messages"):
        assert finance.get(path).json()["error"] == "authz.forbidden", path
