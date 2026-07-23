"""Integration tests for AnalyticsService — 6 endpoints + 503 unavailable."""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base
from app.models.application import Application
from app.models.conversation import Conversation
from app.models.credit import Credit
from app.models.customer import Customer
from app.models.session import Session
from app.services.analytics import AnalyticsService


@pytest_asyncio.fixture
async def analytics_data():
    """In-memory engine + session maker seeded with analytics demo data.

    Creates 3 customers, 3 sessions, 3 applications, 3 credits, and
    10 conversations — enough to exercise every analytics query.
    """
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with maker() as session:
        now = datetime.utcnow()

        # -- Customers --
        c_high = Customer(
            id="analytics-cust-high",
            documento_identidad="AN-001",
            nombre_completo="Cliente Alto",
            salario=10_000_000,
            tipo_contrato="Indefinido",
            antiguedad_meses=60,
            score_crediticio=850,
        )
        c_mid = Customer(
            id="analytics-cust-mid",
            documento_identidad="AN-002",
            nombre_completo="Cliente Medio",
            salario=2_500_000,
            tipo_contrato="Indefinido",
            antiguedad_meses=24,
            score_crediticio=700,
        )
        c_low = Customer(
            id="analytics-cust-low",
            documento_identidad="AN-003",
            nombre_completo="Cliente Bajo",
            salario=500_000,
            tipo_contrato="Temporal",
            antiguedad_meses=3,
        )
        session.add_all([c_high, c_mid, c_low])

        # -- Sessions --
        s_completed = Session(
            id="analytics-ses-completed",
            customer_id="analytics-cust-high",
            estado_actual="completado",
            campos_diligenciados={
                "nombre": "Rich",
                "email": "r@test.com",
                "telefono": "3001112233",
            },
            activa=False,
        )
        s_active = Session(
            id="analytics-ses-active",
            customer_id="analytics-cust-mid",
            estado_actual="recolectando_datos",
            campos_diligenciados={"nombre": "Mid"},
            activa=True,
        )
        s_abandoned = Session(
            id="analytics-ses-abandoned",
            customer_id="analytics-cust-low",
            estado_actual="inicio",
            campos_diligenciados={},
            activa=True,
        )
        session.add_all([s_completed, s_active, s_abandoned])

        # -- Applications --
        app_completed = Application(
            id="analytics-app-completed",
            customer_id="analytics-cust-high",
            tipo="credito",
            estado="completada",
            created_at=now - timedelta(days=1),
        )
        app_pending = Application(
            id="analytics-app-pending",
            customer_id="analytics-cust-mid",
            tipo="credito",
            estado="iniciada",
            created_at=now,
        )
        app_rejected = Application(
            id="analytics-app-rejected",
            customer_id="analytics-cust-low",
            tipo="credito",
            estado="rechazada",
            created_at=now,
        )
        session.add_all([app_completed, app_pending, app_rejected])

        # -- Credits --
        credit_high = Credit(
            id="analytics-cred-high",
            application_id="analytics-app-completed",
            monto_solicitado=20_000_000,
            plazo_meses=60,
            destino="Libre Inversión",
            tasa_interes=12.5,
        )
        credit_mid = Credit(
            id="analytics-cred-mid",
            application_id="analytics-app-pending",
            monto_solicitado=5_000_000,
            plazo_meses=12,
            destino="Vivienda",
            tasa_interes=10.0,
        )
        credit_low = Credit(
            id="analytics-cred-low",
            application_id="analytics-app-rejected",
            monto_solicitado=1_000_000,
            plazo_meses=6,
            destino="Educación",
            tasa_interes=8.0,
        )
        session.add_all([credit_high, credit_mid, credit_low])

        # -- Conversations: 5 on completed session, 5 on active session --
        convs = []
        for i in range(5):
            convs.append(
                Conversation(
                    id=f"analytics-conv-c-{i}",
                    session_id="analytics-ses-completed",
                    rol="user" if i % 2 == 0 else "assistant",
                    mensaje=f"Completed session message {i}",
                    metadata_json=(
                        {"error": "tool_not_found"} if i == 0 else None
                    ),
                )
            )
        for i in range(5):
            convs.append(
                Conversation(
                    id=f"analytics-conv-a-{i}",
                    session_id="analytics-ses-active",
                    rol="user" if i % 2 == 0 else "assistant",
                    mensaje=f"Active session message {i}",
                )
            )
        session.add_all(convs)
        await session.commit()

    yield maker

    await engine.dispose()


class TestAnalyticsService:
    """Integration tests for AnalyticsService methods directly."""

    @pytest.mark.asyncio
    async def test_pipeline_summary(self, analytics_data):
        """Pipeline summary returns expected counts with seeded data."""
        service = AnalyticsService(analytics_data)
        result = await service.get_pipeline_summary()

        assert result["total_sessions"] == 3
        assert result["active_sessions"] == 2  # active + abandoned
        assert result["completed_sessions"] == 1
        assert result["total_applications"] == 3
        assert result["conversion_rate"] == 100.0  # 3/3 * 100
        assert isinstance(result["abandon_at_section"], list)
        assert len(result["abandon_at_section"]) >= 1

    @pytest.mark.asyncio
    async def test_daily_trends(self, analytics_data):
        """Daily trends returns list of records with date/applications/completions."""
        service = AnalyticsService(analytics_data)
        result = await service.get_daily_trends(days=30)

        assert isinstance(result, list)
        assert len(result) >= 1
        assert "date" in result[0]
        assert "applications" in result[0]
        assert "completions" in result[0]

    @pytest.mark.asyncio
    async def test_customer_profile(self, analytics_data):
        """Customer profile returns salary/contract/tenure aggregations."""
        service = AnalyticsService(analytics_data)
        result = await service.get_customer_profile()

        assert "salary_distribution" in result
        assert isinstance(result["salary_distribution"], list)
        assert len(result["salary_distribution"]) >= 1

        assert "contract_types" in result
        assert isinstance(result["contract_types"], list)
        assert result["total_customers"] == 3
        assert result["avg_tenure_months"] > 0

    @pytest.mark.asyncio
    async def test_credit_stats(self, analytics_data):
        """Credit stats returns amount ranges, destinos, and averages."""
        service = AnalyticsService(analytics_data)
        result = await service.get_credit_stats()

        assert result["total_credits"] == 3
        assert result["avg_amount"] > 0
        assert result["avg_term_months"] > 0
        assert result["total_volume"] > 0
        assert isinstance(result["destino_distribution"], list)
        assert len(result["destino_distribution"]) >= 1
        assert isinstance(result["amount_ranges"], list)
        assert len(result["amount_ranges"]) >= 1

    @pytest.mark.asyncio
    async def test_ai_efficiency(self, analytics_data):
        """AI efficiency returns message averages and tool error counts."""
        service = AnalyticsService(analytics_data)
        result = await service.get_ai_efficiency()

        assert "avg_messages_per_completed_session" in result
        assert result["total_conversations"] == 10
        # Completed session (ses-completed) has 5 conversations
        assert result["avg_messages_per_completed_session"] == 5.0
        # ses-completed has one conversation with metadata_json.error
        assert result["sessions_with_tool_errors"] >= 1

    @pytest.mark.asyncio
    async def test_full_summary(self, analytics_data):
        """Full summary returns compound dict with all 5 sub-keys."""
        service = AnalyticsService(analytics_data)
        result = await service.get_full_summary()

        assert "pipeline" in result
        assert "trends" in result
        assert "customers" in result
        assert "credits" in result
        assert "efficiency" in result

        # Each sub-section should have content
        assert result["pipeline"]["total_sessions"] == 3
        assert result["credits"]["total_credits"] == 3

    def test_analytics_503_when_service_unavailable(self):
        """Endpoint returns 503 when analytics_service is not in app state."""
        app = FastAPI()
        from app.routers.analytics import router

        app.include_router(router)

        with TestClient(app) as client:
            response = client.get("/analytics/summary")
            assert response.status_code == 503
            assert "not available" in response.text.lower()
