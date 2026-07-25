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
import os
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
from fastapi.staticfiles import StaticFiles

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

    if settings.app_profile == "multicanal":
        from pathlib import Path

        from app.migrations import database_path, migrate

        migrate(
            settings.app_profile,
            database_path(settings.database_url),
            Path(settings.multicanal_root),
            settings.multicanal_deployment_id,
        )

    # 1. Initialize async database engine
    init_engine(settings.database_url, echo=settings.debug)

    # 2. Create all tables
    from app.database import engine

    async with engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)

    if settings.app_profile == "multicanal":
        from app.security import initialize_security
        async with db.async_session_maker() as security_db:
            await initialize_security(security_db, settings)

    logger.info("Database tables created successfully")

    # 3. Initialize SegmentDataService (loads affiliate CSV dataset)
    from app.services.segment_data import SegmentDataService

    segment_service = SegmentDataService()
    segment_service.load()
    SegmentDataService._set_instance(segment_service)
    app.state.segment_data_service = segment_service
    if segment_service.is_loaded():
        logger.info(
            "SegmentDataService loaded with %d categories, %d segments",
            len(segment_service.get_categories()),
            len(segment_service.get_segments()),
        )
    else:
        logger.info("SegmentDataService: running without affiliate dataset")

    # 4. Import FastMCP server (registers domain tools)
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

    # 6. Initialize Voice Services (TTS/STT — optional, requires ELEVENLABS_API_KEY)
    tts_service = None
    stt_service = None
    if settings.elevenlabs_api_key:
        from app.services.tts import TTSService
        from app.services.stt import STTService

        static_audio_dir = os.path.join(os.path.dirname(__file__), "..", "static", "audio")
        budget_path = os.path.join(os.path.dirname(__file__), "..", "data", "tts_budget.json")

        tts_service = TTSService(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            static_dir=static_audio_dir,
            budget_path=budget_path,
        )
        stt_service = STTService(api_key=settings.elevenlabs_api_key)
        app.state.tts_service = tts_service
        app.state.stt_service = stt_service
        logger.info(
            "Voice services initialized (voice_id=%s)", settings.elevenlabs_voice_id
        )
    else:
        logger.info("Voice services not initialized — no ELEVENLABS_API_KEY")

    # 7. Initialize ChatService (orchestrates AI + tools + persistence)
    if ai_client is not None and db.async_session_maker is not None:
        from app.services.chat import ChatService

        chat_service = ChatService(
            session_maker=db.async_session_maker,
            ai_client=ai_client,
            tool_bridge=tool_bridge,
            tts_service=tts_service,
            stt_service=stt_service,
        )
        app.state.chat_service = chat_service
        logger.info("ChatService initialized")
    else:
        app.state.chat_service = None
        logger.warning("ChatService not initialized — chat will use echo fallback")

    # 7. Initialize OutboundService (proactive messaging)
    from app.services.outbound_service import OutboundService

    outbound_service = OutboundService(
        session_maker=db.async_session_maker,
        ai_client=ai_client,
        tts_service=tts_service,
    )
    app.state.outbound_service = outbound_service
    logger.info("OutboundService initialized")

    # 8. Initialize AnalyticsService (dashboard data aggregation)
    from app.services.analytics import AnalyticsService

    if db.async_session_maker is not None:
        analytics_service = AnalyticsService(db.async_session_maker)
        app.state.analytics_service = analytics_service
        logger.info("AnalyticsService initialized")
    else:
        app.state.analytics_service = None
        logger.warning("AnalyticsService not initialized — no database session maker")

    # 9. Start outbound scheduler (proactive messaging)
    if db.async_session_maker is not None:
        from app.scheduler import OutboundScheduler

        scheduler = OutboundScheduler(
            outbound_service=app.state.outbound_service,
        )
        scheduler.start()
        app.state.outbound_scheduler = scheduler
        logger.info("Outbound scheduler started")

        # Run first cycle immediately on startup (not in testing)
        if settings.environment != "testing":
            await scheduler.run_once()
    else:
        app.state.outbound_scheduler = None
        logger.warning("Outbound scheduler not started — no database session maker")

    yield
    # --- Shutdown ---
    scheduler = getattr(app.state, "outbound_scheduler", None)
    if scheduler is not None:
        await scheduler.stop()
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
    from app.routers.outbound import router as outbound_router
    from app.routers.auth import boundary_router, router as auth_router

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(analytics_router)
    app.include_router(outbound_router)
    app.include_router(auth_router)
    app.include_router(boundary_router)

    # Serve cached TTS audio files
    audio_static_dir = os.path.join(
        os.path.dirname(__file__), "..", "static", "audio"
    )
    os.makedirs(audio_static_dir, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=audio_static_dir), name="audio")

    return app


app = create_app()
