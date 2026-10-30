"""
Codes à usage unique basés sur le temps (TOTP, RFC 6238), compatibles avec les
applications d'authentification courantes : HMAC-SHA1, 6 chiffres, pas de 30 s.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

DIGITS = 6
PERIOD = 30
# Tolérance d'un pas avant et après : décalage d'horloge du téléphone.
WINDOW = 1


def new_secret() -> str:
    """Secret de 160 bits encodé en base32, comme l'attendent les applications."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    return base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)


def code_at(secret: str, step: int, digits: int = DIGITS, digest: str = "sha1") -> str:
    mac = hmac.new(_key(secret), struct.pack(">Q", step), digest).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // PERIOD)


def match_step(secret: str, code: str, now: float | None = None) -> int | None:
    """Pas de temps correspondant au code, ou None. Comparaison à temps constant."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    step = current_step(now)
    for candidate in range(step - WINDOW, step + WINDOW + 1):
        if hmac.compare_digest(code_at(secret, candidate), code):
            return candidate
    return None


def provisioning_uri(secret: str, account: str, issuer: str = "SafeTrade") -> str:
    label = quote(f"{issuer}:{account}", safe=":@")
    params = urlencode({"secret": secret, "issuer": issuer, "digits": DIGITS, "period": PERIOD})
    return f"otpauth://totp/{label}?{params}"


def recovery_codes(count: int = 10) -> list[str]:
    """Codes de secours lisibles (« ABCD-EFGH »), 40 bits d'entropie chacun."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0, O, 1, I : pas d'ambiguïté
    return [
        "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2))
        for _ in range(count)
    ]


def normalize_recovery(code: str) -> str:
    raw = code.strip().upper().replace(" ", "").replace("-", "")
    return f"{raw[:4]}-{raw[4:]}" if len(raw) == 8 else raw


def recovery_hash(code: str) -> bytes:
    return hashlib.sha256(normalize_recovery(code).encode()).digest()
