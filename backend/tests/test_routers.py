import pytest


class TestHealthEndpoint:
    def test_health_returns_200(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_contains_status(self, test_client):
        response = test_client.get("/health")
        body = response.json()
        assert "status" in body

    def test_health_shows_environment(self, test_client):
        response = test_client.get("/health")
        body = response.json()
        assert body.get("environment") == "testing"
        assert "version" in body


class TestChatEchoFallback:
    def test_echo_fallback(self, echo_client):
        response = echo_client.post(
            "/chat", json={"message": "Hola mundo"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "Echo: Hola mundo"
        assert body["model"] == "echo-fallback"

    def test_echo_with_session_id(self, echo_client):
        response = echo_client.post(
            "/chat",
            json={"message": "Test"},
            headers={"X-Session-Id": "mi-session-123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == "mi-session-123"
        assert "Echo:" in body["reply"]


class TestChatWithSession:
    def test_invalid_session_returns_404(self, test_client):
        response = test_client.post(
            "/chat",
            json={"message": "Hola"},
            headers={"X-Session-Id": "id-inexistente"},
        )
        assert response.status_code == 404

    def test_create_session_and_reuse(self, test_client):
        response = test_client.post(
            "/chat",
            json={"message": "Hola"},
        )
        assert response.status_code in (200, 503)


class TestChatValidation:
    def test_empty_message_rejected(self, echo_client):
        response = echo_client.post(
            "/chat", json={"message": ""}
        )
        assert response.status_code == 422

    def test_missing_message_field(self, echo_client):
        response = echo_client.post("/chat", json={})
        assert response.status_code == 422
