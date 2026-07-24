"""Tests for OutboundService — proactive WhatsApp outreach."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import ChatResult
from app.models.application import Application
from app.models.credit import Credit
from app.models.customer import Customer
from app.models.notification import Notification
from app.models.opportunity import Opportunity
from app.models.policy import Policy
from app.services.outbound_service import OutboundService, Prospect

SMMLV = 1_423_500


# ---------------------------------------------------------------------------
# select_prospects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_select_prospects_returns_empty_when_no_eligible(db_engine):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)
    prospects = await service.select_prospects(limit=10)
    assert prospects == []


@pytest.mark.asyncio
async def test_select_prospects_filters_by_contract(db_engine, db_session):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    eligible = Customer(
        id="contract-eligible",
        documento_identidad="111",
        nombre_completo="Indefinido 12m",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    excluded = Customer(
        id="contract-excluded",
        documento_identidad="222",
        nombre_completo="Temporal 1m",
        salario=SMMLV * 2,
        tipo_contrato="Temporal",
        antiguedad_meses=1,
        score_crediticio=0.8,
    )
    db_session.add_all([eligible, excluded])
    await db_session.commit()

    prospects = await service.select_prospects(limit=10)

    assert len(prospects) == 1
    assert prospects[0].customer.id == "contract-eligible"


@pytest.mark.asyncio
async def test_select_prospects_filters_by_income(db_engine, db_session):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    above = Customer(
        id="income-above",
        documento_identidad="333",
        nombre_completo="Above SMMLV",
        salario=SMMLV,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    below = Customer(
        id="income-below",
        documento_identidad="444",
        nombre_completo="Below SMMLV",
        salario=SMMLV - 1,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    db_session.add_all([above, below])
    await db_session.commit()

    prospects = await service.select_prospects(limit=10)

    assert len(prospects) == 1
    assert prospects[0].customer.id == "income-above"


@pytest.mark.asyncio
async def test_select_prospects_excludes_existing_products(db_engine, db_session):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    customer = Customer(
        id="prod-customer",
        documento_identidad="555",
        nombre_completo="With Policy",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    db_session.add(customer)
    await db_session.flush()

    policy = Policy(
        id="existing-policy",
        customer_id=customer.id,
        insurance_id="dummy-insurance",
        prima=100_000,
        fecha_inicio=datetime.utcnow(),
    )
    db_session.add(policy)
    await db_session.commit()

    prospects = await service.select_prospects(limit=10)

    assert len(prospects) == 1
    assert prospects[0].customer.id == "prod-customer"
    assert prospects[0].recommended_product_type == "credito"


@pytest.mark.asyncio
async def test_select_prospects_excludes_customers_with_both_products(
    db_engine, db_session,
):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    customer = Customer(
        id="both-products",
        documento_identidad="666",
        nombre_completo="Has Both",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    db_session.add(customer)
    await db_session.flush()

    policy = Policy(
        id="policy-both",
        customer_id=customer.id,
        insurance_id="dummy-insurance",
        prima=100_000,
        fecha_inicio=datetime.utcnow(),
    )
    db_session.add(policy)

    application = Application(
        id="app-both",
        customer_id=customer.id,
        tipo="credito",
    )
    db_session.add(application)
    await db_session.flush()

    credit = Credit(
        id="credit-both",
        application_id=application.id,
        monto_solicitado=5_000_000,
        plazo_meses=12,
    )
    db_session.add(credit)
    await db_session.commit()

    prospects = await service.select_prospects(limit=10)

    assert len(prospects) == 0


@pytest.mark.asyncio
async def test_select_prospects_returns_top_n(db_engine, db_session):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    customers = []
    for i in range(5):
        c = Customer(
            id=f"topn-{i}",
            documento_identidad=f"topn-doc-{i}",
            nombre_completo=f"Customer {i}",
            salario=SMMLV * 2,
            tipo_contrato="Indefinido",
            antiguedad_meses=12,
            score_crediticio=0.8,
        )
        customers.append(c)
    db_session.add_all(customers)
    await db_session.commit()

    prospects = await service.select_prospects(limit=2)

    assert len(prospects) == 2


@pytest.mark.asyncio
async def test_select_prospects_ordered_by_opportunity_score(
    db_engine, db_session,
):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    low = Customer(
        id="score-low",
        documento_identidad="low",
        nombre_completo="Low Score",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    high = Customer(
        id="score-high",
        documento_identidad="high",
        nombre_completo="High Score",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    db_session.add_all([low, high])
    await db_session.flush()

    opp_low = Opportunity(
        id="opp-low", customer_id=low.id, tipo="seguro", score=0.3
    )
    opp_high = Opportunity(
        id="opp-high", customer_id=high.id, tipo="seguro", score=0.9
    )
    db_session.add_all([opp_low, opp_high])
    await db_session.commit()

    prospects = await service.select_prospects(limit=10)

    assert len(prospects) == 2
    assert prospects[0].customer.id == "score-high"
    assert prospects[1].customer.id == "score-low"


@pytest.mark.asyncio
async def test_select_prospects_excludes_recently_notified(
    db_engine, db_session,
):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    fresh = Customer(
        id="recent-notified",
        documento_identidad="fresh",
        nombre_completo="Recently Notified",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    db_session.add(fresh)
    await db_session.flush()

    recent = Notification(
        id="recent-n",
        customer_id=fresh.id,
        tipo="wpp",
        contenido="Old",
        estado="enviado",
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(recent)
    await db_session.commit()

    prospects = await service.select_prospects(limit=10)

    assert len(prospects) == 0


@pytest.mark.asyncio
async def test_select_prospects_filters_by_score(db_engine, db_session):
    """F-PROS-06: Customers with null score_crediticio are excluded."""
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    with_score = Customer(
        id="score-ok",
        documento_identidad="score-ok",
        nombre_completo="With Score",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    without_score = Customer(
        id="score-none",
        documento_identidad="score-none",
        nombre_completo="No Score",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=None,
    )
    db_session.add_all([with_score, without_score])
    await db_session.commit()

    prospects = await service.select_prospects(limit=10)

    assert len(prospects) == 1
    assert prospects[0].customer.id == "score-ok"


@pytest.mark.asyncio
async def test_select_prospects_filters_by_debt_margin(db_engine, db_session):
    """F-PROS-07: Customers whose estimated monthly payments exceed 50 % of
    salary are excluded."""
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    low_debt = Customer(
        id="debt-low",
        documento_identidad="debt-low",
        nombre_completo="Low Debt",
        salario=SMMLV * 2,  # ~2,847,000 COP
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    high_debt = Customer(
        id="debt-high",
        documento_identidad="debt-high",
        nombre_completo="High Debt",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    db_session.add_all([low_debt, high_debt])
    await db_session.flush()

    # High_debt has a credit whose monthly payment > 50 % of salary
    # salary = 2,847,000 → 50 % = 1,423,500
    # credit: 20,000,000 / 12 = 1,666,667 → exceeds threshold → excluded
    app_high = Application(
        id="app-high-debt", customer_id=high_debt.id, tipo="credito"
    )
    db_session.add(app_high)
    await db_session.flush()

    credit_high = Credit(
        id="credit-high-debt",
        application_id=app_high.id,
        monto_solicitado=20_000_000,
        plazo_meses=12,
    )
    db_session.add(credit_high)

    # Low_debt has a credit with low monthly payment below threshold
    app_low = Application(
        id="app-low-debt", customer_id=low_debt.id, tipo="credito"
    )
    db_session.add(app_low)
    await db_session.flush()

    credit_low = Credit(
        id="credit-low-debt",
        application_id=app_low.id,
        monto_solicitado=5_000_000,
        plazo_meses=24,
    )
    db_session.add(credit_low)
    await db_session.commit()

    prospects = await service.select_prospects(limit=10)

    assert len(prospects) == 1
    assert prospects[0].customer.id == "debt-low"


# ---------------------------------------------------------------------------
# generate_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_message_uses_fallback_when_no_ai(db_engine):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker, ai_client=None)

    customer = Customer(
        id="msg-noai",
        documento_identidad="msg-1",
        nombre_completo="María López",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
    )
    prospect = Prospect(customer=customer, recommended_product_type="seguro")

    message = await service.generate_message(prospect)

    assert "María López" in message
    assert "seguro" in message
    assert "STOP" in message or "no deseas recibir" in message


@pytest.mark.asyncio
async def test_generate_message_fallback_on_exception(
    db_engine, mock_ai_client,
):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    mock_ai_client.chat_raw = AsyncMock(
        side_effect=RuntimeError("API down")
    )
    service = OutboundService(session_maker=maker, ai_client=mock_ai_client)

    customer = Customer(
        id="msg-exc",
        documento_identidad="msg-2",
        nombre_completo="Carlos Ruiz",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
    )
    prospect = Prospect(customer=customer, recommended_product_type="credito")

    message = await service.generate_message(prospect)

    assert "Carlos Ruiz" in message
    assert "crédito" in message


@pytest.mark.asyncio
async def test_generate_message_with_ai(db_engine, mock_ai_client):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    mock_ai_client.chat_raw = AsyncMock(
        return_value=ChatResult(
            reply="¡Hola! Te ofrezco un seguro especialmente pensado para ti.",
            model="test-model",
        )
    )
    service = OutboundService(session_maker=maker, ai_client=mock_ai_client)

    customer = Customer(
        id="msg-ai",
        documento_identidad="msg-3",
        nombre_completo="Ana Gómez",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
    )
    prospect = Prospect(customer=customer, recommended_product_type="seguro")

    message = await service.generate_message(prospect)

    assert message == "¡Hola! Te ofrezco un seguro especialmente pensado para ti."

    # Verify the system prompt includes the opt-out hint (F-MSG-06)
    call_args = mock_ai_client.chat_raw.call_args
    system_prompt = call_args[1]["openai_messages"][0]["content"]
    assert "STOP" in system_prompt or "no deseas recibir" in system_prompt


@pytest.mark.asyncio
async def test_generate_message_fallback_on_empty_ai_reply(
    db_engine, mock_ai_client,
):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    mock_ai_client.chat_raw = AsyncMock(
        return_value=ChatResult(reply="", model="test-model")
    )
    service = OutboundService(session_maker=maker, ai_client=mock_ai_client)

    customer = Customer(
        id="msg-empty",
        documento_identidad="msg-4",
        nombre_completo="Pedro Díaz",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
    )
    prospect = Prospect(customer=customer, recommended_product_type="credito")

    message = await service.generate_message(prospect)

    assert "Pedro Díaz" in message
    assert "crédito" in message


# ---------------------------------------------------------------------------
# create_notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_notification_persists_record(db_engine, db_session):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    customer = Customer(
        id="notif-customer",
        documento_identidad="notif-1",
        nombre_completo="Test User",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
        score_crediticio=0.8,
    )
    db_session.add(customer)
    await db_session.flush()

    opportunity = Opportunity(
        id="notif-opp",
        customer_id=customer.id,
        tipo="seguro",
        estado="pendiente",
        score=0.8,
    )
    db_session.add(opportunity)
    await db_session.commit()

    prospect = Prospect(
        customer=customer,
        recommended_product_type="seguro",
        opportunity=opportunity,
    )

    notification = await service.create_notification(prospect, "Hola, te ofrecemos un seguro.")

    assert notification.customer_id == customer.id
    assert notification.tipo == "wpp"
    assert notification.contenido == "Hola, te ofrecemos un seguro."
    assert notification.estado == "pendiente"
    assert notification.opportunity_id == opportunity.id
    assert notification.scheduled_at is not None

    # Verify it actually persisted
    async with maker() as session:
        saved = await session.get(Notification, notification.id)
        assert saved is not None
        assert saved.customer_id == customer.id


# ---------------------------------------------------------------------------
# process_reattempts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_reattempts_creates_new_records(db_engine, db_session):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    customer = Customer(
        id="reattempt-customer",
        documento_identidad="reattempt-1",
        nombre_completo="Reattempt User",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
    )
    db_session.add(customer)
    await db_session.flush()

    old_notification = Notification(
        id="old-sent",
        customer_id=customer.id,
        tipo="wpp",
        contenido="Test message",
        estado="enviado",
        sent_at=datetime.utcnow() - timedelta(days=6),
        responded_at=None,
        intento_actual=0,
        max_intentos=2,
    )
    db_session.add(old_notification)
    await db_session.commit()

    count = await service.process_reattempts()

    assert count == 1

    async with maker() as session:
        notifications = (
            (
                await session.execute(
                    select(Notification).where(
                        Notification.customer_id == customer.id
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(notifications) == 2
    retry = [n for n in notifications if n.id != "old-sent"][0]
    assert retry.estado == "reintento"
    assert retry.intento_actual == 1


@pytest.mark.asyncio
async def test_process_reattempts_skips_recent_sent(db_engine, db_session):
    maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    service = OutboundService(session_maker=maker)

    customer = Customer(
        id="recent-customer",
        documento_identidad="recent-1",
        nombre_completo="Recent",
        salario=SMMLV * 2,
        tipo_contrato="Indefinido",
        antiguedad_meses=12,
    )
    db_session.add(customer)
    await db_session.flush()

    recent_notification = Notification(
        id="recent-sent",
        customer_id=customer.id,
        tipo="wpp",
        contenido="Test",
        estado="enviado",
        sent_at=datetime.utcnow() - timedelta(days=1),
        responded_at=None,
        intento_actual=0,
        max_intentos=2,
    )
    db_session.add(recent_notification)
    await db_session.commit()

    count = await service.process_reattempts()
    assert count == 0