"""
Journaux structurés : une ligne JSON par événement, lisible par un collecteur.

Les champs proviennent uniquement du paramètre `extra` choisi par le code appelant ; un jeton
ou un OTP n'y figure jamais.
"""

import json
import logging
from datetime import UTC, datetime

_STANDARD = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD})
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = record.exc_info[0].__name__
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_json_logs() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
