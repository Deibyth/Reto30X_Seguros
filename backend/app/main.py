"""FastAPI application factory — create_app() with lifespan management.

Architecture
------------
- create_app() is the single entry point for the FastAPI application.
- Lifespan context manager handles startup/shutdown lifecycle.
- Settings are loaded from env vars / .env with pydantic-settings.
- Database engine is initialized and tables are created on startup.
- FastMCP server is imported and logged (embedded mode).
- AIClient, ToolBridge, and ChatService are initialized and stored in app state.
"""

import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

# Ensure app logs propagate through uvicorn (it replaces root handlers)
_app_logger = logging.getLogger("app")
_app_logger.setLevel(logging.INFO)
if not _app_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    ))
    _app_logger.addHandler(_handler)
    _app_logger.propagate = False

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai import AIClient
from app.config import Settings
from app.database import dispose_engine, init_engine
import app.database as db
from app.middleware.security import add_security_middleware
from app.models import Base

logger = logging.getLogger(__name__)

_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup → yield → shutdown."""
    settings: Settings = app.state.settings  # type: ignore[union-attr]

    # --- Startup ---
    logger.info(
        "Starting %s v%s in %s mode",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    # 1. Initialize async database engine
    init_engine(settings.database_url, echo=settings.debug)

    # 2. Create all tables
    from app.database import engine

    async with engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")

    # 3. Import FastMCP server (registers domain tools)
    from app.tools.mcp_server import mcp  # noqa: F401

    logger.info("FastMCP server '%s' initialized", "Proteccion360")

    # 4. Initialize LLM AI client (provider-agnostic, OpenAI-compatible)
    ai_client: AIClient | None = None
    if settings.llm_api_key:
        ai_client = AIClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
        )
        app.state.ai_client = ai_client
        logger.info(
            "AI client initialized with model '%s' at '%s'",
            settings.llm_model,
            settings.llm_base_url or "default OpenAI endpoint",
        )
    else:
        app.state.ai_client = None
        logger.warning("No LLM_API_KEY configured — AI chat will fall back to echo")

    # 5. Initialize ToolBridge (reads FastMCP tool registry)
    from app.services.tool_bridge import ToolBridge

    tool_bridge = ToolBridge(mcp)
    app.state.tool_bridge = tool_bridge
    logger.info("ToolBridge initialized")

    # 6. Initialize ChatService (orchestrates AI + tools + persistence)
    if ai_client is not None and db.async_session_maker is not None:
        from app.services.chat import ChatService

        chat_service = ChatService(
            session_maker=db.async_session_maker,
            ai_client=ai_client,
            tool_bridge=tool_bridge,
        )
        app.state.chat_service = chat_service
        logger.info("ChatService initialized")
    else:
        app.state.chat_service = None
        logger.warning("ChatService not initialized — chat will use echo fallback")

    # 7. Initialize AnalyticsService (dashboard data aggregation)
    from app.services.analytics import AnalyticsService

    if db.async_session_maker is not None:
        analytics_service = AnalyticsService(db.async_session_maker)
        app.state.analytics_service = analytics_service
        logger.info("AnalyticsService initialized")
    else:
        app.state.analytics_service = None
        logger.warning("AnalyticsService not initialized — no database session maker")

    yield
    # --- Shutdown ---
    await dispose_engine()
    logger.info("Application shut down gracefully")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    settings : Settings | None
        Injected settings (for testing) or None to auto-load from environment.

    Returns
    -------
    FastAPI
        Configured application instance ready for uvicorn.
    """
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # Store settings and startup time in app state
    app.state.settings = settings
    app.state.start_time = _start_time

    # CORS middleware — allow frontend origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-Session-Id",
            "X-Requested-With",
        ],
    )

    # Security middleware — rate limiting, security headers
    add_security_middleware(app, environment=settings.environment)

    # Register routers
    from app.routers.analytics import router as analytics_router
    from app.routers.chat import router as chat_router
    from app.routers.health import router as health_router

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(analytics_router)

    return app


app = create_app()
