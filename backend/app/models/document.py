"""
document.py — SQLAlchemy ORM model for the `documents` table

Stores document metadata and extracted text — no file bytes live here.
Actual file bytes live in Supabase Storage, referenced by `storage_path`.

Columns:
  id           → UUID string primary key
  workspace_id → FK → workspaces.id  (document belongs to one workspace)
  uploaded_by  → FK → users.id       (who uploaded it)
  filename     → original file name shown to users
  file_type    → MIME type, e.g. "application/pdf"
  storage_path → canonical Supabase Storage key, e.g. "documents/ws/doc/file.pdf"
  status       → lifecycle state: uploaded → parsed → failed
  parsed_text  → raw extracted text from the PDF (set after parsing)
  page_count   → number of pages in the PDF (set after parsing)
  parsed_at    → timestamp of successful parse (set after parsing)
  created_at   → set once at insert
  updated_at   → refreshed on every write

Status values:
  "uploaded"  → file received, not yet processed
  "parsed"    → text extracted successfully, ready for chunking
  "failed"    → processing error during parsing
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
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
    # Default is "uploaded"; updated to "parsed" or "failed" after parsing.
    status = Column(String, nullable=False, default="uploaded")

    # ── Parsed content (populated by the parsing pipeline) ────────────────────
    # parsed_text  → full extracted text from PyMuPDF; NULL until parsed
    # page_count   → total pages in the PDF; NULL until parsed
    # parsed_at    → UTC timestamp of successful parse; NULL until parsed
    parsed_text = Column(Text,             nullable=True,  default=None)
    page_count  = Column(Integer,          nullable=True,  default=None)
    parsed_at   = Column(DateTime(timezone=True), nullable=True, default=None)

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
