"""
app/services/parser.py — PDF text extraction using PyMuPDF
===========================================================

Responsibility: receive raw PDF bytes, extract all readable text,
and return structured results for persistence.

This module sits between the storage layer (bytes in) and the database
layer (text out). It has no knowledge of HTTP, FastAPI, or SQLAlchemy.

Public surface:
  ParseResult     → dataclass holding extraction results
  extract_text()  → parse raw bytes; returns ParseResult

Future compatibility:
  parsed_text in ParseResult feeds directly into the chunking pipeline.
  Each page's text is separated by a form-feed character (\\f) which is
  the natural delimiter PyMuPDF uses — chunkers can split on it.
"""

import logging
from dataclasses import dataclass

import pymupdf  # PyMuPDF — import name is "pymupdf" not "fitz" in v1.24+

logger = logging.getLogger(__name__)


# ── Result container ──────────────────────────────────────────────────────────
@dataclass
class ParseResult:
    """
    Holds the output of a successful PDF text extraction.

    Attributes:
        extracted_text: Full text of the PDF. Pages are separated by the
                        form-feed character (\\f) as PyMuPDF produces naturally.
                        May be an empty string for image-only PDFs.
        page_count:     Total number of pages in the PDF.
    """
    extracted_text: str
    page_count:     int


# ── Main extraction function ──────────────────────────────────────────────────
def extract_text(pdf_bytes: bytes) -> ParseResult:
    """
    Extract all readable text from raw PDF bytes using PyMuPDF.

    Args:
        pdf_bytes: Raw bytes of a valid PDF file.

    Returns:
        ParseResult with extracted_text and page_count.

    Raises:
        ValueError: If the PDF has zero pages (empty document).
        RuntimeError: If PyMuPDF cannot open or parse the file.

    Text extraction strategy:
        - Opens the PDF from bytes (no temp file needed)
        - Extracts text from every page via get_text("text")
        - Joins pages with form-feed (\\f) — a standard page separator
        - Strips leading/trailing whitespace from the final result

    Empty PDFs:
        If the document has pages but all text is empty (e.g. scanned image PDF),
        extracted_text will be an empty string. The caller decides how to handle
        this — here we log a warning but do not raise.
    """
    logger.info("Starting PDF text extraction  size=%d bytes", len(pdf_bytes))

    # ── Open from bytes (no temp file) ────────────────────────────────────────
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        logger.error("PyMuPDF failed to open PDF bytes: %s", exc)
        raise RuntimeError(f"Could not open PDF for parsing: {exc}") from exc

    page_count = len(doc)
    logger.info("PDF opened successfully  page_count=%d", page_count)

    if page_count == 0:
        doc.close()
        raise ValueError("PDF contains zero pages — nothing to extract.")

    # ── Extract text page by page ─────────────────────────────────────────────
    page_texts: list[str] = []
    for page_num in range(page_count):
        try:
            page = doc.load_page(page_num)
            text = page.get_text("text")   # plain text, preserves line breaks
            page_texts.append(text)
        except Exception as exc:
            # Log the bad page but continue — partial extraction is better than none
            logger.warning(
                "Failed to extract text from page %d/%d: %s",
                page_num + 1, page_count, exc,
            )
            page_texts.append("")  # placeholder so page indices stay consistent

    doc.close()

    # ── Join pages and clean up ────────────────────────────────────────────────
    # Form-feed (\f) is the natural separator PyMuPDF uses for page boundaries.
    # Future chunkers can split on \f to get per-page chunks.
    extracted_text = "\f".join(page_texts).strip()

    if not extracted_text:
        logger.warning(
            "Extraction produced empty text for %d-page PDF "
            "(possibly a scanned/image-only document)",
            page_count,
        )
    else:
        logger.info(
            "Text extraction complete  pages=%d  characters=%d",
            page_count, len(extracted_text),
        )

    return ParseResult(
        extracted_text=extracted_text,
        page_count=page_count,
    )
