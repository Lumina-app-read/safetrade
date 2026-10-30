"""
Chiffrement des secrets au repos (section 14) : AES-256-GCM.

Format stocké : « v1.<base64(nonce de 12 octets + texte chiffré et étiquette)> ».
Le préfixe de version permettra la rotation de clé. Les données associées (AAD)
lient chaque valeur à son usage et à son propriétaire : un secret copié vers une
autre ligne ou un autre usage ne se déchiffre pas.
"""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = "v1"


class CryptoError(Exception):
    pass


def load_key(encoded: str) -> bytes:
    """Clé de 32 octets encodée en base64 (variable SAFETRADE_ENCRYPTION_KEY)."""
    try:
        key = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise CryptoError("clé de chiffrement illisible") from exc
    if len(key) != 32:
        raise CryptoError("la clé de chiffrement doit faire 32 octets")
    return key


def encrypt(key: bytes, plaintext: str, context: str) -> str:
    nonce = os.urandom(12)
    sealed = AESGCM(key).encrypt(nonce, plaintext.encode(), context.encode())
    return f"{VERSION}.{base64.b64encode(nonce + sealed).decode()}"


def decrypt(key: bytes, stored: str, context: str) -> str:
    version, _, payload = stored.partition(".")
    if version != VERSION:
        raise CryptoError("version de chiffrement inconnue")
    raw = base64.b64decode(payload)
    try:
        return AESGCM(key).decrypt(raw[:12], raw[12:], context.encode()).decode()
    except InvalidTag as exc:
        raise CryptoError("donnée chiffrée invalide ou altérée") from exc
