"""
workspace.py — Pydantic schemas for Workspace request/response shapes

Separate from the SQLAlchemy ORM model (app/models/workspace.py).
These schemas control what data comes IN (requests) and goes OUT (responses).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    """
    Input schema for POST /workspaces.
    owner_id is NOT accepted from the client — it is always derived from the
    authenticated user's JWT to prevent ownership spoofing.
    """
    name: str
    description: Optional[str] = None


class WorkspaceResponse(BaseModel):
    """
    Output schema — returned for all workspace read operations.
    Includes timestamps so the client can sort / display recency.
    """
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # allows reading SQLAlchemy ORM objects
