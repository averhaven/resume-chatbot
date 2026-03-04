"""Tests for resume API endpoints."""

import json
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_db_session
from app.main import app
from tests.conftest import TestDatabase

# --- Dependency override ---


async def override_db_session():
    """Use the test database session instead of the real one."""
    if TestDatabase.session_factory is None:
        raise RuntimeError("Test database not initialized")
    async with TestDatabase.session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def override_dependencies():
    """Override get_db_session with the test database for all tests in this module."""
    app.dependency_overrides[get_db_session] = override_db_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture()
def client():
    """Provide a TestClient with the LLM client patched out."""
    with patch("app.main.create_llm_client"):
        with TestClient(app) as c:
            yield c


def _register_and_get_token(client: TestClient, suffix: str = "") -> str:
    """Helper: register a user and return the access token."""
    response = client.post(
        "/auth/register",
        json={
            "username": f"resumeuser{suffix}",
            "email": f"resume{suffix}@example.com",
            "password": "securepassword123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Upload tests ---


class TestUploadResume:
    """Tests for POST /resume/upload."""

    def test_upload_txt_success(self, client):
        """Uploading a .txt file returns 201 with resume info."""
        token = _register_and_get_token(client)
        response = client.post(
            "/resume/upload",
            headers=_auth_header(token),
            files={
                "file": ("resume.txt", BytesIO(b"Hello, I am a resume."), "text/plain")
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "resume.txt"
        assert data["chat_enabled"] is True

    def test_upload_json_success(self, client):
        """Uploading a .json resume file extracts formatted text."""
        token = _register_and_get_token(client)
        resume_json = json.dumps(
            {
                "name": "Test User",
                "title": "Developer",
                "summary": "A great developer.",
            }
        )
        response = client.post(
            "/resume/upload",
            headers=_auth_header(token),
            files={
                "file": (
                    "resume.json",
                    BytesIO(resume_json.encode()),
                    "application/json",
                )
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "resume.json"

    def test_upload_md_success(self, client):
        """Uploading a .md file returns 201."""
        token = _register_and_get_token(client)
        response = client.post(
            "/resume/upload",
            headers=_auth_header(token),
            files={
                "file": (
                    "resume.md",
                    BytesIO(b"# My Resume\n\nExperience here."),
                    "text/markdown",
                )
            },
        )

        assert response.status_code == 201
        assert response.status_code == 201

    def test_upload_too_large(self, client):
        """Uploading a file over the size limit returns 413."""
        token = _register_and_get_token(client)
        # Create a file larger than 5 MB
        large_content = b"x" * (5 * 1024 * 1024 + 1)
        response = client.post(
            "/resume/upload",
            headers=_auth_header(token),
            files={"file": ("resume.txt", BytesIO(large_content), "text/plain")},
        )

        assert response.status_code == 413

    def test_upload_unsupported_format(self, client):
        """Uploading an unsupported file type returns 400."""
        token = _register_and_get_token(client)
        response = client.post(
            "/resume/upload",
            headers=_auth_header(token),
            files={
                "file": (
                    "resume.exe",
                    BytesIO(b"binary data"),
                    "application/octet-stream",
                )
            },
        )

        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]

    def test_upload_unauthenticated(self, client):
        """Uploading without auth returns 401."""
        response = client.post(
            "/resume/upload",
            files={"file": ("resume.txt", BytesIO(b"content"), "text/plain")},
        )

        assert response.status_code == 401


# --- Get resume tests ---


class TestGetResume:
    """Tests for GET /resume."""

    def test_get_resume_none_uploaded(self, client):
        """Getting resume info when none uploaded returns filename=None."""
        token = _register_and_get_token(client)
        response = client.get("/resume", headers=_auth_header(token))

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] is None
        assert data["chat_enabled"] is True

    def test_get_resume_after_upload(self, client):
        """Getting resume info after upload returns filename and has_content=True."""
        token = _register_and_get_token(client)

        # Upload first
        client.post(
            "/resume/upload",
            headers=_auth_header(token),
            files={"file": ("my_resume.txt", BytesIO(b"Resume content"), "text/plain")},
        )

        response = client.get("/resume", headers=_auth_header(token))

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "my_resume.txt"

    def test_get_resume_unauthenticated(self, client):
        """Getting resume info without auth returns 401."""
        response = client.get("/resume")
        assert response.status_code == 401


# --- Delete resume tests ---


class TestDeleteResume:
    """Tests for DELETE /resume."""

    def test_delete_resume(self, client):
        """Deleting resume returns 204, then get shows no resume."""
        token = _register_and_get_token(client)

        # Upload first
        client.post(
            "/resume/upload",
            headers=_auth_header(token),
            files={"file": ("resume.txt", BytesIO(b"Resume content"), "text/plain")},
        )

        # Delete
        response = client.delete("/resume", headers=_auth_header(token))
        assert response.status_code == 204

        # Verify deleted
        get_response = client.get("/resume", headers=_auth_header(token))
        data = get_response.json()
        assert data["filename"] is None

    def test_delete_resume_unauthenticated(self, client):
        """Deleting resume without auth returns 401."""
        response = client.delete("/resume")
        assert response.status_code == 401


# --- Chat toggle tests ---


class TestToggleChat:
    """Tests for PATCH /resume/chat-enabled."""

    def test_toggle_chat_disabled(self, client):
        """Disabling chat returns updated chat_enabled=False."""
        token = _register_and_get_token(client)
        response = client.patch(
            "/resume/chat-enabled",
            headers=_auth_header(token),
            json={"enabled": False},
        )

        assert response.status_code == 200
        assert response.json()["chat_enabled"] is False

    def test_toggle_chat_enabled(self, client):
        """Enabling chat after disabling returns chat_enabled=True."""
        token = _register_and_get_token(client)

        # Disable
        client.patch(
            "/resume/chat-enabled",
            headers=_auth_header(token),
            json={"enabled": False},
        )

        # Re-enable
        response = client.patch(
            "/resume/chat-enabled",
            headers=_auth_header(token),
            json={"enabled": True},
        )

        assert response.status_code == 200
        assert response.json()["chat_enabled"] is True

    def test_toggle_chat_unauthenticated(self, client):
        """Toggling chat without auth returns 401."""
        response = client.patch("/resume/chat-enabled", json={"enabled": False})
        assert response.status_code == 401
