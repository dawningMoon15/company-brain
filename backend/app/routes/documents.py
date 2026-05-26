"""
documents.py — Document metadata CRUD + PDF upload + parsing routes

All routes are JWT-protected. Workspace ownership is verified before any
document operation — users can only touch documents inside workspaces they own.

Route map:
  POST   /workspaces/{workspace_id}/upload      → upload real PDF to Supabase Storage
  POST   /documents/{document_id}/parse         → parse uploaded PDF, extract text
  POST   /workspaces/{workspace_id}/documents   → create document metadata (JSON)
  GET    /workspaces/{workspace_id}/documents   → list documents in workspace
  GET    /documents/{document_id}               → get single document
  DELETE /documents/{document_id}               → delete document metadata
"""

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.document import DocumentCreate, DocumentResponse
from app.services.parser import extract_text
from app.services.storage import download_file, upload_pdf

router = APIRouter(tags=["Documents"])

# ── Module logger ─────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Upload constraints ────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024   # 20 MB
ALLOWED_CONTENT_TYPE = "application/pdf"


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


# ── POST /workspaces/{workspace_id}/upload ───────────────────────────────────
@router.post(
    "/workspaces/{workspace_id}/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF file to a workspace",
)
async def upload_document(
    workspace_id: str,
    file: UploadFile = File(..., description="PDF file to upload (max 20 MB)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a real PDF file to Supabase Storage and register its metadata.

    Full flow:
      1. Authenticate the caller via JWT                    (get_current_user)
      2. Verify the caller owns the target workspace        (_get_owned_workspace)
      3. Reject non-PDF content types                       → 415
      4. Reject files larger than 20 MB                    → 413
      5. Generate a document_id and build the storage path
      6. Upload bytes to Supabase Storage                  → 502 on failure
      7. Persist a Document metadata row (status=uploaded)
      8. Return the DocumentResponse

    Storage path format:
      {workspace_id}/{document_id}/{original_filename}
    """
    # ── Step 1 & 2: Auth + ownership ──────────────────────────────────────────
    _get_owned_workspace(workspace_id, current_user, db)

    # ── Step 3: MIME type validation ──────────────────────────────────────────
    if file.content_type != ALLOWED_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Only PDF files are accepted. "
                f"Received content type: '{file.content_type}'"
            ),
        )

    # ── Step 4: Read bytes + size validation ──────────────────────────────────
    file_bytes = await file.read()
    logger.info(
        "Upload request  workspace=%r  filename=%r  content_type=%r  size=%d bytes",
        workspace_id, file.filename, file.content_type, len(file_bytes),
    )
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the 20 MB limit ({len(file_bytes):,} bytes received).",
        )
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── Step 5: Generate IDs and build storage path ───────────────────────────
    document_id   = str(uuid.uuid4())
    # Sanitise the filename to prevent path-traversal characters
    safe_filename = file.filename.replace("/", "_").replace("..", "_")
    intended_path = f"{workspace_id}/{document_id}/{safe_filename}"
    logger.info("Intended storage path: %r", intended_path)

    # ── Step 6: Upload to Supabase Storage ────────────────────────────────────
    # IMPORTANT: upload_pdf() returns the canonical full_path that Supabase
    # recorded (e.g. "documents/workspace/doc/file.pdf"). We must use THAT
    # value in the DB row — not our locally-constructed intended_path —
    # so that storage_path in the DB always matches the real object location.
    try:
        confirmed_storage_path = upload_pdf(file_bytes, intended_path)
    except RuntimeError as exc:
        logger.error("Storage upload failed, NOT creating metadata row. Error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage upload failed: {exc}",
        )

    logger.info("Confirmed storage path from Supabase: %r", confirmed_storage_path)

    # ── Step 7: Persist metadata row (only after confirmed upload) ────────────
    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        uploaded_by=current_user.id,
        filename=safe_filename,
        file_type="application/pdf",
        storage_path=confirmed_storage_path,   # ← Supabase's canonical key
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    logger.info(
        "Document metadata created  id=%r  storage_path=%r",
        document.id, document.storage_path,
    )

    # ── Step 8: Return response ───────────────────────────────────────────────
    return document


# ── POST /documents/{document_id}/parse ────────────────────────────────────────
@router.post(
    "/documents/{document_id}/parse",
    response_model=DocumentResponse,
    summary="Parse an uploaded PDF and extract its text",
)
def parse_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download a previously uploaded PDF from Supabase Storage, extract its
    text using PyMuPDF, and persist the results.

    Full flow:
      1. Fetch document row from DB                          → 404 if missing
      2. Verify workspace ownership                          → 403 if not owner
      3. Download PDF bytes from Supabase Storage            → 502 if fails
      4. Parse PDF with PyMuPDF                              → 422 if corrupt/empty
      5. Persist: parsed_text, page_count, parsed_at
      6. Update status to "parsed"
      7. Return updated DocumentResponse

    On any failure after fetching the document, status is set to "failed"
    so the document never gets stuck in an intermediate state.
    """
    from datetime import datetime, timezone

    # ── Step 1: Fetch document ──────────────────────────────────────────────────
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # ── Step 2: Verify workspace ownership ──────────────────────────────────────
    _get_owned_workspace(document.workspace_id, current_user, db)

    logger.info(
        "Parse requested  document_id=%r  filename=%r  storage_path=%r",
        document.id, document.filename, document.storage_path,
    )

    # ── Step 3: Download PDF bytes from Supabase Storage ──────────────────────
    try:
        pdf_bytes = download_file(document.storage_path)
    except RuntimeError as exc:
        # Mark as failed so the user knows something went wrong
        document.status = "failed"
        db.commit()
        logger.error("Download failed for document_id=%r: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not download PDF from storage: {exc}",
        )

    # ── Step 4: Extract text with PyMuPDF ───────────────────────────────────
    try:
        result = extract_text(pdf_bytes)
    except (ValueError, RuntimeError) as exc:
        # Mark as failed — PDF is corrupt or unreadable
        document.status = "failed"
        db.commit()
        logger.error("Parsing failed for document_id=%r: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"PDF parsing failed: {exc}",
        )

    # ── Step 5 & 6: Persist results and update status ──────────────────────────
    document.parsed_text = result.extracted_text
    document.page_count  = result.page_count
    document.parsed_at   = datetime.now(timezone.utc)
    document.status      = "parsed"
    db.commit()
    db.refresh(document)

    logger.info(
        "Parse complete  document_id=%r  pages=%d  chars=%d  status=%r",
        document.id, result.page_count, len(result.extracted_text), document.status,
    )

    # ── Step 7: Return updated document ─────────────────────────────────────────
    return document


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

    Note: this only removes the metadata row from the database.
    Deleting the corresponding file from Supabase Storage is a future
    enhancement (requires the storage_path to be passed to storage.delete()).
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
