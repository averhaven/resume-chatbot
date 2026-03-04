"""Tests for text extraction service."""

import json
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docx import Document
from fastapi import UploadFile

from app.services.text_extractor import (
    _extract_docx,
    _extract_json,
    _extract_pdf,
    extract_text,
)


def _make_upload_file(
    filename: str, content: bytes, size: int | None = None
) -> UploadFile:
    """Create a mock UploadFile for testing."""
    mock = MagicMock(spec=UploadFile)
    mock.filename = filename
    mock.size = size if size is not None else len(content)
    mock.read = AsyncMock(return_value=content)
    return mock


def _make_docx_bytes(*paragraphs: str) -> bytes:
    """Create an in-memory DOCX file with the given paragraphs."""
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --- extract_text dispatcher tests ---


class TestExtractText:
    """Tests for the extract_text() dispatcher."""

    @pytest.mark.asyncio
    async def test_txt_returns_decoded_content(self):
        file = _make_upload_file("resume.txt", b"Hello, I am a resume.")
        assert await extract_text(file) == "Hello, I am a resume."

    @pytest.mark.asyncio
    async def test_md_returns_decoded_content(self):
        file = _make_upload_file("resume.md", b"# My Resume\n\nExperience here.")
        assert await extract_text(file) == "# My Resume\n\nExperience here."

    @pytest.mark.asyncio
    async def test_unsupported_extension_raises(self):
        file = _make_upload_file("resume.exe", b"binary")
        with pytest.raises(ValueError, match="Unsupported file type"):
            await extract_text(file)

    @pytest.mark.asyncio
    async def test_file_too_large_raises(self):
        file = _make_upload_file("resume.txt", b"content", size=999_999_999)
        with pytest.raises(ValueError, match="too large"):
            await extract_text(file)


# --- JSON extraction tests ---


class TestExtractJson:
    """Tests for _extract_json."""

    def test_valid_json_returns_indented_dump(self):
        data = {"name": "Jane Doe", "title": "Developer"}
        result = _extract_json(json.dumps(data).encode())

        assert '"name": "Jane Doe"' in result
        assert '"title": "Developer"' in result

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            _extract_json(b"not json at all")


# --- PDF extraction tests ---


class TestExtractPdf:
    """Tests for _extract_pdf."""

    def test_valid_pdf_returns_text(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Resume content from PDF"

        with patch("app.services.text_extractor.PdfReader") as mock_reader_cls:
            mock_reader_cls.return_value.pages = [mock_page]
            result = _extract_pdf(b"fake pdf bytes")

        assert result == "Resume content from PDF"

    def test_multiple_pages_joined(self):
        pages = [MagicMock(), MagicMock()]
        pages[0].extract_text.return_value = "Page one content"
        pages[1].extract_text.return_value = "Page two content"

        with patch("app.services.text_extractor.PdfReader") as mock_reader_cls:
            mock_reader_cls.return_value.pages = pages
            result = _extract_pdf(b"fake pdf bytes")

        assert "Page one content" in result
        assert "Page two content" in result

    def test_invalid_bytes_raises(self):
        with pytest.raises(ValueError, match="Failed to extract text from PDF"):
            _extract_pdf(b"not a pdf")

    def test_no_extractable_text_raises(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        with patch("app.services.text_extractor.PdfReader") as mock_reader_cls:
            mock_reader_cls.return_value.pages = [mock_page]
            with pytest.raises(ValueError, match="no extractable text"):
                _extract_pdf(b"fake pdf bytes")


# --- DOCX extraction tests ---


class TestExtractDocx:
    """Tests for _extract_docx."""

    def test_valid_docx_returns_text(self):
        content = _make_docx_bytes("My resume content")
        result = _extract_docx(content)
        assert "My resume content" in result

    def test_multiple_paragraphs_joined(self):
        content = _make_docx_bytes("First paragraph", "Second paragraph")
        result = _extract_docx(content)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_invalid_bytes_raises(self):
        with pytest.raises(ValueError, match="Failed to extract text from DOCX"):
            _extract_docx(b"not a docx")

    def test_empty_docx_raises(self):
        content = _make_docx_bytes()  # no paragraphs
        with pytest.raises(ValueError, match="no extractable text"):
            _extract_docx(content)
