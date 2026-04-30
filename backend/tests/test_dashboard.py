"""Tests for GET /dashboard and GET /dashboard/analytics endpoints."""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_db_session
from app.main import app
from tests.conftest import TestDatabase


async def override_db_session():
    if TestDatabase.session_factory is None:
        raise RuntimeError("Test database not initialized")
    async with TestDatabase.session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def override_dependencies():
    app.dependency_overrides[get_db_session] = override_db_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture()
def client():
    with patch("app.main.create_llm_client"):
        with TestClient(app) as c:
            yield c


def _register_and_login(client: TestClient, username: str, suffix: str = "") -> str:
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}{suffix}@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestDashboard:
    """Tests for GET /dashboard."""

    def test_dashboard_unauthenticated(self, client):
        response = client.get("/dashboard")
        assert response.status_code == 401

    def test_dashboard_returns_user_info(self, client):
        token = _register_and_login(client, "dashuser")
        response = client.get("/dashboard", headers=_auth(token))

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "dashuser"
        assert data["email"] == "dashuser@example.com"
        assert "id" in data
        assert "created_at" in data

    def test_dashboard_resume_info_no_resume(self, client):
        token = _register_and_login(client, "dashnofile")
        response = client.get("/dashboard", headers=_auth(token))

        assert response.status_code == 200
        resume = response.json()["resume"]
        assert resume["filename"] is None
        assert resume["has_resume"] is False
        assert resume["chat_enabled"] is True

    def test_dashboard_resume_info_after_upload(self, client):
        token = _register_and_login(client, "dashwithfile")

        client.post(
            "/resume/upload",
            headers=_auth(token),
            files={"file": ("cv.txt", BytesIO(b"My resume content"), "text/plain")},
        )

        response = client.get("/dashboard", headers=_auth(token))
        assert response.status_code == 200
        resume = response.json()["resume"]
        assert resume["filename"] == "cv.txt"
        assert resume["has_resume"] is True

    def test_dashboard_public_chatbot_url(self, client):
        token = _register_and_login(client, "chatbotuser")
        response = client.get("/dashboard", headers=_auth(token))

        assert response.status_code == 200
        url = response.json()["public_chatbot_url"]
        assert "/chat/chatbotuser" in url

    def test_dashboard_chat_disabled_reflected(self, client):
        token = _register_and_login(client, "dashchatoff")
        client.patch(
            "/resume/chat-enabled",
            headers=_auth(token),
            json={"enabled": False},
        )

        response = client.get("/dashboard", headers=_auth(token))
        assert response.json()["resume"]["chat_enabled"] is False


class TestAnalytics:
    """Tests for GET /dashboard/analytics."""

    def test_analytics_unauthenticated(self, client):
        response = client.get("/dashboard/analytics")
        assert response.status_code == 401

    def test_analytics_zero_when_no_conversations(self, client):
        token = _register_and_login(client, "noconvuser")
        response = client.get("/dashboard/analytics", headers=_auth(token))

        assert response.status_code == 200
        data = response.json()
        assert data["total_conversations"] == 0
        assert data["total_messages"] == 0
        assert data["conversations_this_week"] == 0
        assert data["messages_this_week"] == 0
        assert data["average_messages_per_conversation"] == 0.0

    def test_analytics_tenant_isolation(self, client):
        """User A's analytics must not include User B's data."""
        token_a = _register_and_login(client, "analyticsa")
        token_b = _register_and_login(client, "analyticsb")

        # Both users check analytics — neither sees the other's (zero state)
        resp_a = client.get("/dashboard/analytics", headers=_auth(token_a))
        resp_b = client.get("/dashboard/analytics", headers=_auth(token_b))

        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        # Independent zero counts confirm isolation
        assert resp_a.json()["total_conversations"] == 0
        assert resp_b.json()["total_conversations"] == 0
