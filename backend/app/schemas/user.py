"""
user.py — Pydantic schemas for User data shapes

Separate from the SQLAlchemy ORM model (app/models/user.py).
These schemas control what data comes IN (requests) and goes OUT (responses).
"""

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """
    Input schema for POST /signup.
    Validates that email is a well-formed address and password is present.
    """
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """
    Output schema — what we return to the client after signup or /me.
    We deliberately omit the password hash from all responses.
    """
    id: str
    email: EmailStr

    model_config = {"from_attributes": True}  # lets Pydantic read SQLAlchemy ORM objects
