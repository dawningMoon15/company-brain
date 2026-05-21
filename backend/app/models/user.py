"""
user.py — SQLAlchemy ORM model for the `users` table

Columns:
  id       → UUID stored as a string (primary key, auto-generated)
  email    → unique, non-nullable
  password → hashed password string, non-nullable
"""

import uuid
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    # Primary key: UUID generated in Python so it works across all DB drivers
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    # Email must be unique and is required
    email = Column(String, unique=True, nullable=False, index=True)

    # Password (store the hashed value — never plaintext)
    password = Column(String, nullable=False)

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"

    # ── Relationships ─────────────────────────────────────────────────────────
    # Populated automatically by SQLAlchemy — do not set manually.
    # back_populates mirrors Workspace.owner on the other side.
    workspaces = relationship(
        "Workspace",
        back_populates="owner",
        cascade="all, delete-orphan",  # deleting user removes their workspaces
    )
