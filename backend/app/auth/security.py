"""Mots de passe (Argon2id) et jetons opaques (seule leur empreinte est stockée)."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Paramètres par défaut d'argon2-cffi : Argon2id, profil RFC 9106 « faible mémoire ».
_hasher = PasswordHasher()

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

# Empreinte calculée une fois : vérifier un mot de passe pour un compte inexistant
# prend le même temps que pour un compte réel (pas d'énumération par la durée).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problem(password: str, email: str) -> str | None:
    """Code d'erreur si le mot de passe est refusé, sinon None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return "auth.password_too_short"
    if len(password) > PASSWORD_MAX_LENGTH:
        return "auth.password_too_long"
    if password.strip().lower() == email.strip().lower() or len(set(password)) < 4:
        return "auth.password_too_weak"
    return None


def new_token() -> str:
    """Jeton aléatoire de 256 bits, transmis une seule fois au client."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()
