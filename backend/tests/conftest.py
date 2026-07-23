from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.ai.client import AIClient, ChatResult
from app.config import Settings
from app.main import create_app
from app.models import Base
from app.models.customer import Customer
from app.models.session import Session


@pytest_asyncio.fixture
async def db_engine():
    """Async engine connected to in-memory SQLite with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Short-lived async session for unit tests."""
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with maker() as session:
        yield session


@pytest.fixture
def test_client():
    """TestClient with in-memory SQLite + fake API key (ChatService active)."""
    settings = Settings(
        database_url="sqlite+aiosqlite://",
        environment="testing",
        llm_api_key="test-key",
        llm_model="test-model",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def echo_client():
    """TestClient without API key — chat falls back to echo."""
    settings = Settings(
        database_url="sqlite+aiosqlite://",
        environment="testing",
        llm_api_key="",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_ai_client():
    client = MagicMock(spec=AIClient)
    client.model = "test-model"
    client.chat_with_tools = AsyncMock(
        return_value=ChatResult(
            reply="Respuesta de prueba",
            model="test-model",
        )
    )
    client.chat_raw = AsyncMock(
        return_value=ChatResult(
            reply="Respuesta de prueba",
            model="test-model",
        )
    )
    return client


@pytest_asyncio.fixture
async def sample_session(db_session):
    """A Session row inserted in the test DB."""
    session = Session(
        id="test-session-456",
        estado_actual="inicio",
        campos_diligenciados={},
        activa=True,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def domain_db_maker():
    """In-memory engine + session maker pre-populated with test data
    (Session, Customer rows) for domain_tools tests.
    """
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with maker() as session:
        session.add(
            Session(
                id="domain-test-session",
                estado_actual="inicio",
                campos_diligenciados={},
                activa=True,
            )
        )
        session.add(
            Customer(
                id="test-customer-uuid",
                documento_identidad="1234567890",
                nombre_completo="Juan Pérez",
                email="juan@example.com",
                salario=2_000_000.0,
                tipo_contrato="Indefinido",
                antiguedad_meses=24,
                score_crediticio=850.0,
            )
        )
        session.add(
            Customer(
                id="test-customer-low",
                documento_identidad="0987654321",
                nombre_completo="María García",
                salario=500_000.0,
                tipo_contrato="Temporal",
                antiguedad_meses=2,
            )
        )
        await session.commit()

    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def domain_db_session(domain_db_maker):
    """Short-lived session from domain_db_maker for direct assertions."""
    async with domain_db_maker() as session:
        yield session
