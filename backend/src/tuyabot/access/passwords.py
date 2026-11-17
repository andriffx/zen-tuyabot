"""Password hashing with stdlib scrypt.

Format: scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

N = 2**14
R = 8
P = 1
DKLEN = 32
SALT_BYTES = 16
MIN_LENGTH = 8


class WeakPassword(ValueError):
    pass


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode())


def check_strength(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise WeakPassword(f"Password minimal {MIN_LENGTH} karakter")


def hash_password(password: str) -> str:
    check_strength(password)
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=DKLEN)
    return f"scrypt${N}${R}${P}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=_b64d(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64d(hash_b64)),
        )
        return hmac.compare_digest(digest, _b64d(hash_b64))
    except (ValueError, TypeError):
        return False
