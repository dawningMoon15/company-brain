"""
workspaces.py — Workspace CRUD routes

All routes are protected: the caller must supply a valid Bearer JWT.
Ownership is always enforced — users can only see and manage their own workspaces.

POST /workspaces              → create a workspace
GET  /workspaces              → list all workspaces owned by current user
GET  /workspaces/{workspace_id} → get a single workspace (owner-only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


# ── POST /workspaces ──────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a workspace owned by the authenticated user.

    The owner_id is pulled from the JWT — clients cannot supply it directly,
    which prevents ownership spoofing.
    """
    workspace = Workspace(
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


# ── GET /workspaces ───────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=list[WorkspaceResponse],
    summary="List all workspaces owned by the current user",
)
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return every workspace where owner_id matches the authenticated user.
    Results are ordered newest-first by created_at.
    """
    workspaces = (
        db.query(Workspace)
        .filter(Workspace.owner_id == current_user.id)
        .order_by(Workspace.created_at.desc())
        .all()
    )
    return workspaces


# ── GET /workspaces/{workspace_id} ────────────────────────────────────────────
@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get a single workspace by ID",
)
def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch one workspace by its ID.

    - Returns 404 if the workspace does not exist.
    - Returns 403 if it exists but belongs to a different user.
      (We return 404 first so that IDs of other users' workspaces are not leaked.)
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workspace.",
        )

    return workspace
