"""
auth.py — Pydantic schemas for authentication request/response shapes
"""

from pydantic import BaseModel, EmailStr


class UserLogin(BaseModel):
    """
    Input schema for POST /login.
    """
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Output schema for POST /login.
    Returns a signed JWT and its type so clients can attach it as:
        Authorization: Bearer <access_token>
    """
    access_token: str
    token_type: str = "bearer"
