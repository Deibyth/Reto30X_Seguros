"""Tests for InterestRate model queries."""

import pytest
from datetime import date
from sqlalchemy import select
from app.models.interest_rate import InterestRate
from app.models.product import Product


class TestInterestRate:
    """Tests for InterestRate CRUD and queries."""

    @pytest.mark.asyncio
    async def test_create_interest_rate(self, db_session):
        """Should create an InterestRate record with all fields."""
        # Need a product for the FK
        product = Product(nombre="Test Credit", tipo="credito", activo=True)
        db_session.add(product)
        await db_session.flush()

        rate = InterestRate(
            categoria="A",
            product_id=product.id,
            modalidad_pago="libranza",
            tasa_min=12.0,
            tasa_max=15.0,
            vigencia_desde=date.today(),
            activo=True,
        )
        db_session.add(rate)
        await db_session.commit()

        assert rate.id is not None
        assert len(rate.id) == 36  # UUID length
        assert rate.categoria == "A"
        assert rate.product_id == product.id
        assert rate.modalidad_pago == "libranza"
        assert rate.tasa_min == 12.0
        assert rate.tasa_max == 15.0

    @pytest.mark.asyncio
    async def test_query_rate_by_triple_and_active(self, db_session):
        """Should query rates by (categoria, product_id, modalidad, activo)."""
        product = Product(nombre="Test Credit", tipo="credito", activo=True)
        db_session.add(product)
        await db_session.flush()

        rate = InterestRate(
            categoria="B",
            product_id=product.id,
            modalidad_pago="pago_directo",
            tasa_min=10.0,
            tasa_max=14.0,
            vigencia_desde=date.today(),
            activo=True,
        )
        db_session.add(rate)
        await db_session.commit()

        result = await db_session.execute(
            select(InterestRate).where(
                InterestRate.categoria == "B",
                InterestRate.product_id == product.id,
                InterestRate.modalidad_pago == "pago_directo",
                InterestRate.activo == True,
            )
        )
        found = result.scalar_one()
        assert found.id == rate.id
        assert found.tasa_min == 10.0
        assert found.tasa_max == 14.0

    @pytest.mark.asyncio
    async def test_query_nonexistent_returns_none(self, db_session):
        """Querying a nonexistent combination should return None."""
        product = Product(nombre="Test", tipo="credito", activo=True)
        db_session.add(product)
        await db_session.flush()

        # Create one rate
        rate = InterestRate(
            categoria="A",
            product_id=product.id,
            modalidad_pago="libranza",
            tasa_min=12.0,
            tasa_max=15.0,
            vigencia_desde=date.today(),
            activo=True,
        )
        db_session.add(rate)
        await db_session.commit()

        # Query with different modalidad — should not find
        result = await db_session.execute(
            select(InterestRate).where(
                InterestRate.categoria == "A",
                InterestRate.product_id == product.id,
                InterestRate.modalidad_pago == "pago_directo",
                InterestRate.activo == True,
            )
        )
        found = result.scalar_one_or_none()
        assert found is None

    @pytest.mark.asyncio
    async def test_unique_constraint(self, db_session):
        """Should enforce unique (categoria, product_id, modalidad_pago, vigencia_desde)."""
        product = Product(nombre="Test Credit", tipo="credito", activo=True)
        db_session.add(product)
        await db_session.flush()

        rate1 = InterestRate(
            categoria="A",
            product_id=product.id,
            modalidad_pago="libranza",
            tasa_min=12.0,
            tasa_max=15.0,
            vigencia_desde=date.today(),
            activo=True,
        )
        db_session.add(rate1)
        await db_session.commit()

        rate2 = InterestRate(
            categoria="A",
            product_id=product.id,
            modalidad_pago="libranza",
            tasa_min=14.0,
            tasa_max=16.0,
            vigencia_desde=date.today(),
            activo=True,
        )
        db_session.add(rate2)
        with pytest.raises(Exception):
            await db_session.commit()
        await db_session.rollback()
