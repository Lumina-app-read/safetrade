"""
E-mails types modifiables dans l'administration, en français et en anglais.

Seuls les textes changent : la mise en page, le lien et l'expéditeur restent dans le code. Une
variable (« {ends} ») n'est acceptée que là où le texte par défaut l'emploie : un texte modifié
ne peut ni casser l'envoi ni afficher une donnée qui n'était pas prévue.
"""

import json
import re
import string
import time
import uuid
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from app.auth import mailer
from app.db.models import SiteSetting
from app.errors import ApiError

KEY = "email_templates"
CACHE_SECONDS = 60
LANGS = ("fr", "en")
LIMITS = {"subject": 150, "title": 150, "line": 600, "note": 400, "action": 60}
MAX_LINES = 6


def _names(text: str) -> set[str]:
    try:
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}
    except ValueError as exc:
        raise ApiError(422, "settings.invalid_placeholder") from exc


def read(db: DbSession) -> dict[str, dict[str, dict[str, Any]]]:
    row = db.get(SiteSetting, KEY)
    data: dict[str, dict[str, dict[str, Any]]] = json.loads(row.value) if row else {}
    return data


class CachedSource:
    """Lecture en base, gardée une minute : un envoi d'e-mail n'attend jamais la base."""

    def __init__(self, factory: sessionmaker[DbSession]) -> None:
        self._factory = factory
        self._value: dict[str, dict[str, dict[str, Any]]] = {}
        self._read_at = 0.0

    def __call__(self) -> dict[str, dict[str, dict[str, Any]]]:
        now = time.monotonic()
        if now - self._read_at >= CACHE_SECONDS:
            with self._factory() as db:
                self._value = read(db)
            self._read_at = now
        return self._value


def view(db: DbSession) -> list[dict[str, Any]]:
    changed = read(db)
    result = []
    for name, langs in mailer.TEMPLATES.items():
        entry: dict[str, Any] = {"template": name, "langs": {}}
        for lang in LANGS:
            base = langs[lang]
            values = changed.get(name, {}).get(lang)
            current = _merged(base, values) if values else base
            entry["langs"][lang] = {
                "default": asdict(base),
                "current": asdict(current),
                "changed": lang in changed.get(name, {}),
                "placeholders": sorted(_names(base.note)),
            }
        result.append(entry)
    return result


def _merged(base: mailer.Template, values: dict[str, Any]) -> mailer.Template:
    return mailer.Template(
        subject=values.get("subject", base.subject),
        title=values.get("title", base.title),
        lines=tuple(values.get("lines", base.lines)),
        note=values.get("note", base.note),
        action=values.get("action", base.action) if base.action else None,
    )


def validate_name(name: str, lang: str) -> None:
    if name not in mailer.TEMPLATES or lang not in LANGS:
        raise ApiError(404, "settings.email_not_found")


def validate(name: str, lang: str, values: dict[str, Any]) -> dict[str, Any]:
    validate_name(name, lang)
    base = mailer.TEMPLATES[name][lang]
    lines = [str(line).strip() for line in values.get("lines", []) if str(line).strip()]
    clean: dict[str, Any] = {
        "subject": str(values.get("subject", "")).strip(),
        "title": str(values.get("title", "")).strip(),
        "lines": lines,
        "note": str(values.get("note", "")).strip(),
    }
    if base.action:
        clean["action"] = str(values.get("action", "")).strip()
    fields = [k for k, v in clean.items() if k != "lines" and not v]
    if not lines or len(lines) > MAX_LINES:
        fields.append("lines")
    for key, value in clean.items():
        texts = value if isinstance(value, list) else [value]
        limit = LIMITS["line" if key == "lines" else key]
        if any(len(text) > limit for text in texts):
            fields.append(key)
    if fields:
        raise ApiError(422, "settings.email_invalid", fields=sorted(set(fields)))
    # Seule la note est remplie avec des variables, et seulement celles du texte par défaut.
    allowed = _names(base.note)
    if not _names(clean["note"]) <= allowed:
        raise ApiError(422, "settings.invalid_placeholder", fields=["note"])
    for key in ("subject", "title", "action"):
        if re.search(r"[{}]", str(clean.get(key, ""))):
            raise ApiError(422, "settings.invalid_placeholder", fields=[key])
    if any(re.search(r"[{}]", line) for line in lines):
        raise ApiError(422, "settings.invalid_placeholder", fields=["lines"])
    return clean


def write(
    db: DbSession, name: str, lang: str, values: dict[str, Any] | None, by: uuid.UUID
) -> None:
    data = read(db)
    if values is None:
        data.get(name, {}).pop(lang, None)
        if name in data and not data[name]:
            del data[name]
    else:
        data.setdefault(name, {})[lang] = values
    row = db.get(SiteSetting, KEY)
    encoded = json.dumps(data, ensure_ascii=False)
    if row is None:
        db.add(SiteSetting(key=KEY, value=encoded, updated_by=by))
    else:
        row.value, row.updated_by = encoded, by


def preview(name: str, lang: str, values: dict[str, Any]) -> dict[str, str]:
    """Rendu d'essai avec des valeurs d'exemple, sans rien envoyer."""
    base = mailer.TEMPLATES[name][lang]
    sample: defaultdict[str, str] = defaultdict(lambda: "...")
    sample.update(
        first_name="Clovis",
        link="https://safetrade.example/lien",
        hours="24",
        minutes="60",
        amount="15,00 $" if lang == "fr" else "$15.00",
        code="SAFE-1234",
        ends="1 décembre 2026" if lang == "fr" else "1 December 2026",
    )
    item = _merged(base, values)
    note = item.note.format_map(sample)
    greeting = mailer.GREETING[lang].format_map(sample)
    return {
        "subject": item.subject,
        "html": mailer._html_page(lang, item.title, greeting, item, note, sample["link"]),
    }
