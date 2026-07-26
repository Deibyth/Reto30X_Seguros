"""Security middleware: rate limiting, security headers, and basic protections.

Use Starlette Middleware (not FastAPI) for maximum compatibility.
Rate limiting uses an in-memory sliding window (per IP).
For production, replace with Redis-backed rate limiting.
"""

import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Rate Limiter (in-memory sliding window)
# ------------------------------------------------------------------

class RateLimiter:
    """Sliding-window rate limiter per IP.

    Limits each client IP to ``max_requests`` in any ``window_seconds``
    window. Tracks state in-memory — reset on server restart.
    """

    def __init__(
        self,
        max_requests: int = 20,
        window_seconds: int = 60,
        whitelist_paths: set[str] | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.whitelist_paths = whitelist_paths or {"/health"}
        self._clients: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP respecting proxy headers."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> bool:
        """Check if the request is within rate limits.

        Returns True if allowed, False if rate-limited.
        """
        # Whitelist exact paths + prefix matches (health checks, outbound, etc.)
        path = request.url.path
        if path in self.whitelist_paths:
            return True
        for whitelisted in self.whitelist_paths:
            if whitelisted.endswith("*") and path.startswith(whitelisted.rstrip("*")):
                return True

        client_ip = self._get_client_ip(request)
        now = time.time()
        window_start = now - self.window_seconds

        # Prune expired entries
        timestamps = self._clients[client_ip]
        self._clients[client_ip] = [t for t in timestamps if t > window_start]

        # Check limit
        if len(self._clients[client_ip]) >= self.max_requests:
            logger.warning("Rate limit exceeded for %s (path=%s)", client_ip, request.url.path)
            return False

        self._clients[client_ip].append(now)
        return True


# ------------------------------------------------------------------
# Security Headers Middleware
# ------------------------------------------------------------------

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",  # XSS Auditor deprecated, 0 = disable (modern browsers)
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
}

# Stricter CSP for production — only allow same-origin resources
CSP_DEV = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://localhost:* ws://localhost:*; font-src 'self' data:"
CSP_PROD = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self' data:"


class SecurityMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses.

    Also handles rate limiting for sensitive endpoints.
    """

    def __init__(
        self,
        app: Any,
        rate_limiter: RateLimiter | None = None,
        environment: str = "development",
    ) -> None:
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.csp = CSP_DEV if environment == "development" else CSP_PROD

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # --- Rate limiting ---
        if self.rate_limiter and not self.rate_limiter.check(request):
            return Response(
                content='{"detail": "Demasiadas solicitudes. Intentá de nuevo en un momento."}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": "60",
                    "X-Content-Type-Options": "nosniff",
                },
            )

        # --- Process request ---
        response = await call_next(request)

        # --- Security headers ---
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        # CSP
        response.headers["Content-Security-Policy"] = self.csp

        # HSTS (only in production)
        settings = getattr(request.app.state, "settings", None)
        if settings and getattr(settings, "environment", None) == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Remove server header (info leak)
        if "server" in response.headers:
            del response.headers["server"]

        return response


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def add_security_middleware(
    app: FastAPI,
    environment: str = "development",
    chat_rate_limit_per_minute: int = 15,
    whitelist_paths: set[str] | None = None,
) -> None:
    """Register security middleware on the FastAPI application.

    Called during ``create_app()`` with the detected environment.
    """
    whitelist = whitelist_paths or {"/health"}
    rate_limiter = RateLimiter(
        max_requests=chat_rate_limit_per_minute,
        window_seconds=60,
        whitelist_paths=whitelist,
    )

    app.add_middleware(
        SecurityMiddleware,
        rate_limiter=rate_limiter,
        environment=environment,
    )

    logger.info(
        "Security middleware: rate=%d/min, env=%s",
        chat_rate_limit_per_minute,
        environment,
    )
