"""
workspace.py — SQLAlchemy ORM model for the `workspaces` table

Each workspace is owned by a single user and acts as an isolation boundary
for all future resources (documents, chunks, conversations, AI namespaces).

Columns:
  id          → UUID string primary key (auto-generated in Python)
  name        → required display name
  description → optional longer description
  owner_id    → FK → users.id (cascade delete: workspace gone if user deleted)
  created_at  → set once at insert time
  updated_at  → updated automatically on every write
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    # ── Primary key ───────────────────────────────────────────────────────────
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    # ── Core fields ───────────────────────────────────────────────────────────
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)  # Text allows longer strings than String

    # ── Ownership ─────────────────────────────────────────────────────────────
    # ondelete="CASCADE" → DB removes workspaces if the owning user is deleted
    owner_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    # back_populates="workspaces" requires a matching relationship on User.
    # We use back_populates (not backref) for explicit bidirectional clarity.
    owner = relationship("User", back_populates="workspaces")

    def __repr__(self):
        return f"<Workspace id={self.id} name={self.name!r} owner_id={self.owner_id}>"
