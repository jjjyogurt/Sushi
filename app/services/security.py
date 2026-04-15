from __future__ import annotations

import hashlib
import secrets


def hash_password(password: str, *, salt: str | None = None) -> str:
    normalized_password = str(password or "")
    normalized_salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        normalized_password.encode("utf-8"),
        normalized_salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"pbkdf2_sha256${normalized_salt}${derived}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, expected = str(password_hash or "").split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256" or not salt or not expected:
        return False
    actual_hash = hash_password(password, salt=salt)
    return secrets.compare_digest(actual_hash, password_hash)


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(str(raw_token or "").encode("utf-8")).hexdigest()
