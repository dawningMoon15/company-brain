"""
document.py — Pydantic schemas for Document request/response shapes

Keeps the API contract separate from the ORM model.
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
    It will point to a real Supabase Storage key once file uploads land.
    """
    filename:     str
    file_type:    str
    storage_path: str


class DocumentResponse(BaseModel):
    """
    Output schema — returned for all document read and write operations.

    Exposes pipeline state fields (page_count, parsed_at, status) so clients
    can track the document lifecycle without needing to re-query separately.

    Note: parsed_text is intentionally NOT included here — it can be very large
    and is only needed by the future chunking pipeline, not by list/detail views.
    """
    id:           str
    workspace_id: str
    uploaded_by:  Optional[str]       # nullable — user may have been deleted
    filename:     str
    file_type:    str
    storage_path: str
    status:       str
    page_count:   Optional[int]       # None until parsing completes
    parsed_at:    Optional[datetime]  # None until parsing completes
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}  # allows reading SQLAlchemy ORM objects
