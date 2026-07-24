"""Tests for Notification model extensions for outbound outreach."""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.notification import Notification
from app.models.opportunity import Opportunity


class TestNotificationOutboundFields:
    """Verify the extended Notification fields exist and work."""

    @pytest.mark.asyncio
    async def test_notification_has_new_columns(self, db_session: AsyncSession):
        """Check all outbound-specific fields are present."""
        n = Notification(
            customer_id="00000000-0000-0000-0000-000000000001",
            tipo="wpp",
            contenido="Test message",
        )
        db_session.add(n)
        await db_session.commit()

        result = await db_session.execute(
            select(Notification).where(Notification.id == n.id)
        )
        saved = result.scalar_one()

        # Nullable scheduling fields
        assert saved.scheduled_at is None
        assert saved.sent_at is None
        assert saved.responded_at is None

        # Defaults
        assert saved.intento_actual == 0
        assert saved.max_intentos == 1

        # Nullable FK and error log
        assert saved.opportunity_id is None
        assert saved.error_log is None

    @pytest.mark.asyncio
    async def test_notification_scheduling_fields(self, db_session: AsyncSession):
        """Set and read back scheduling fields."""
        now = datetime.utcnow()
        n = Notification(
            customer_id="00000000-0000-0000-0000-000000000001",
            tipo="wpp",
            contenido="Scheduled test",
            estado="pendiente",
            scheduled_at=now,
        )
        db_session.add(n)
        await db_session.commit()

        result = await db_session.execute(
            select(Notification).where(Notification.id == n.id)
        )
        saved = result.scalar_one()
        assert saved.scheduled_at is not None
        assert abs((saved.scheduled_at - now).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_notification_sent_lifecycle(self, db_session: AsyncSession):
        """Simulate sent → responded lifecycle."""
        n = Notification(
            customer_id="00000000-0000-0000-0000-000000000001",
            tipo="wpp",
            contenido="Lifecycle test",
            estado="pendiente",
        )
        db_session.add(n)
        await db_session.commit()

        # Mark sent
        n.estado = "enviado"
        n.sent_at = datetime.utcnow()
        await db_session.commit()

        result = await db_session.execute(
            select(Notification).where(Notification.id == n.id)
        )
        sent = result.scalar_one()
        assert sent.estado == "enviado"
        assert sent.sent_at is not None

        # Mark responded
        sent.estado = "respondido"
        sent.responded_at = datetime.utcnow()
        await db_session.commit()

        result = await db_session.execute(
            select(Notification).where(Notification.id == n.id)
        )
        responded = result.scalar_one()
        assert responded.estado == "respondido"
        assert responded.responded_at is not None

    @pytest.mark.asyncio
    async def test_notification_error_and_retry(self, db_session: AsyncSession):
        """Simulate a failed delivery with retry."""
        n = Notification(
            customer_id="00000000-0000-0000-0000-000000000001",
            tipo="wpp",
            contenido="Retry test",
            estado="pendiente",
        )
        db_session.add(n)
        await db_session.commit()

        # Mark failed
        n.estado = "fallido"
        n.error_log = "Timeout: no response from WhatsApp API"
        n.intento_actual = 1
        await db_session.commit()

        result = await db_session.execute(
            select(Notification).where(Notification.id == n.id)
        )
        failed = result.scalar_one()
        assert failed.estado == "fallido"
        assert "Timeout" in failed.error_log
        assert failed.intento_actual == 1

    @pytest.mark.asyncio
    async def test_notification_opportunity_relationship(self, db_session: AsyncSession):
        """Notification can link to an Opportunity."""
        opp = Opportunity(
            customer_id="00000000-0000-0000-0000-000000000001",
            tipo="seguro",
            estado="pendiente",
            descripcion="Test opportunity",
            score=85.0,
        )
        db_session.add(opp)
        await db_session.flush()

        n = Notification(
            customer_id="00000000-0000-0000-0000-000000000001",
            tipo="wpp",
            contenido="Linked notification",
            estado="pendiente",
            opportunity_id=opp.id,
        )
        db_session.add(n)
        await db_session.commit()

        result = await db_session.execute(
            select(Notification).where(Notification.id == n.id)
        )
        saved = result.scalar_one()
        assert saved.opportunity_id == opp.id
        assert saved.opportunity is not None
        assert saved.opportunity.tipo == "seguro"
