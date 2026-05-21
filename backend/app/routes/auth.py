"""
auth.py — Authentication routes

POST /signup  → register a new user, returns UserResponse
POST /login   → validate credentials, returns JWT TokenResponse
GET  /me      → returns the currently authenticated user (protected)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin
from app.schemas.user import UserCreate, UserResponse
from app.utils.jwt import create_access_token
from app.utils.security import hash_password, verify_password

router = APIRouter(tags=["Auth"])


# ── POST /signup ──────────────────────────────────────────────────────────────
@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account.

    - Rejects duplicate emails with 400
    - Hashes the password before storing
    - Returns the created user (id + email, no password)
    """
    # Guard: reject if email is already registered
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    # Create and persist the new user
    new_user = User(
        email=payload.email,
        password=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # populate auto-generated fields (e.g. id)

    return new_user


# ── POST /login ───────────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT",
)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate with email + password.

    - Returns a signed JWT access token on success
    - Raises 401 if credentials are wrong (deliberately vague to avoid enumeration)
    """
    # Fetch user — use a generic error if not found to avoid user enumeration
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Embed the user's ID as the token subject ("sub" is the JWT standard claim)
    token = create_access_token(data={"sub": user.id})
    return TokenResponse(access_token=token)


# ── GET /me ───────────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user",
)
def me(current_user: User = Depends(get_current_user)):
    """
    Protected route — requires a valid Bearer token in the Authorization header.

    Returns the authenticated user's id and email.
    """
    return current_user
