"""
Envoi des e-mails transactionnels.

Le fournisseur d'e-mails n'est pas encore choisi (dépense externe : décision du
propriétaire). En développement, les messages sont écrits dans le journal de
l'API ; hors développement, aucun envoi n'est simulé et l'API refuse de démarrer.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("safetrade.mail")

# Textes traduits (section 15 : e-mails en français et en anglais).
TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "verify_email": {
        "fr": (
            "Confirmez votre adresse e-mail SafeTrade",
            "Bonjour {first_name},\n\n"
            "Confirmez votre adresse pour activer votre compte :\n{link}\n\n"
            "Ce lien expire dans {hours} heures. "
            "Si vous n'êtes pas à l'origine de cette inscription, ignorez ce message.",
        ),
        "en": (
            "Confirm your SafeTrade email address",
            "Hello {first_name},\n\n"
            "Confirm your address to activate your account:\n{link}\n\n"
            "This link expires in {hours} hours. If you did not sign up, ignore this message.",
        ),
    },
    "already_registered": {
        "fr": (
            "Tentative d'inscription avec votre adresse",
            "Bonjour {first_name},\n\n"
            "Quelqu'un a tenté de créer un compte SafeTrade avec votre adresse, "
            "qui en possède déjà un. Pour vous connecter : {link}\n\n"
            "Si ce n'était pas vous, aucune action n'est nécessaire.",
        ),
        "en": (
            "Sign-up attempt with your address",
            "Hello {first_name},\n\n"
            "Someone tried to create a SafeTrade account with your address, "
            "which already has one. To sign in: {link}\n\n"
            "If this was not you, no action is needed.",
        ),
    },
}


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str
    template: str


def render(template: str, locale: str, to: str, **values: object) -> Email:
    subject, body = TEMPLATES[template]["en" if locale == "en" else "fr"]
    return Email(to=to, subject=subject, body=body.format(**values), template=template)


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
