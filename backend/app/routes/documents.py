"""
documents.py — Document metadata CRUD routes

All routes are JWT-protected. Workspace ownership is verified before any
document operation — users can only touch documents inside workspaces they own.

Route map:
  POST   /workspaces/{workspace_id}/documents   → create document metadata
  GET    /workspaces/{workspace_id}/documents   → list documents in workspace
  GET    /documents/{document_id}               → get single document
  DELETE /documents/{document_id}               → delete document metadata
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.document import DocumentCreate, DocumentResponse

router = APIRouter(tags=["Documents"])


# ── Helper ────────────────────────────────────────────────────────────────────
def _get_owned_workspace(
    workspace_id: str,
    current_user: User,
    db: Session,
) -> Workspace:
    """
    Fetch a workspace by ID and assert the current user owns it.

    Raises:
      404 — workspace does not exist
      403 — workspace exists but belongs to a different user

    Using 404-before-403 so that workspace IDs of other users are not leaked.
    Extracted as a helper because multiple routes repeat this check.
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


# ── POST /workspaces/{workspace_id}/documents ─────────────────────────────────
@router.post(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document metadata entry in a workspace",
)
def create_document(
    workspace_id: str,
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register document metadata inside a workspace.

    - workspace_id comes from the URL (not the body)
    - uploaded_by is always the authenticated user (no spoofing)
    - status is always initialised to "uploaded"
    - storage_path is a placeholder string for now
    """
    _get_owned_workspace(workspace_id, current_user, db)  # ownership check

    document = Document(
        workspace_id=workspace_id,
        uploaded_by=current_user.id,
        filename=payload.filename,
        file_type=payload.file_type,
        storage_path=payload.storage_path,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


# ── GET /workspaces/{workspace_id}/documents ──────────────────────────────────
@router.get(
    "/workspaces/{workspace_id}/documents",
    response_model=list[DocumentResponse],
    summary="List all documents in a workspace",
)
def list_documents(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all document metadata entries for a workspace the user owns.
    Results are ordered newest-first.
    """
    _get_owned_workspace(workspace_id, current_user, db)  # ownership check

    documents = (
        db.query(Document)
        .filter(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return documents


# ── GET /documents/{document_id} ──────────────────────────────────────────────
@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Get a single document by ID",
)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch one document by its ID.

    - 404 if the document doesn't exist
    - 403 if the document's workspace belongs to a different user
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Verify the user owns the workspace this document lives in
    _get_owned_workspace(document.workspace_id, current_user, db)

    return document


# ── DELETE /documents/{document_id} ───────────────────────────────────────────
@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document metadata entry",
)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete the document metadata row.

    - 404 if the document doesn't exist
    - 403 if the document's workspace belongs to a different user
    - Returns 204 No Content on success (no body)

    Note: this only removes the metadata row. Deleting the actual file from
    storage will be wired up when the upload pipeline is implemented.
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    _get_owned_workspace(document.workspace_id, current_user, db)

    db.delete(document)
    db.commit()
    # 204 — FastAPI sends no body automatically when status_code=204
