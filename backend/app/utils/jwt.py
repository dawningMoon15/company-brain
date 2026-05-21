"""
jwt.py — JWT creation and decoding utilities

Tokens are signed with HS256 using the JWT_SECRET from .env.
Expiry is fixed at 60 minutes — no refresh tokens.
"""

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
_SECRET_KEY: str = os.getenv("JWT_SECRET", "")
_ALGORITHM: str = "HS256"
_EXPIRE_MINUTES: int = 60

if not _SECRET_KEY:
    raise ValueError("JWT_SECRET is not set. Add it to your .env file.")


# ── Token creation ────────────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    """
    Build and sign a JWT from the given payload dict.

    Automatically appends an 'exp' (expiry) claim of now + 60 minutes.
    The returned string is what you hand back to the client.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=_EXPIRE_MINUTES)
    payload["exp"] = expire

    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


# ── Token decoding ────────────────────────────────────────────────────────────
def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT string.

    Returns the decoded payload dict on success.
    Raises jose.JWTError if the token is invalid, expired, or tampered with.
    Callers are responsible for catching JWTError and converting to HTTP 401.
    """
    return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
