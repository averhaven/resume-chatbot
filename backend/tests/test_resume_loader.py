"""Tests for resume loader service."""

import json
import tempfile
from pathlib import Path

import pytest

from app.services.resume_loader import (
    ResumeLoader,
    ResumeLoadError,
    create_resume_loader,
)


@pytest.fixture
def sample_resume_data():
    """Sample resume data for testing."""
    return {
        "name": "Test User",
        "title": "Software Engineer",
        "contact": {
            "email": "test@example.com",
            "location": "Test City",
        },
        "summary": "Test summary",
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "TestCorp",
                "location": "Test City",
                "start_date": "2020-01",
                "end_date": None,
                "current": True,
                "responsibilities": ["Led projects", "Mentored team"],
            }
        ],
        "skills": {
            "languages": ["Python", "JavaScript"],
            "frameworks": ["FastAPI"],
        },
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "Test University",
                "location": "Test City",
                "graduation_date": "2019-05",
            }
        ],
    }


@pytest.fixture
def temp_resume_file(sample_resume_data):
    """Create a temporary resume JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_resume_data, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def invalid_json_file():
    """Create a temporary file with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ invalid json content")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


def test_resume_loader_initialization():
    """Test ResumeLoader initialization."""
    loader = ResumeLoader("test_path.json")
    assert loader.resume_path == Path("test_path.json")
    assert loader._resume_data is None
    assert loader._resume_text is None


def test_load_resume_success(temp_resume_file, sample_resume_data):
    """Test successful resume loading."""
    loader = ResumeLoader(temp_resume_file)
    loader.load()

    assert loader._resume_data == sample_resume_data
    assert loader._resume_text is not None
    assert isinstance(loader._resume_text, str)
    assert len(loader._resume_text) > 0


def test_load_resume_file_not_found():
    """Test loading non-existent resume file."""
    loader = ResumeLoader("nonexistent_file.json")

    with pytest.raises(ResumeLoadError, match="Resume file not found"):
        loader.load()


def test_load_resume_invalid_json(invalid_json_file):
    """Test loading resume with invalid JSON."""
    loader = ResumeLoader(invalid_json_file)

    with pytest.raises(ResumeLoadError, match="Invalid JSON"):
        loader.load()


def test_get_resume_text(temp_resume_file):
    """Test getting formatted resume text."""
    loader = ResumeLoader(temp_resume_file)
    loader.load()

    text = loader.get_resume_text()

    # Verify key sections are present
    assert "Test User" in text
    assert "Software Engineer" in text
    assert "test@example.com" in text
    assert "Test summary" in text
    assert "Senior Engineer" in text
    assert "TestCorp" in text
    assert "Python" in text
    assert "BS Computer Science" in text


def test_get_resume_text_before_load(temp_resume_file):
    """Test getting resume text before loading returns None."""
    loader = ResumeLoader(temp_resume_file)

    text = loader.get_resume_text()
    assert text is None


def test_get_resume_data(temp_resume_file, sample_resume_data):
    """Test getting raw resume data."""
    loader = ResumeLoader(temp_resume_file)
    loader.load()

    data = loader.get_resume_data()
    assert data == sample_resume_data


def test_get_resume_data_before_load(temp_resume_file):
    """Test getting resume data before loading returns None."""
    loader = ResumeLoader(temp_resume_file)

    data = loader.get_resume_data()
    assert data is None


def test_format_resume_as_text_comprehensive(temp_resume_file):
    """Test comprehensive resume formatting."""
    loader = ResumeLoader(temp_resume_file)
    loader.load()

    text = loader.get_resume_text()

    # Check markdown formatting
    assert "# Test User" in text
    assert "## Software Engineer" in text
    assert "### Contact Information" in text
    assert "### Professional Summary" in text
    assert "### Work Experience" in text
    assert "### Skills" in text
    assert "### Education" in text

    # Check bullet points and formatting
    assert "- Email:" in text
    assert "- **Languages**:" in text
    assert "- Led projects" in text


def test_format_resume_handles_optional_fields():
    """Test formatting with missing optional fields."""
    minimal_data = {
        "name": "Minimal User",
        "title": "Developer",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(minimal_data, f)
        temp_path = Path(f.name)

    try:
        loader = ResumeLoader(temp_path)
        loader.load()
        text = loader.get_resume_text()

        # Should still have basic structure
        assert "Minimal User" in text
        assert "Developer" in text

    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_create_resume_loader(temp_resume_file):
    """Test factory function creates and loads resume."""
    loader = create_resume_loader(temp_resume_file)

    assert loader is not None
    assert loader._resume_data is not None
    assert loader._resume_text is not None


def test_create_resume_loader_invalid_file():
    """Test factory function with invalid file."""
    with pytest.raises(ResumeLoadError):
        create_resume_loader("nonexistent_file.json")


def test_resume_with_projects_and_certifications():
    """Test formatting resume with projects and certifications."""
    data = {
        "name": "Test User",
        "title": "Engineer",
        "projects": [
            {
                "name": "Test Project",
                "description": "A test project",
                "technologies": ["Python", "FastAPI"],
                "url": "github.com/test",
            }
        ],
        "certifications": [
            {
                "name": "Test Certification",
                "issuer": "Test Org",
                "date": "2023-01",
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        temp_path = Path(f.name)

    try:
        loader = ResumeLoader(temp_path)
        loader.load()
        text = loader.get_resume_text()

        # Verify projects section
        assert "### Notable Projects" in text
        assert "Test Project" in text
        assert "A test project" in text
        assert "Python, FastAPI" in text
        assert "github.com/test" in text

        # Verify certifications section
        assert "### Certifications" in text
        assert "Test Certification" in text
        assert "Test Org" in text

    finally:
        if temp_path.exists():
            temp_path.unlink()
