"""
app/services/storage.py — Supabase Storage integration
=======================================================

Initialises the Supabase Python client using the service role key so that
uploads bypass Row Level Security (needed because the uploading user's JWT
is a custom app JWT, not a Supabase auth token).

Public surface:
  BUCKET            → name of the Supabase Storage bucket ("documents")
  upload_pdf()      → uploads raw bytes; returns the confirmed full_path from Supabase
  download_file()   → downloads raw bytes from a stored full_path

Key implementation notes (storage3 v2 SDK):
  - upload() returns UploadResponse(path, full_path, fullPath) — NO .error field.
    Failures raise storage3.utils.StorageException, so we catch that explicitly.
  - FileOptions key is "content-type" (lowercase hyphen), not "contentType".
  - full_path from upload is "bucket/path/to/file.pdf" (bucket-prefixed).
    download() takes only the bucket-relative part, so we strip the prefix.
"""

import logging
import os

from dotenv import load_dotenv
from storage3.utils import StorageException
from supabase import Client, create_client

# ── Logger ────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Load secrets from backend/.env ────────────────────────────────────────────
load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in backend/.env"
    )

logger.info("Supabase storage client initialising (URL: %s)", SUPABASE_URL)

# ── Supabase client (service role) ────────────────────────────────────────────
# One client instance, reused across all requests (no per-request cost).
# Service role key is required to bypass Supabase RLS on storage objects.
_supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ── Bucket name ───────────────────────────────────────────────────────────────
# Assumes the bucket already exists in your Supabase project.
BUCKET = "documents"


# ── Upload helper ─────────────────────────────────────────────────────────────
def upload_pdf(file_bytes: bytes, storage_path: str) -> str:
    """
    Upload raw PDF bytes to Supabase Storage.

    Args:
        file_bytes:   Raw bytes of the PDF file (already read and size-validated).
        storage_path: Intended destination path inside the bucket, e.g.
                      "workspace_id/document_id/filename.pdf"

    Returns:
        The confirmed full_path returned by Supabase (e.g. "documents/workspace/doc/file.pdf").
        Always use this return value as the storage_path saved to the DB — never
        the locally-constructed path — so that both sides always agree.

    Raises:
        RuntimeError: Wraps StorageException if Supabase rejects the upload.
    """
    logger.info(
        "Starting upload → bucket=%r  path=%r  size=%d bytes",
        BUCKET,
        storage_path,
        len(file_bytes),
    )

    try:
        response = (
            _supabase.storage
            .from_(BUCKET)
            .upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/pdf"},
            )
        )
    except StorageException as exc:
        # StorageException is what storage3 raises on API-level failures
        # (e.g. bucket not found, duplicate path, auth error).
        logger.error(
            "Supabase StorageException during upload  path=%r  error=%s",
            storage_path,
            exc,
        )
        raise RuntimeError(f"Supabase Storage upload failed: {exc}") from exc
    except Exception as exc:
        # Catch-all for unexpected network/SDK errors
        logger.error(
            "Unexpected error during Supabase upload  path=%r  error=%s",
            storage_path,
            exc,
        )
        raise RuntimeError(f"Unexpected storage error: {exc}") from exc

    # UploadResponse fields: .path (bucket-relative), .full_path / .fullPath
    # (the canonical "bucket/path" key Supabase stores the object under).
    logger.info(
        "Upload successful → response.path=%r  response.full_path=%r",
        response.path,
        response.full_path,
    )

    # Return full_path — this is the authoritative key Supabase has recorded.
    # Saving this (rather than our locally-built path) guarantees DB ↔ Storage
    # consistency even if the SDK normalises the path internally.
    return response.full_path


# ── Download helper ───────────────────────────────────────────────────────────
def download_file(storage_path: str) -> bytes:
    """
    Download raw bytes from Supabase Storage.

    Args:
        storage_path: The full_path as stored in the DB, e.g.
                      "documents/workspace_id/document_id/filename.pdf"
                      This is the bucket-prefixed path returned by upload_pdf().

    Returns:
        Raw bytes of the stored file.

    Raises:
        RuntimeError: If the download fails for any reason.

    Implementation note:
        The storage3 download() API takes a bucket-relative path (no bucket prefix).
        Our DB stores full_path = "bucket/path/to/file" from Supabase's upload response.
        We strip the leading "bucket/" segment before calling download().
    """
    # Strip the leading bucket name from the full_path.
    # full_path format: "documents/workspace_id/document_id/filename.pdf"
    # download() expects:          "workspace_id/document_id/filename.pdf"
    bucket_prefix = BUCKET + "/"
    if storage_path.startswith(bucket_prefix):
        relative_path = storage_path[len(bucket_prefix):]
    else:
        # Path may already be bucket-relative (e.g. from legacy rows)
        relative_path = storage_path

    logger.info(
        "Downloading from bucket=%r  relative_path=%r  (full_path=%r)",
        BUCKET, relative_path, storage_path,
    )

    try:
        file_bytes: bytes = (
            _supabase.storage
            .from_(BUCKET)
            .download(relative_path)
        )
    except StorageException as exc:
        logger.error(
            "Supabase StorageException during download  path=%r  error=%s",
            relative_path, exc,
        )
        raise RuntimeError(f"Supabase Storage download failed: {exc}") from exc
    except Exception as exc:
        logger.error(
            "Unexpected error during Supabase download  path=%r  error=%s",
            relative_path, exc,
        )
        raise RuntimeError(f"Unexpected storage download error: {exc}") from exc

    logger.info(
        "Download successful  path=%r  size=%d bytes",
        relative_path, len(file_bytes),
    )
    return file_bytes
