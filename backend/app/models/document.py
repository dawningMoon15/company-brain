"""
document.py — SQLAlchemy ORM model for the `documents` table

Stores document metadata only — no file bytes live here.
Actual file bytes will later be stored in Supabase Storage (or S3),
referenced by `storage_path`.

Columns:
  id           → UUID string primary key
  workspace_id → FK → workspaces.id  (document belongs to one workspace)
  uploaded_by  → FK → users.id       (who uploaded it)
  filename     → original file name shown to users
  file_type    → MIME type or extension, e.g. "application/pdf" or "pdf"
  storage_path → opaque path in the storage backend, e.g. "uploads/abc.pdf"
  status       → lifecycle state: uploaded → parsing → parsed → failed
  created_at   → set once at insert
  updated_at   → refreshed on every write

Status values (intentionally kept as a plain string for now — migrate to
an Enum column when the pipeline stabilises):
  "uploaded"  → file received, not yet processed
  "parsing"   → actively being parsed
  "parsed"    → text extracted, ready for chunking
  "chunking"  → chunks being created
  "ready"     → chunks + embeddings done, searchable
  "failed"    → processing error
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    # ── Primary key ───────────────────────────────────────────────────────────
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    # ── Workspace scope ───────────────────────────────────────────────────────
    # Cascade: if a workspace is deleted, its documents are deleted too
    workspace_id = Column(
        String,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Uploader ──────────────────────────────────────────────────────────────
    # SET NULL: if the user is deleted we keep the document row (audit trail)
    # but clear the reference so there's no dangling FK
    uploaded_by = Column(
        String,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,   # nullable because of SET NULL on delete
        index=True,
    )

    # ── File metadata ─────────────────────────────────────────────────────────
    filename     = Column(String, nullable=False)               # display name
    file_type    = Column(String, nullable=False)               # e.g. "pdf"
    storage_path = Column(Text,   nullable=False)               # e.g. "uploads/abc.pdf"

    # ── Processing status ─────────────────────────────────────────────────────
    # Default is "uploaded"; the pipeline will update this as it progresses.
    status = Column(String, nullable=False, default="uploaded")

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
    workspace = relationship("Workspace", back_populates="documents")
    uploader  = relationship("User",      back_populates="uploaded_documents")

    def __repr__(self):
        return (
            f"<Document id={self.id} filename={self.filename!r} "
            f"status={self.status!r} workspace_id={self.workspace_id}>"
        )
