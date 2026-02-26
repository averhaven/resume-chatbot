"""Tests for authentication utilities and endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from jwt.exceptions import InvalidTokenError

from app.core.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.config import get_settings
from app.core.dependencies import get_db_session
from app.main import app
from tests.conftest import TestDatabase

# --- Dependency override for auth endpoint tests ---


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


# --- Auth utility unit tests ---


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_returns_string(self):
        """hash_password returns a non-empty string."""
        hashed = hash_password("mysecretpassword")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_is_not_plaintext(self):
        """Hashed password is not the same as the plain text."""
        password = "mysecretpassword"
        hashed = hash_password(password)
        assert hashed != password

    def test_same_password_different_hashes(self):
        """Two hashes of the same password are different (salt randomness)."""
        password = "mysecretpassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_verify_correct_password(self):
        """verify_password returns True for the correct password."""
        password = "mysecretpassword"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """verify_password returns False for an incorrect password."""
        hashed = hash_password("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_empty_password_against_valid_hash(self):
        """verify_password returns False for an empty password."""
        hashed = hash_password("correctpassword")
        assert verify_password("", hashed) is False


class TestJWT:
    """Tests for JWT token creation and decoding."""

    def test_create_access_token_returns_string(self):
        """create_access_token returns a non-empty string."""
        token = create_access_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token_returns_payload(self):
        """decode_access_token returns the token payload with correct subject."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        token = create_access_token(user_id)
        payload = decode_access_token(token)
        assert payload["sub"] == user_id

    def test_tampered_token_raises_error(self):
        """decode_access_token raises InvalidTokenError for tampered tokens."""
        token = create_access_token("user-123")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(InvalidTokenError):
            decode_access_token(tampered)

    def test_invalid_token_raises_error(self):
        """decode_access_token raises InvalidTokenError for garbage input."""
        with pytest.raises(InvalidTokenError):
            decode_access_token("not.a.valid.token")

    def test_token_signed_with_different_key_rejected(self):
        """Token signed with a different key is rejected."""
        payload = {
            "sub": "user-123",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        }
        bad_token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(InvalidTokenError):
            decode_access_token(bad_token)


# --- Auth endpoint integration tests ---


class TestRegisterEndpoint:
    """Tests for POST /auth/register."""

    def test_register_success(self, client):
        """Successful registration returns 201 with token and user info."""
        response = client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "testuser"
        assert data["user"]["email"] == "test@example.com"
        assert "id" in data["user"]
        # Password should not be in response
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

    def test_register_normalizes_username_to_lowercase(self, client):
        """Username is normalized to lowercase."""
        response = client.post(
            "/auth/register",
            json={
                "username": "TestUser",
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 201
        assert response.json()["user"]["username"] == "testuser"

    def test_register_duplicate_email(self, client):
        """Registration with duplicate email returns 409."""
        client.post(
            "/auth/register",
            json={
                "username": "user1",
                "email": "same@example.com",
                "password": "securepassword123",
            },
        )
        response = client.post(
            "/auth/register",
            json={
                "username": "user2",
                "email": "same@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 409
        assert "Email" in response.json()["detail"]

    def test_register_duplicate_username(self, client):
        """Registration with duplicate username returns 409."""
        client.post(
            "/auth/register",
            json={
                "username": "sameuser",
                "email": "user1@example.com",
                "password": "securepassword123",
            },
        )
        response = client.post(
            "/auth/register",
            json={
                "username": "sameuser",
                "email": "user2@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 409
        assert "Username" in response.json()["detail"]

    def test_register_short_password(self, client):
        """Registration with password under 8 chars returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "short",
            },
        )

        assert response.status_code == 422

    def test_register_invalid_username_special_chars(self, client):
        """Registration with special chars in username returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "username": "user@name!",
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 422

    def test_register_username_too_short(self, client):
        """Registration with username under 3 chars returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "username": "ab",
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 422

    def test_register_invalid_email(self, client):
        """Registration with invalid email returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "notanemail",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 422


class TestLoginEndpoint:
    """Tests for POST /auth/login."""

    def test_login_success(self, client):
        """Successful login returns token and user info."""
        client.post(
            "/auth/register",
            json={
                "username": "loginuser",
                "email": "login@example.com",
                "password": "securepassword123",
            },
        )
        response = client.post(
            "/auth/login",
            data={"username": "loginuser", "password": "securepassword123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "login@example.com"
        assert data["user"]["username"] == "loginuser"

    def test_login_wrong_password(self, client):
        """Login with wrong password returns 401."""
        client.post(
            "/auth/register",
            json={
                "username": "loginuser",
                "email": "login@example.com",
                "password": "correctpassword",
            },
        )
        response = client.post(
            "/auth/login",
            data={"username": "loginuser", "password": "wrongpassword"},
        )

        assert response.status_code == 401

    def test_login_nonexistent_username(self, client):
        """Login with non-existent username returns 401."""
        response = client.post(
            "/auth/login",
            data={"username": "nobody", "password": "anypassword"},
        )

        assert response.status_code == 401

    def test_login_returns_valid_jwt(self, client):
        """Token returned by login can be decoded and has correct subject."""
        reg = client.post(
            "/auth/register",
            json={
                "username": "jwtuser",
                "email": "jwt@example.com",
                "password": "securepassword123",
            },
        )
        user_id = reg.json()["user"]["id"]

        login = client.post(
            "/auth/login",
            data={"username": "jwtuser", "password": "securepassword123"},
        )
        token = login.json()["access_token"]

        payload = decode_access_token(token)
        assert payload["sub"] == user_id


class TestMeEndpoint:
    """Tests for GET /auth/me."""

    def test_me_returns_current_user(self, client):
        """Authenticated request to /auth/me returns current user."""
        reg = client.post(
            "/auth/register",
            json={
                "username": "meuser",
                "email": "me@example.com",
                "password": "securepassword123",
            },
        )
        token = reg.json()["access_token"]

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "meuser"
        assert data["email"] == "me@example.com"
        assert "id" in data

    def test_me_without_token_returns_401(self, client):
        """Request to /auth/me without token returns 401 (no credentials)."""
        response = client.get("/auth/me")

        assert response.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        """Request to /auth/me with invalid token returns 401."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401

    def test_me_with_expired_token_returns_401(self, client):
        """Request to /auth/me with expired token returns 401."""
        settings = get_settings()
        expired_payload = {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        }
        expired_token = pyjwt.encode(
            expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
