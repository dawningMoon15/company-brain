"""
auth.py — FastAPI dependency for protected routes

get_current_user() is injected via Depends() into any route that requires
an authenticated user. It:
  1. Extracts the Bearer token from the Authorization header
  2. Decodes and validates the JWT
  3. Loads the corresponding User row from the database
  4. Returns the User ORM object, or raises HTTP 401 if anything is wrong
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.utils.jwt import decode_access_token

# Tells FastAPI where clients obtain a token (used by Swagger's Authorize button)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# Reusable 401 exception — raised whenever auth fails
_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — inject this into any route to protect it.

    Usage:
        @router.get("/me")
        def me(current_user: User = Depends(get_current_user)):
            ...
    """
    # 1. Decode and validate the JWT
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise _CREDENTIALS_EXCEPTION
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    # 2. Fetch user from DB — token is valid but user may have been deleted
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user
