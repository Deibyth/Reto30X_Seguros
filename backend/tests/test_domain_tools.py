import pytest

from app.tools import domain_tools


@pytest.mark.asyncio
async def test_get_products_no_db(monkeypatch):
    monkeypatch.setattr(domain_tools, "async_session_maker", None)
    result = await domain_tools.get_products()
    assert "no está inicializada" in result


@pytest.mark.asyncio
async def test_get_customer_no_db(monkeypatch):
    monkeypatch.setattr(domain_tools, "async_session_maker", None)
    result = await domain_tools.get_customer(documento_identidad="123")
    assert "no está inicializada" in result


@pytest.mark.asyncio
async def test_save_form_field_invalid_campo(monkeypatch):
    """save_form_field no longer validates campo names (trusts AI prompt).
    When DB is unavailable, it returns 'no está inicializada' for any campo."""
    monkeypatch.setattr(domain_tools, "async_session_maker", None)
    result = await domain_tools.save_form_field(
        session_id="x", campo="campo_inexistente", valor="algo"
    )
    assert "no está inicializada" in result


@pytest.mark.asyncio
async def test_save_form_field_valid_campo(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.save_form_field(
        session_id="domain-test-session",
        campo="nombres",
        valor="Juan Carlos",
    )
    assert result == "ok"

    async with domain_db_maker() as session:
        from app.models.session import Session

        updated = await session.get(Session, "domain-test-session")
        assert updated.campos_diligenciados.get("nombres") == "Juan Carlos"


@pytest.mark.asyncio
async def test_save_form_field_none_value(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.save_form_field(
        session_id="domain-test-session",
        campo="segundo_apellido",
        valor=None,
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_create_application_no_db(monkeypatch):
    monkeypatch.setattr(domain_tools, "async_session_maker", None)
    result = await domain_tools.create_application(
        tipo="credito",
        customer_id="x",
        form_data={},
        monto_solicitado=1000000,
        plazo_meses=12,
        destino="Libre Inversión",
    )
    assert "no está inicializada" in result


@pytest.mark.asyncio
async def test_create_application_success(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.create_application(
        tipo="credito",
        customer_id="test-customer-uuid",
        form_data={"nombres": "Juan"},
        monto_solicitado=5_000_000,
        plazo_meses=24,
        destino="Libre Inversión",
    )
    assert "Error" not in result
    assert len(result) == 36


@pytest.mark.asyncio
async def test_check_eligibility_no_db(monkeypatch):
    monkeypatch.setattr(domain_tools, "async_session_maker", None)
    result = await domain_tools.check_eligibility(customer_id="x")
    assert "no está inicializada" in result


@pytest.mark.asyncio
async def test_check_eligibility_eligible(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.check_eligibility(customer_id="test-customer-uuid")
    assert "ES elegible" in result
    assert "$2,000,000" in result or "$2.000.000" in result


@pytest.mark.asyncio
async def test_check_eligibility_not_eligible(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.check_eligibility(
        customer_id="test-customer-low"
    )
    assert "requieren revisiones" in result
    assert "Salario menor" in result


@pytest.mark.asyncio
async def test_check_eligibility_not_found(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.check_eligibility(
        customer_id="nonexistent-id"
    )
    assert "No se encontró" in result


@pytest.mark.asyncio
async def test_simulate_credit_no_db():
    result = await domain_tools.simulate_credit(monto=10_000_000, plazo=12)
    assert "Simulación" in result
    assert "$10,000,000" in result or "$10.000.000" in result


@pytest.mark.asyncio
async def test_simulate_credit_invalid_amount():
    result = await domain_tools.simulate_credit(monto=0, plazo=12)
    assert "mayor a cero" in result


@pytest.mark.asyncio
async def test_simulate_credit_invalid_plazo():
    result = await domain_tools.simulate_credit(monto=1_000_000, plazo=200)
    assert "1 y 120 meses" in result


@pytest.mark.asyncio
async def test_get_insurance_no_db(monkeypatch):
    monkeypatch.setattr(domain_tools, "async_session_maker", None)
    result = await domain_tools.get_insurance(insurance_id="x")
    assert "no está inicializada" in result


@pytest.mark.asyncio
async def test_get_insurance_not_found(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.get_insurance(insurance_id="no-existe")
    assert "No se encontró" in result


@pytest.mark.asyncio
async def test_get_customer_not_found(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.get_customer(documento_identidad="0000000000")
    assert "No se encontró" in result


@pytest.mark.asyncio
async def test_get_customer_found(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.get_customer(documento_identidad="1234567890")
    assert "Juan Pérez" in result
    assert "juan@example.com" in result


@pytest.mark.asyncio
async def test_get_products_with_filter(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.get_products(tipo="credito")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_products_all(monkeypatch, domain_db_maker):
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)
    result = await domain_tools.get_products(tipo=None)
    assert isinstance(result, str)


# --- Tests for _calcular_categoria -----------------------------------------

class TestCalcularCategoria:
    """Tests for the _calcular_categoria helper function."""

    @pytest.mark.asyncio
    async def test_categoria_salary_none(self):
        """Null salary should return 'A'."""
        from app.tools.domain_tools import _calcular_categoria
        assert _calcular_categoria(None) == "A"

    @pytest.mark.asyncio
    async def test_categoria_salary_zero(self):
        """Zero salary should return 'A'."""
        from app.tools.domain_tools import _calcular_categoria
        assert _calcular_categoria(0) == "A"

    @pytest.mark.asyncio
    async def test_categoria_salary_up_to_2_smmlv(self):
        """Salary ≤ 2 SMMLV ($3,501,810) → 'A'."""
        from app.tools.domain_tools import _calcular_categoria
        assert _calcular_categoria(1_000_000) == "A"
        assert _calcular_categoria(3_501_810) == "A"  # boundary

    @pytest.mark.asyncio
    async def test_categoria_salary_up_to_4_smmlv(self):
        """Salary > 2 SMMLV and ≤ 4 SMMLV → 'B'."""
        from app.tools.domain_tools import _calcular_categoria
        assert _calcular_categoria(3_501_811) == "B"  # just above 2 SMMLV
        assert _calcular_categoria(7_003_620) == "B"  # boundary

    @pytest.mark.asyncio
    async def test_categoria_salary_above_4_smmlv(self):
        """Salary > 4 SMMLV → 'C'."""
        from app.tools.domain_tools import _calcular_categoria
        assert _calcular_categoria(7_003_621) == "C"  # just above 4 SMMLV
        assert _calcular_categoria(50_000_000) == "C"


# --- Tests for simulate_credit with category and product ---------------------

class TestSimulateCreditCategory:
    """Tests for simulate_credit with category and product."""

    @pytest.mark.asyncio
    async def test_simulate_credit_basic(self):
        """Basic simulation without DB should use fallback 18%."""
        from app.tools.domain_tools import simulate_credit
        result = await simulate_credit(monto=10_000_000, plazo=12)
        assert "Simulación" in result
        assert "18.0" in result  # fallback rate

    @pytest.mark.asyncio
    async def test_simulate_credit_invalid_amount(self):
        """Zero or negative monto should error."""
        from app.tools.domain_tools import simulate_credit
        result = await simulate_credit(monto=0, plazo=12)
        assert "mayor a cero" in result

    @pytest.mark.asyncio
    async def test_simulate_credit_invalid_plazo(self):
        """Plazo > 120 should error."""
        from app.tools.domain_tools import simulate_credit
        result = await simulate_credit(monto=1_000_000, plazo=200)
        assert "120 meses" in result

    @pytest.mark.asyncio
    async def test_simulate_credit_with_category_and_product(self, monkeypatch, domain_db_maker):
        """Simulate with real InterestRate should show category-specific rate."""
        from app.tools.domain_tools import simulate_credit
        from app.models.product import Product
        from app.models.interest_rate import InterestRate
        from datetime import date

        monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)

        # Seed a Product + InterestRate
        async with domain_db_maker() as session:
            product = Product(
                nombre="Crédito Test",
                tipo="credito",
                activo=True,
            )
            session.add(product)
            await session.flush()
            product_id = product.id

            rate = InterestRate(
                categoria="A",
                product_id=product_id,
                modalidad_pago="libranza",
                tasa_min=12.0,
                tasa_max=12.0,
                vigencia_desde=date.today(),
                activo=True,
            )
            session.add(rate)
            await session.commit()

        result = await simulate_credit(
            monto=10_000_000, plazo=12,
            categoria="A",
            modalidad="libranza",
            product_id=product_id,
        )
        assert "Simulación" in result
        assert "12.0" in result  # our test rate


# --- Tests for get_customer with categoria_afiliacion ------------------------

class TestGetCustomerCategory:
    """Tests for get_customer with categoria_afiliacion."""

    @pytest.mark.asyncio
    async def test_get_customer_returns_category(self, monkeypatch, domain_db_maker):
        """get_customer should include categoria_afiliacion from DB."""
        from app.tools.domain_tools import get_customer
        from app.models.customer import Customer

        monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)

        # Add a customer with explicit categoria_afiliacion="B"
        async with domain_db_maker() as session:
            session.add(Customer(
                id="test-customer-cat-b",
                documento_identidad="5555555555",
                nombre_completo="Cliente Categoria B",
                salario=10_000_000,  # would compute as "C" if no explicit cat
                categoria_afiliacion="B",
                tipo_contrato="Indefinido",
                antiguedad_meses=12,
            ))
            await session.commit()

        result = await get_customer(documento_identidad="5555555555")
        assert "Categoría" in result
        assert "B" in result


# --- Tests for create_application with modalidad_pago ------------------------

class TestCreateApplicationModalidad:
    """Tests for create_application with modalidad_pago."""

    @pytest.mark.asyncio
    async def test_create_application_with_modalidad(self, monkeypatch, domain_db_maker):
        """create_application should accept modalidad_pago in form_data."""
        from app.tools.domain_tools import create_application

        monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)

        app_id = await create_application(
            tipo="credito",
            customer_id="test-customer-uuid",
            form_data={"modalidad_pago": "libranza"},
            monto_solicitado=5_000_000,
            plazo_meses=12,
            destino="Libre Inversión",
        )
        assert app_id and "Error" not in app_id

    @pytest.mark.asyncio
    async def test_create_application_without_modalidad(self, monkeypatch, domain_db_maker):
        """create_application should work without modalidad_pago."""
        from app.tools.domain_tools import create_application

        monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)

        app_id = await create_application(
            tipo="credito",
            customer_id="test-customer-uuid",
            form_data={},
            monto_solicitado=3_000_000,
            plazo_meses=6,
            destino="Educativo",
        )
        assert app_id and "Error" not in app_id
