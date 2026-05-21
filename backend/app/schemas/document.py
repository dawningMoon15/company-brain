"""
document.py — Pydantic schemas for Document request/response shapes

Keeps API contract separate from the ORM model.
workspace_id and uploaded_by are always derived server-side — never
accepted from the client — to prevent injection/spoofing.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentCreate(BaseModel):
    """
    Input schema for POST /workspaces/{workspace_id}/documents.

    workspace_id  → taken from the URL path parameter (not the body)
    uploaded_by   → taken from the authenticated user's JWT (not the body)
    status        → always starts as "uploaded" (set server-side)

    storage_path is a placeholder string for now (e.g. "uploads/demo.pdf").
    It will point to a real Supabase Storage / S3 key once file uploads land.
    """
    filename:     str
    file_type:    str
    storage_path: str


class DocumentResponse(BaseModel):
    """
    Output schema — returned for all document read operations.
    """
    id:           str
    workspace_id: str
    uploaded_by:  Optional[str]   # nullable — user may have been deleted
    filename:     str
    file_type:    str
    storage_path: str
    status:       str
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}  # allows reading SQLAlchemy ORM objects
