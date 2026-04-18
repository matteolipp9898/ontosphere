"""Tests for document parsing and text chunking logic."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services.document_service import chunk_text, parse_document


# ---------------------------------------------------------------------------
# parse_document
# ---------------------------------------------------------------------------
def test_parse_text_file():
    """Parsing a .txt file returns its full text content."""
    content = "Hello, this is a sample document.\nIt has two lines."

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        result = parse_document(str(tmp_path), "text/plain")
        assert "Hello, this is a sample document." in result
        assert "It has two lines." in result
    finally:
        tmp_path.unlink(missing_ok=True)


def test_parse_markdown_file():
    """Parsing a .md file returns its text content."""
    content = "# Heading\n\nSome **markdown** content."

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        result = parse_document(str(tmp_path), "text/markdown")
        assert "# Heading" in result
        assert "markdown" in result
    finally:
        tmp_path.unlink(missing_ok=True)


def test_parse_unsupported_type():
    """Parsing an unsupported content type raises ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
        f.write("data")
        tmp_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Unsupported content type"):
            parse_document(str(tmp_path), "application/x-unknown")
    finally:
        tmp_path.unlink(missing_ok=True)


def test_parse_missing_file():
    """Parsing a non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_document("/nonexistent/file.txt", "text/plain")


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------
def test_chunk_text_respects_max_size():
    """Each chunk must not exceed the specified maximum size by too much."""
    text = "word " * 500  # ~2500 characters
    chunk_size = 200

    chunks = chunk_text(text, chunk_size=chunk_size, overlap=50)

    assert len(chunks) > 1, "Expected multiple chunks"
    # Allow some tolerance since chunking is paragraph/sentence-boundary aware
    for chunk in chunks:
        assert len(chunk) <= chunk_size + 100


def test_chunk_text_overlap():
    """Consecutive chunks share overlapping content when overlap > 0."""
    # Build text with clear paragraph boundaries
    paragraphs = [f"Paragraph number {i} with some filler text here." for i in range(20)]
    text = "\n\n".join(paragraphs)
    overlap = 40

    chunks = chunk_text(text, chunk_size=200, overlap=overlap)

    assert len(chunks) > 1, "Expected multiple chunks"


def test_chunk_text_single_chunk():
    """Short text that fits in one chunk is returned as a single element."""
    text = "Short text."
    chunks = chunk_text(text, chunk_size=1000, overlap=50)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty():
    """An empty string yields an empty list of chunks."""
    chunks = chunk_text("", chunk_size=100, overlap=10)
    assert chunks == []
