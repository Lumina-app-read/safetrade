import base64
import os

import pytest

from app import crypto
from app.auth import totp

# Vecteurs officiels de la RFC 6238 (annexe B), SHA-1, clé ASCII « 12345678901234567890 ».
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    ("unix_time", "expected"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_totp_matches_rfc_6238_vectors(unix_time: int, expected: str) -> None:
    assert totp.code_at(RFC_SECRET, unix_time // 30, digits=8) == expected


def test_match_step_accepts_one_step_of_clock_drift() -> None:
    secret = totp.new_secret()
    now = 1_800_000_000.0
    step = totp.current_step(now)
    assert totp.match_step(secret, totp.code_at(secret, step - 1), now) == step - 1
    assert totp.match_step(secret, totp.code_at(secret, step + 1), now) == step + 1
    assert totp.match_step(secret, totp.code_at(secret, step - 3), now) is None
    assert totp.match_step(secret, "12345", now) is None
    assert totp.match_step(secret, "abcdef", now) is None


def test_recovery_codes_are_unique_and_normalized() -> None:
    codes = totp.recovery_codes()
    assert len(set(codes)) == 10
    assert all(len(c) == 9 and c[4] == "-" for c in codes)
    assert totp.recovery_hash(codes[0].lower().replace("-", " ")) == totp.recovery_hash(codes[0])


def test_aes_gcm_roundtrip_and_context_binding() -> None:
    key = os.urandom(32)
    stored = crypto.encrypt(key, "secret-value", "totp:user-1")
    assert stored.startswith("v1.") and "secret-value" not in stored
    assert crypto.decrypt(key, stored, "totp:user-1") == "secret-value"
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(key, stored, "totp:user-2")
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(os.urandom(32), stored, "totp:user-1")


def test_load_key_requires_32_bytes() -> None:
    assert len(crypto.load_key(base64.b64encode(os.urandom(32)).decode())) == 32
    with pytest.raises(crypto.CryptoError):
        crypto.load_key(base64.b64encode(os.urandom(16)).decode())
