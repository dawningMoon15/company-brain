"""
security.py — Password hashing utilities

Uses bcrypt directly (not via passlib) because passlib 1.7.4 has a broken
wrap-bug detection step that crashes on Python 3.14 with newer bcrypt builds.

All other modules should call these two functions rather than touching bcrypt
directly.
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a plaintext password and return the bcrypt digest as a UTF-8 string.
    Call this once at signup before writing to the database.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare a plaintext password against the stored bcrypt hash.
    Returns True if they match, False otherwise.
    Call this at login to authenticate the user.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )
