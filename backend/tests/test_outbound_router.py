"""Tests for outbound API endpoints."""

import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings
from app.main import create_app
from app.models import Base
from app.models.customer import Customer
from app.models.notification import Notification


# ---------------------------------------------------------------------------
# Fixture: TestClient with pre-seeded Notification data
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_test_client(tmp_path):
    """TestClient with one pending Notification in the database."""
    db_path = tmp_path / "test_router.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    async def _seed():
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with maker() as session:
            customer = Customer(
                id="router-happy-customer",
                documento_identidad="router-happy",
                nombre_completo="Happy Customer",
                telefono="+573001234567",
                salario=2_847_000,
                score_crediticio=0.8,
            )
            session.add(customer)
            await session.flush()

            notification = Notification(
                id="router-happy-notif",
                customer_id=customer.id,
                tipo="wpp",
                contenido="Test message for happy path",
                estado="pendiente",
                scheduled_at=datetime.utcnow() - timedelta(hours=1),
            )
            session.add(notification)
            await session.commit()

        await engine.dispose()

    asyncio.run(_seed())

    settings = Settings(
        database_url=db_url,
        environment="testing",
        llm_api_key="test-key",
        llm_model="test-model",
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOutboundPending:
    def test_get_pending_empty(self, test_client: TestClient):
        """No pending notifications returns empty list."""
        response = test_client.get("/outbound/pending")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []

    def test_get_pending_validates_limit(self, test_client: TestClient):
        """Out of range limit returns 400."""
        response = test_client.get("/outbound/pending?limit=0")
        assert response.status_code == 400
        response = test_client.get("/outbound/pending?limit=100")
        assert response.status_code == 400

    def test_get_pending_with_results(self, seeded_test_client: TestClient):
        """Happy path: returns seeded pending notification."""
        response = seeded_test_client.get("/outbound/pending")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["notification_id"] == "router-happy-notif"
        assert item["phone"] == "+573001234567"
        assert "Test message for happy path" in item["content"]
        assert item["customer_name"] == "Happy Customer"


class TestOutboundMutations:
    def test_mutation_404(self, test_client: TestClient):
        """Unknown notification ID returns 404."""
        response = test_client.post("/outbound/non-existent-id/sent")
        assert response.status_code == 404
        response = test_client.post("/outbound/non-existent-id/responded")
        assert response.status_code == 404
        response = test_client.post(
            "/outbound/non-existent-id/failed",
            json={"error": "test"},
        )
        assert response.status_code == 404

    def test_mark_sent_happy(self, seeded_test_client: TestClient):
        """Happy path: mark notification as sent."""
        response = seeded_test_client.post(
            "/outbound/router-happy-notif/sent"
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_mark_responded_happy(self, seeded_test_client: TestClient):
        """Happy path: mark notification as responded."""
        # First mark as sent
        seeded_test_client.post("/outbound/router-happy-notif/sent")
        response = seeded_test_client.post(
            "/outbound/router-happy-notif/responded"
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_mark_failed_happy(self, seeded_test_client: TestClient):
        """Happy path: mark notification as failed."""
        response = seeded_test_client.post(
            "/outbound/router-happy-notif/failed",
            json={"error": "test error"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
