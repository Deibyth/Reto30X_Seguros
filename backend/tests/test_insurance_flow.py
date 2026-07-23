"""Integration tests for the full insurance conversational flow.

Exercises the complete happy path end-to-end through direct service/MCP tool
calls with real DB sessions, plus error paths for quote, policy creation,
and empty profile handling.

Task 4.1: Integration test file for insurance flow.
"""

import pytest
from sqlalchemy import select

from app.models.application import Application
from app.models.insurance import Insurance
from app.models.policy import Policy
from app.models.session import Session
from app.tools import domain_tools


# ──────────────────────────────────────────────
# Full happy path integration test
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_insurance_flow_happy_path(monkeypatch, domain_db_maker):
    """Complete happy path: profile → recommend → quote → collect → create_policy."""
    monkeypatch.setattr(domain_tools, "async_session_maker", domain_db_maker)

    # ── 1. Seed test data ──────────────────────────────────────────────
    async with domain_db_maker() as session:
        # Create an Insurance product
        ins = Insurance(
            nombre="Seguro de Vida Test",
            insurance_category="personal",
            prima_base=45_000,
        )
        session.add(ins)
        await session.flush()
        insurance_id = ins.id

        # Get the pre-seeded session and customer
        db_session = await session.get(Session, "domain-test-session")
        assert db_session is not None
        db_session.estado_actual = "perfilando"
        await session.commit()

    # ── 2. recommend_insurance ─────────────────────────────────────────
    profile = {"familia_con_hijos": True, "preocupacion": "proteger", "edad": 35}
    rec_result = domain_tools.recommend_insurance(profile)
    assert "Seguro de Vida" in rec_result
    assert "alta" in rec_result or "high" in rec_result.lower() or "✅" in rec_result

    # ── 3. quote_insurance ─────────────────────────────────────────────
    quote_result = domain_tools.quote_insurance("vida", {"edad": 35}, "estandar")
    assert "Seguro de Vida" in quote_result
    assert "prima" in quote_result.lower()

    # ── 4. save_form_field (collect data) ──────────────────────────────
    # save_form_field validates against credit FormSchema field names
    result = await domain_tools.save_form_field(
        session_id="domain-test-session",
        campo="nombres",
        valor="Juan Pérez",
    )
    assert result == "ok"

    result = await domain_tools.save_form_field(
        session_id="domain-test-session",
        campo="email",
        valor="juan@example.com",
    )
    assert result == "ok"

    result = await domain_tools.save_form_field(
        session_id="domain-test-session",
        campo="telefono",
        valor="3001234567",
    )
    assert result == "ok"

    # ── 5. create_policy ───────────────────────────────────────────────
    policy_result = await domain_tools.create_policy(
        customer_id="test-customer-uuid",
        form_data={
            "acepta_terminos": True,
            "nombre": "Juan Pérez",
            "documento": "1234567890",
            "email": "juan@example.com",
        },
        insurance_id=insurance_id,
    )
    assert "POL-" in policy_result
    assert "Seguro de Vida Test" in policy_result
    assert "Activa" in policy_result or "activo" in policy_result.lower()

    # ── 6. Verify DB records ───────────────────────────────────────────
    async with domain_db_maker() as session:
        # Verify Application created
        apps = (await session.execute(
            select(Application).where(Application.tipo == "seguro")
        )).scalars().all()
        assert len(apps) == 1
        assert apps[0].tipo == "seguro"
        assert apps[0].form_data.get("acepta_terminos") is True

        # Verify Policy created
        policies = (await session.execute(
            select(Policy)
        )).scalars().all()
        assert len(policies) == 1
        assert policies[0].insurance_id == insurance_id
        assert policies[0].estado == "activo"
        assert policies[0].numero_poliza.startswith("POL-")

        # Verify Session state (unchanged by create_policy — ChatService handles transitions)
        updated_session = await session.get(Session, "domain-test-session")
        assert updated_session is not None
        assert updated_session.estado_actual == "perfilando"


# ──────────────────────────────────────────────
# Error path tests
# ──────────────────────────────────────────────


class TestQuoteErrorPaths:
    """Quote for unknown product and other quote error scenarios."""

    def test_quote_unknown_product_returns_error(self):
        """Quote for unknown product returns error message."""
        result = domain_tools.quote_insurance(
            "nonexistent", {"edad": 25}, "estandar"
        )
        assert "No encontramos" in result or "error" in result.lower()

    def test_quote_invalid_coverage_returns_error(self):
        """Quote with invalid coverage level returns error message."""
        result = domain_tools.quote_insurance(
            "vida", {"edad": 25}, "invalid_level"
        )
        assert "no es un nivel de cobertura válido" in result or "inválido" in result.lower()


class TestCreatePolicyErrorPaths:
    """Policy creation error scenarios."""

    @pytest.mark.asyncio
    async def test_create_policy_terms_declined_returns_error(self, monkeypatch, domain_db_maker):
        """When terms are not accepted, policy is NOT created."""
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)

        # Seed an Insurance product
        async with domain_db_maker() as session:
            ins = Insurance(nombre="Test Seguro", prima_base=30_000)
            session.add(ins)
            await session.commit()
            insurance_id = ins.id

        result = await dt.create_policy(
            customer_id="test-customer-uuid",
            form_data={"acepta_terminos": False},
            insurance_id=insurance_id,
        )
        assert "términos" in result.lower() or "terms" in result.lower()
        assert "POL-" not in result

        # Verify NO Application was created
        async with domain_db_maker() as session:
            apps = (await session.execute(
                select(Application)
            )).scalars().all()
            assert len(apps) == 0

    @pytest.mark.asyncio
    async def test_create_policy_missing_acepta_terminos(self, monkeypatch, domain_db_maker):
        """When acepta_terminos is missing, policy is NOT created."""
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)

        async with domain_db_maker() as session:
            ins = Insurance(nombre="Test Seguro", prima_base=30_000)
            session.add(ins)
            await session.commit()
            insurance_id = ins.id

        result = await dt.create_policy(
            customer_id="test-customer-uuid",
            form_data={},
            insurance_id=insurance_id,
        )
        assert "términos" in result.lower() or "terms" in result.lower()

    @pytest.mark.asyncio
    async def test_create_policy_customer_not_found(self, monkeypatch, domain_db_maker):
        """When customer does not exist, appropriate error returned."""
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)

        async with domain_db_maker() as session:
            ins = Insurance(nombre="Test Seguro")
            session.add(ins)
            await session.commit()
            insurance_id = ins.id

        result = await dt.create_policy(
            customer_id="nonexistent-id",
            form_data={"acepta_terminos": True},
            insurance_id=insurance_id,
        )
        assert "no se encontró" in result.lower() or "Error" in result


class TestRecommendInsuranceErrorPaths:
    """Recommend insurance edge cases."""

    def test_empty_profile_returns_empty_message(self):
        """Empty profile should return 'no encontramos productos'."""
        result = domain_tools.recommend_insurance({})
        assert "No encontramos productos" in result

    def test_no_match_profile_returns_empty_message(self):
        """Profile with no matching rules should return no-products message."""
        result = domain_tools.recommend_insurance({"unknown_attr": "value"})
        assert "No encontramos productos" in result

    def test_newborn_young_single_returns_no_match(self):
        """Profile with edad=0 should not match R2 (18-35)."""
        result = domain_tools.recommend_insurance({"edad": 0, "estado_civil": "soltero"})
        assert "No encontramos productos" in result
