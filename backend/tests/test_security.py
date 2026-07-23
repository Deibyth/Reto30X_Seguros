"""Tests for SecurityMiddleware — security headers and rate limiting."""

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter
from fastapi.testclient import TestClient

from app.middleware.security import add_security_middleware


@pytest.fixture
def low_limit_app():
    """FastAPI app with rate limit set to 2/min for deterministic testing."""
    app = FastAPI()
    router = APIRouter()

    @router.get("/test")
    async def test_endpoint():
        return {"ok": True}

    @router.get("/health")
    async def health_endpoint():
        return {"status": "ok"}

    app.include_router(router)
    add_security_middleware(app, environment="testing", chat_rate_limit_per_minute=2)
    return app


@pytest.fixture
def rate_limit_client(low_limit_app):
    """TestClient against the low-limit app."""
    with TestClient(low_limit_app) as client:
        yield client


class TestSecurityHeaders:
    """Security headers must be present on every response."""

    def test_security_headers_present(self, test_client):
        """Response includes X-Content-Type-Options, X-Frame-Options,
        Content-Security-Policy, Referrer-Policy, and Permissions-Policy."""
        response = test_client.get("/health")

        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert "content-security-policy" in response.headers
        assert "referrer-policy" in response.headers
        assert "permissions-policy" in response.headers

    def test_server_header_removed(self, test_client):
        """Server header must not leak framework info."""
        response = test_client.get("/health")
        server = response.headers.get("server", "")
        assert "uvicorn" not in server.lower()

    def test_hsts_not_in_testing_environment(self, test_client):
        """Strict-Transport-Security should only be present in production."""
        response = test_client.get("/health")
        assert "strict-transport-security" not in response.headers


class TestRateLimiting:
    """Rate limiter must block requests after the configured threshold."""

    def test_rate_limit_after_threshold(self, rate_limit_client):
        """3rd request to a rate-limited endpoint returns 429 with Retry-After."""
        resp1 = rate_limit_client.get("/test")
        assert resp1.status_code == 200

        resp2 = rate_limit_client.get("/test")
        assert resp2.status_code == 200

        resp3 = rate_limit_client.get("/test")
        assert resp3.status_code == 429
        assert "retry-after" in resp3.headers

    def test_health_endpoint_whitelisted(self, rate_limit_client):
        """Health endpoint is never rate-limited regardless of request count."""
        for _ in range(10):
            response = rate_limit_client.get("/health")
            assert response.status_code == 200
