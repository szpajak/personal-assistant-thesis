from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

import bcrypt
from jose import JWTError, jwt

from ..config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return cast(str, hashed.decode("utf-8"))


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hash using bcrypt."""
    password_bytes = password.encode("utf-8")
    hashed_password_bytes = hashed_password.encode("utf-8")
    try:
        return cast(bool, bcrypt.checkpw(password_bytes, hashed_password_bytes))
    except Exception:
        return False


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return cast(str, jwt.encode(to_encode, settings.secret_key, algorithm="HS256"))


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return cast(dict[str, Any], payload)
    except JWTError as exc:
        raise RuntimeError("Invalid token") from exc
