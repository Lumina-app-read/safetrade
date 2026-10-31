"""Envoi des e-mails : gabarits, SMTP chiffré, file, renvoi du lien. Aucun envoi réel."""

import logging
import re
import smtplib
import uuid
from collections.abc import Iterator
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.auth import mailer as mail
from app.auth.mailer import (
    TEMPLATES,
    Email,
    MemoryMailer,
    QueuedMailer,
    SmtpMailer,
    build_mailer,
    build_message,
    render,
)
from app.auth.rate_limit import MemoryFailureCounter
from app.config import Settings
from app.main import create_app
from tests.conftest import requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"
LINK = "https://safetrade.test/fr/verify-email?token=abc&x=1"


@pytest.mark.parametrize("template", list(TEMPLATES))
@pytest.mark.parametrize("locale", ["fr", "en"])
def test_every_template_renders_text_and_html(template: str, locale: str) -> None:
    email = render(
        template, locale, "a@example.com", first_name="Ada", link=LINK, hours=24, minutes=60
    )
    assert "Ada" in email.body
    assert "Ada" in email.html
    assert "{" not in email.body
    assert email.html.startswith("<!doctype html>")
    assert f'lang="{locale}"' in email.html
    if TEMPLATES[template][locale].action:
        assert LINK in email.body
        assert "token=abc&amp;x=1" in email.html


def test_first_name_cannot_inject_html() -> None:
    email = render(
        "verify_email", "fr", "a@example.com",
        first_name='<img src=x onerror="alert(1)">', link=LINK, hours=24,
    )  # fmt: skip
    assert "<img" not in email.html
    assert "&lt;img" in email.html


def sample() -> Email:
    return render("verify_email", "fr", "a@example.com", first_name="Ada", link=LINK, hours=24)


def test_message_has_text_and_html_parts() -> None:
    message = build_message(sample(), "no-reply@safetrade.test", "SafeTrade")
    assert message["From"] == "SafeTrade <no-reply@safetrade.test>"
    assert message["Message-ID"].endswith("@safetrade.test>")
    assert {p.get_content_type() for p in message.walk()} >= {"text/plain", "text/html"}


def test_header_injection_is_refused() -> None:
    bad = Email(to="a@example.com\nBcc: b@example.com", subject="x", body="x", template="t")
    with pytest.raises(ValueError, match=r"linefeed|newline"):
        build_message(bad, "no-reply@safetrade.test", "SafeTrade")


class FakeSmtp:
    calls: ClassVar[list[str]] = []

    def __init__(self, *_: Any, **__: Any) -> None: ...

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *_: object) -> None: ...

    def starttls(self, **_: Any) -> None:
        self.calls.append("starttls")

    def login(self, *_: str) -> None:
        self.calls.append("login")

    def send_message(self, *_: Any) -> None:
        self.calls.append("send")


def smtp(port: int) -> SmtpMailer:
    return SmtpMailer("smtp.test", port, "user", "secret", "no-reply@safetrade.test", "SafeTrade")


def test_encryption_comes_before_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSmtp.calls = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    smtp(587).send(sample())
    assert FakeSmtp.calls == ["starttls", "login", "send"]


def test_port_465_uses_implicit_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSmtp.calls = []
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtp)
    smtp(465).send(sample())
    assert FakeSmtp.calls == ["login", "send"]


class Flaky:
    def __init__(self, failures: list[Exception]) -> None:
        self.failures = failures
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append(email)


def test_queue_retries_after_temporary_failure() -> None:
    inner = Flaky([OSError("coupure"), smtplib.SMTPServerDisconnected("coupé")])
    queued = QueuedMailer(inner, delays=(0, 0, 0))
    queued.send(sample())
    queued.wait()
    assert len(inner.sent) == 1


def test_queue_gives_up_and_logs_without_address_or_link(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Alembic désactive les journaux déjà créés quand une base de test est migrée.
    monkeypatch.setattr(mail.logger, "disabled", False)
    inner = Flaky([OSError("x")] * 5)
    queued = QueuedMailer(inner, delays=(0, 0))
    with caplog.at_level(logging.INFO, "safetrade.mail"):
        queued.send(sample())
        queued.wait()
    assert inner.sent == []
    assert "a@example.com" not in caplog.text
    assert "token=" not in caplog.text
    failed = [r for r in caplog.records if getattr(r, "event", "") == "mail.failed"]
    assert len(failed) == 1


def test_refused_recipient_is_not_retried() -> None:
    inner = Flaky([smtplib.SMTPRecipientsRefused({})])
    queued = QueuedMailer(inner, delays=(0, 0, 0))
    queued.send(sample())
    queued.wait()
    assert inner.failures == []
    assert inner.sent == []


def test_mailer_needs_complete_configuration() -> None:
    assert build_mailer(Settings(environment="test")) is None
    assert build_mailer(Settings(environment="test", smtp_host="", smtp_user="u")) is None
    built = build_mailer(
        Settings(
            environment="test",
            smtp_host="smtp.test",
            smtp_user="u",
            smtp_password="p",
            smtp_from="no-reply@safetrade.test",
        )
    )
    assert isinstance(built, QueuedMailer)


def test_api_refuses_to_start_without_provider_outside_development() -> None:
    with pytest.raises(RuntimeError, match="e-mails"):
        create_app(
            Settings(
                environment="staging",
                encryption_key="a" * 44,
                redis_url="redis://127.0.0.1:1/0",
            )
        )


def test_smtp_password_is_never_in_settings_repr() -> None:
    settings = Settings(environment="test", smtp_password="tres-secret")
    assert "tres-secret" not in repr(settings)
    assert mail.SMTP_TIMEOUT_SECONDS > 0


@pytest.fixture
def api(migrated_engine: Engine) -> Iterator[tuple[TestClient, MemoryMailer, Engine]]:
    mailer = MemoryMailer()
    app = create_app(
        Settings(
            environment="test",
            session_cookie_secure=False,
            allowed_origins=[ORIGIN],
            verification_max_per_hour=3,
        ),
        session_factory=sessionmaker(migrated_engine, expire_on_commit=False),
        mailer=mailer,
        failures=MemoryFailureCounter(),
    )
    with TestClient(app, base_url="http://127.0.0.1:18000", headers={"origin": ORIGIN}) as client:
        yield client, mailer, migrated_engine


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "first_name": "Ada",
            "locale": "fr",
            "accept_risk": True,
        },
    )
    assert response.status_code == 202


def email_address() -> str:
    return f"mail-{uuid.uuid4().hex[:8]}@example.com"


def templates(mailer: MemoryMailer, email: str) -> list[str]:
    return [m.template for m in mailer.sent if m.to == email]


@requires_db
def test_resend_gives_a_working_link(api: Any) -> None:
    client, mailer, _ = api
    email = email_address()
    register(client, email)
    response = client.post("/auth/verify-email/resend", json={"email": email})
    assert (response.status_code, response.json()) == (202, {"status": "verification_sent"})
    assert templates(mailer, email) == ["verify_email", "verify_email"]
    token = re.search(r"token=([\w-]+)", mailer.sent[-1].body)
    assert token is not None
    assert client.post("/auth/verify-email", json={"token": token.group(1)}).status_code == 200


@requires_db
def test_resend_answers_the_same_for_unknown_and_verified_addresses(api: Any) -> None:
    client, mailer, engine = api
    unknown = client.post("/auth/verify-email/resend", json={"email": email_address()})
    email = email_address()
    register(client, email)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET email_verified_at = now() WHERE email = :e"), {"e": email}
        )
    verified = client.post("/auth/verify-email/resend", json={"email": email})
    assert unknown.json() == verified.json()
    assert unknown.status_code == verified.status_code == 202
    assert templates(mailer, email) == ["verify_email"]


@requires_db
def test_mails_to_one_address_are_capped_silently(api: Any) -> None:
    client, mailer, _ = api
    email = email_address()
    register(client, email)
    for _ in range(6):
        assert client.post("/auth/verify-email/resend", json={"email": email}).status_code == 202
    assert len(templates(mailer, email)) == 4  # inscription, puis 3 renvois


@requires_db
def test_confirmed_owner_is_warned_on_second_registration(api: Any) -> None:
    client, mailer, engine = api
    email = email_address()
    register(client, email)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET email_verified_at = now() WHERE email = :e"), {"e": email}
        )
    register(client, email)
    assert templates(mailer, email) == ["verify_email", "already_registered"]
