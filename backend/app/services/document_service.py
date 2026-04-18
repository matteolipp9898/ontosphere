"""Document parsing and text processing service.

Handles extraction of plain text from uploaded documents (PDF, DOCX, TXT, MD)
and splitting into overlapping chunks suitable for LLM context windows.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------

def parse_document(file_path: str, content_type: str) -> str:
    """Extract plain text from a document file.

    Supports:
      - application/pdf            (via PyPDF2)
      - application/vnd.openxmlformats-officedocument.wordprocessingml.document (via python-docx)
      - text/plain, text/markdown  (read directly)

    Args:
        file_path: Absolute path to the file on disk.
        content_type: MIME type of the file.

    Returns:
        Extracted plain text.

    Raises:
        ValueError: If the content type is unsupported.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Normalise content type
    ct = content_type.lower().strip()

    if ct == "application/pdf":
        return _parse_pdf(path)

    if ct in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return _parse_docx(path)

    if ct in ("text/plain", "text/markdown", "text/x-markdown"):
        return path.read_text(encoding="utf-8")

    # Fallback: attempt to detect by extension
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(path)
    if ext in (".docx",):
        return _parse_docx(path)
    if ext in (".txt", ".md", ".markdown", ".text"):
        return path.read_text(encoding="utf-8")

    raise ValueError(
        f"Unsupported content type '{content_type}' for file '{path.name}'"
    )


def _parse_pdf(path: Path) -> str:
    """Extract text from a PDF using PyPDF2."""
    from PyPDF2 import PdfReader

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    full_text = "\n\n".join(pages)
    if not full_text.strip():
        logger.warning("PDF '%s' yielded no extractable text", path.name)
    return full_text


def _parse_docx(path: Path) -> str:
    """Extract text from a DOCX using python-docx."""
    from docx import Document as DocxDocument

    doc = DocxDocument(str(path))
    paragraphs: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    full_text = "\n\n".join(paragraphs)
    if not full_text.strip():
        logger.warning("DOCX '%s' yielded no extractable text", path.name)
    return full_text


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 4000,
    overlap: int = 200,
) -> list[str]:
    """Split text into overlapping chunks.

    Splits on paragraph boundaries (double newline) first, then sentence
    boundaries, falling back to character-level splitting only when a single
    segment exceeds *chunk_size*.

    Args:
        text: The full plain text to split.
        chunk_size: Maximum number of characters per chunk.
        overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        List of text chunks.  Empty list if the input text is empty.
    """
    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    # Split into paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for para in paragraphs:
        para_len = len(para)

        # If a single paragraph exceeds chunk_size, split it further
        if para_len > chunk_size:
            # Flush current buffer
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            # Split long paragraph by sentences
            _split_long_segment(para, chunk_size, overlap, chunks)
            continue

        # Check if adding this paragraph would exceed the limit
        # Account for the "\n\n" separator between paragraphs
        separator_len = 2 if current_chunk else 0
        if current_length + separator_len + para_len > chunk_size and current_chunk:
            chunk_text_str = "\n\n".join(current_chunk)
            chunks.append(chunk_text_str)

            # Build overlap from the tail of the finished chunk
            overlap_text = chunk_text_str[-overlap:] if overlap > 0 else ""
            if overlap_text:
                current_chunk = [overlap_text]
                current_length = len(overlap_text)
            else:
                current_chunk = []
                current_length = 0

        current_chunk.append(para)
        current_length += (separator_len + para_len) if separator_len else para_len

    # Flush remaining
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def _split_long_segment(
    text: str,
    chunk_size: int,
    overlap: int,
    out: list[str],
) -> None:
    """Split a segment that exceeds chunk_size into smaller pieces."""
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            out.append(text[start:])
            break

        # Try to find a sentence boundary near the end
        boundary = text.rfind(". ", start, end)
        if boundary == -1 or boundary <= start:
            boundary = text.rfind(" ", start, end)
        if boundary == -1 or boundary <= start:
            boundary = end

        out.append(text[start : boundary + 1].rstrip())
        start = max(start + 1, boundary + 1 - overlap)


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

async def save_uploaded_file(
    file: UploadFile,
    upload_dir: str,
) -> tuple[str, int]:
    """Persist an uploaded file to disk.

    Creates the upload directory if it does not exist.  The file is saved with
    a UUID prefix to avoid name collisions.

    Args:
        file: FastAPI UploadFile object.
        upload_dir: Directory in which to store the file.

    Returns:
        Tuple of (absolute file path, file size in bytes).
    """
    upload_path = Path(upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    # Generate a unique filename
    original_name = file.filename or "upload"
    # Sanitise the original name
    safe_name = "".join(
        c if (c.isalnum() or c in "._-") else "_" for c in original_name
    )
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    dest = upload_path / unique_name

    size = 0
    async with aiofiles.open(dest, "wb") as f:
        while True:
            chunk = await file.read(1024 * 64)  # 64 KiB
            if not chunk:
                break
            await f.write(chunk)
            size += len(chunk)

    logger.info(
        "Saved uploaded file '%s' -> '%s' (%d bytes)",
        original_name,
        dest,
        size,
    )
    return str(dest), size
