"""Text extraction from uploaded resume files."""

import json
from io import BytesIO
from pathlib import PurePosixPath

from docx import Document
from fastapi import UploadFile
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".txt", ".md", ".json", ".pdf", ".docx"}


async def extract_text(file: UploadFile) -> str:
    """Extract text content from an uploaded file.

    Args:
        file: FastAPI UploadFile instance

    Returns:
        Extracted text content

    Raises:
        ValueError: If file type is unsupported, file is too large, or extraction fails
    """
    # Validate extension
    filename = file.filename or ""
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Check size before reading (file.size is populated by Starlette on upload)
    settings = get_settings()
    if file.size is not None and file.size > settings.max_resume_file_size:
        raise ValueError(
            f"File too large ({file.size} bytes). "
            f"Maximum size is {settings.max_resume_file_size} bytes."
        )

    content = await file.read()

    if ext in {".txt", ".md"}:
        return content.decode("utf-8")

    if ext == ".json":
        return _extract_json(content)

    if ext == ".pdf":
        return _extract_pdf(content)

    if ext == ".docx":
        return _extract_docx(content)

    raise ValueError(f"Unsupported file type '{ext}'")


def _extract_json(content: bytes) -> str:
    """Extract text from a JSON file."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON file: {e}") from e

    return json.dumps(data, indent=2)


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF file."""
    try:
        reader = PdfReader(BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages).strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}") from e

    if not text:
        raise ValueError("PDF contains no extractable text")
    return text


def _extract_docx(content: bytes) -> str:
    """Extract text from DOCX file."""
    try:
        doc = Document(BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs).strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from DOCX: {e}") from e

    if not text:
        raise ValueError("DOCX contains no extractable text")
    return text
