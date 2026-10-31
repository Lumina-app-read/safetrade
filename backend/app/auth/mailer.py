"""
Envoi des e-mails transactionnels, par SMTP (Brevo, décision q15).

L'envoi part d'une file : une requête n'attend jamais le fournisseur, et le temps de réponse
ne révèle pas si une adresse possède un compte. En développement sans fournisseur configuré,
les messages vont au journal ; hors développement, l'API refuse alors de démarrer.
"""

import html
import logging
import queue
import smtplib
import ssl
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Protocol

from app.config import Settings

logger = logging.getLogger("safetrade.mail")

SMTP_TIMEOUT_SECONDS = 20
RETRY_DELAYS_SECONDS = (5.0, 30.0, 120.0)
QUEUE_SIZE = 1000

# Couleurs de l'identité : un e-mail n'a pas accès aux variables de thème du site.
BRAND_RED = "#D6041D"
ANTHRACITE = "#202329"
RED_ON_DARK = "#FF3B4E"
TEXT = "#202329"
MUTED = "#5B616E"
LINE = "#E4E6EB"
PAGE = "#F4F5F7"


@dataclass(frozen=True)
class Template:
    subject: str
    title: str
    lines: tuple[str, ...]
    note: str
    action: str | None = None


GREETING = {"fr": "Bonjour {first_name},", "en": "Hello {first_name},"}
FALLBACK = {
    "fr": "Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :",
    "en": "If the button does not work, copy this link into your browser:",
}
FOOTER = {
    "fr": (
        "Message automatique de SafeTrade. "
        "Nous ne vous demanderons jamais votre mot de passe par e-mail."
    ),
    "en": ("Automatic message from SafeTrade. We will never ask for your password by email."),
}

# Textes traduits (section 15 : e-mails en français et en anglais).
TEMPLATES: dict[str, dict[str, Template]] = {
    "verify_email": {
        "fr": Template(
            "Confirmez votre adresse e-mail SafeTrade",
            "Confirmez votre adresse e-mail",
            ("Il reste une étape pour activer votre compte SafeTrade.",),
            "Ce lien expire dans {hours} heures. "
            "Si vous n'êtes pas à l'origine de cette inscription, ignorez ce message.",
            "Confirmer mon adresse",
        ),
        "en": Template(
            "Confirm your SafeTrade email address",
            "Confirm your email address",
            ("One step left to activate your SafeTrade account.",),
            "This link expires in {hours} hours. If you did not sign up, ignore this message.",
            "Confirm my address",
        ),
    },
    "already_registered": {
        "fr": Template(
            "Tentative d'inscription avec votre adresse",
            "Votre adresse possède déjà un compte",
            ("Quelqu'un a tenté de créer un compte SafeTrade avec votre adresse.",),
            "Si ce n'était pas vous, aucune action n'est nécessaire.",
            "Me connecter",
        ),
        "en": Template(
            "Sign-up attempt with your address",
            "Your address already has an account",
            ("Someone tried to create a SafeTrade account with your address.",),
            "If this was not you, no action is needed.",
            "Sign in",
        ),
    },
    "reset_password": {
        "fr": Template(
            "Réinitialisez votre mot de passe SafeTrade",
            "Choisissez un nouveau mot de passe",
            ("Vous avez demandé à réinitialiser votre mot de passe SafeTrade.",),
            "Ce lien expire dans {minutes} minutes. "
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
            "Choisir un mot de passe",
        ),
        "en": Template(
            "Reset your SafeTrade password",
            "Choose a new password",
            ("You asked to reset your SafeTrade password.",),
            "This link expires in {minutes} minutes. "
            "If you did not request this, ignore this message.",
            "Choose a password",
        ),
    },
    "payment_received": {
        "fr": Template(
            "Votre paiement SafeTrade est confirmé",
            "Paiement confirmé",
            ("Merci, votre abonnement SafeTrade est actif.",),
            "Montant : {amount}. Accès valable jusqu'au {ends}. Conservez ce message comme reçu.",
            "Voir mon abonnement",
        ),
        "en": Template(
            "Your SafeTrade payment is confirmed",
            "Payment confirmed",
            ("Thank you, your SafeTrade subscription is active.",),
            "Amount: {amount}. Access valid until {ends}. Keep this message as your receipt.",
            "View my subscription",
        ),
    },
    "affiliate_approved": {
        "fr": Template(
            "Votre demande d'affiliation SafeTrade est acceptée",
            "Vous êtes affilié SafeTrade",
            ("Votre lien de parrainage est prêt dans votre espace.",),
            "Votre code : {code}. Ne promettez jamais de gain : "
            "le trading comporte un risque de perte en capital.",
            "Voir mon espace affilié",
        ),
        "en": Template(
            "Your SafeTrade affiliate application is approved",
            "You are a SafeTrade affiliate",
            ("Your referral link is ready in your area.",),
            "Your code: {code}. Never promise gains: trading carries a risk of capital loss.",
            "View my affiliate area",
        ),
    },
    "affiliate_refused": {
        "fr": Template(
            "Votre demande d'affiliation SafeTrade",
            "Demande non retenue",
            ("Votre demande d'affiliation n'a pas été retenue pour le moment.",),
            "Vous pouvez déposer une nouvelle demande depuis votre espace.",
            "Voir mon espace affilié",
        ),
        "en": Template(
            "Your SafeTrade affiliate application",
            "Application not accepted",
            ("Your affiliate application was not accepted at this time.",),
            "You can submit a new application from your area.",
            "View my affiliate area",
        ),
    },
    "affiliate_payout": {
        "fr": Template(
            "Votre versement d'affiliation SafeTrade",
            "Versement enregistré",
            ("Un versement a été enregistré pour vos commissions.",),
            "Montant : {amount}. Le détail figure dans votre espace affilié.",
            "Voir mon espace affilié",
        ),
        "en": Template(
            "Your SafeTrade affiliate payout",
            "Payout recorded",
            ("A payout was recorded for your commissions.",),
            "Amount: {amount}. The details are in your affiliate area.",
            "View my affiliate area",
        ),
    },
    "subscription_expiring": {
        "fr": Template(
            "Votre accès SafeTrade se termine bientôt",
            "Votre accès se termine bientôt",
            ("Sans renouvellement, le bot ne pourra plus ouvrir de position.",),
            "Fin de l'accès : {ends}.",
            "Renouveler",
        ),
        "en": Template(
            "Your SafeTrade access ends soon",
            "Your access ends soon",
            ("Without renewal, the bot will no longer open positions.",),
            "Access ends: {ends}.",
            "Renew",
        ),
    },
    "password_changed": {
        "fr": Template(
            "Votre mot de passe SafeTrade a été modifié",
            "Votre mot de passe a été modifié",
            ("Votre mot de passe vient d'être modifié et vos appareils ont été déconnectés.",),
            "Si ce n'était pas vous, contactez immédiatement le support.",
        ),
        "en": Template(
            "Your SafeTrade password was changed",
            "Your password was changed",
            ("Your password has just been changed and your devices were signed out.",),
            "If this was not you, contact support immediately.",
        ),
    },
}


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str
    template: str
    html: str = field(default="", repr=False)


def _html_page(
    lang: str, title: str, greeting: str, template: Template, note: str, link: str
) -> str:
    """Mise en page par tableaux et styles en ligne : seule forme fiable dans les messageries."""
    text = "".join(
        f'<p style="margin:0 0 16px;font-size:15px;line-height:24px;color:{TEXT};">'
        f"{html.escape(line)}</p>"
        for line in (greeting, *template.lines)
    )
    button = ""
    if template.action and link:
        safe = html.escape(link, quote=True)
        button = (
            '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 24px;">'
            f'<tr><td style="border-radius:8px;background:{BRAND_RED};">'
            f'<a href="{safe}" style="display:inline-block;padding:14px 24px;font-size:15px;'
            f'font-weight:600;color:#FFFFFF;text-decoration:none;">'
            f"{html.escape(template.action)}</a></td></tr></table>"
            f'<p style="margin:0 0 4px;font-size:13px;line-height:20px;color:{MUTED};">'
            f"{html.escape(FALLBACK[lang])}</p>"
            f'<p style="margin:0 0 24px;font-size:13px;line-height:20px;word-break:break-all;">'
            f'<a href="{safe}" style="color:{BRAND_RED};">{safe}</a></p>'
        )
    return (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(template.subject)}</title></head>"
        f'<body style="margin:0;padding:0;background:{PAGE};'
        'font-family:Arial,Helvetica,sans-serif;">'
        f'<div style="display:none;max-height:0;overflow:hidden;">{html.escape(title)}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td align="center" style="padding:32px 16px;background:{PAGE};">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="max-width:560px;background:#FFFFFF;border:1px solid {LINE};'
        'border-radius:12px;overflow:hidden;">'
        f'<tr><td style="padding:20px 32px;background:{ANTHRACITE};font-size:20px;'
        'font-weight:600;color:#FFFFFF;">'
        f'Safe<span style="color:{RED_ON_DARK};">Trade</span></td></tr>'
        '<tr><td style="padding:32px;">'
        f'<h1 style="margin:0 0 20px;font-size:22px;line-height:30px;font-weight:500;'
        f'color:{TEXT};">{html.escape(title)}</h1>'
        f"{text}{button}"
        f'<p style="margin:0;font-size:13px;line-height:20px;color:{MUTED};">'
        f"{html.escape(note)}</p></td></tr>"
        f'<tr><td style="padding:16px 32px;border-top:1px solid {LINE};font-size:12px;'
        f'line-height:18px;color:{MUTED};">{html.escape(FOOTER[lang])}</td></tr>'
        "</table></td></tr></table></body></html>"
    )


def render(template: str, locale: str, to: str, **values: object) -> Email:
    lang = "en" if locale == "en" else "fr"
    item = TEMPLATES[template][lang]
    greeting = GREETING[lang].format(**values)
    note = item.note.format(**values)
    link = str(values.get("link", ""))
    parts = [greeting, *item.lines]
    if item.action and link:
        parts.append(f"{item.action} :\n{link}" if lang == "fr" else f"{item.action}:\n{link}")
    parts.append(note)
    return Email(
        to=to,
        subject=item.subject,
        body="\n\n".join(parts),
        template=template,
        html=_html_page(lang, item.title, greeting, item, note, link),
    )


class Mailer(Protocol):
    def send(self, email: Email) -> None: ...


class LogMailer:
    """Développement uniquement : le message (lien compris) est écrit dans le journal local."""

    def send(self, email: Email) -> None:
        logger.warning(
            "E-MAIL DE DÉVELOPPEMENT pour %s : %s\n%s", email.to, email.subject, email.body
        )


class MemoryMailer:
    """Tests : les messages sont conservés pour inspection."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


def build_message(email: Email, sender: str, sender_name: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((sender_name, sender))
    message["To"] = email.to
    message["Subject"] = email.subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1])
    message.set_content(email.body)
    if email.html:
        message.add_alternative(email.html, subtype="html")
    return message


class SmtpMailer:
    """Une connexion chiffrée par envoi : la cadence transactionnelle reste faible."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sender: str,
        sender_name: str,
        *,
        timeout: float = SMTP_TIMEOUT_SECONDS,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._sender = sender
        self._sender_name = sender_name
        self._timeout = timeout

    def send(self, email: Email) -> None:
        message = build_message(email, self._sender, self._sender_name)
        context = ssl.create_default_context()
        if self._port == 465:
            with smtplib.SMTP_SSL(
                self._host, self._port, timeout=self._timeout, context=context
            ) as client:
                client.login(self._user, self._password)
                client.send_message(message)
            return
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
            # Jamais d'envoi en clair : starttls échoue si le serveur ne le propose pas.
            client.starttls(context=context)
            client.login(self._user, self._password)
            client.send_message(message)


class QueuedMailer:
    """
    File en mémoire avec nouvelles tentatives. Un envoi perdu n'empêche pas de s'inscrire :
    le client peut redemander le lien. Journal : modèle et cause, jamais l'adresse ni le lien.
    """

    def __init__(self, inner: Mailer, *, delays: Sequence[float] = RETRY_DELAYS_SECONDS) -> None:
        self._inner = inner
        self._delays = delays
        self._queue: queue.Queue[Email] = queue.Queue(maxsize=QUEUE_SIZE)
        threading.Thread(target=self._work, name="mail", daemon=True).start()

    def send(self, email: Email) -> None:
        try:
            self._queue.put_nowait(email)
        except queue.Full:
            logger.error(
                "file d'e-mails pleine",
                extra={"event": "mail.queue_full", "template": email.template},
            )

    def wait(self) -> None:
        self._queue.join()

    def _work(self) -> None:
        while True:
            email = self._queue.get()
            try:
                self._deliver(email)
            finally:
                self._queue.task_done()

    def _deliver(self, email: Email) -> None:
        for delay in (*self._delays, None):
            try:
                self._inner.send(email)
            except smtplib.SMTPRecipientsRefused as exc:
                self._failed(email, exc)  # adresse refusée : réessayer ne changerait rien
                return
            except (OSError, smtplib.SMTPException) as exc:
                if delay is None:
                    self._failed(email, exc)
                    return
                time.sleep(delay)
            else:
                logger.info(
                    "e-mail envoyé", extra={"event": "mail.sent", "template": email.template}
                )
                return

    @staticmethod
    def _failed(email: Email, exc: Exception) -> None:
        logger.error(
            "e-mail non envoyé",
            extra={
                "event": "mail.failed",
                "template": email.template,
                "reason": type(exc).__name__,
            },
        )


def build_mailer(settings: Settings) -> Mailer | None:
    """Fournisseur réel si la configuration est complète, sinon None."""
    password = settings.smtp_password.get_secret_value() if settings.smtp_password else ""
    if not (settings.smtp_host and settings.smtp_user and password and settings.smtp_from):
        return None
    return QueuedMailer(
        SmtpMailer(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_user,
            password,
            settings.smtp_from,
            settings.smtp_from_name,
        )
    )
