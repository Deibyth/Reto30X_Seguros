"""Tests for the insurance recommendation engine and MCP tools.

Task 2.1: recommendation_engine.py — PRODUCTS catalog (7 products), RULES (7 rules),
match_products(), quote_product(), COVERAGE_MULTIPLIERS, AGE_MULTIPLIER.
Task 2.2: recommend_insurance() MCP tool — calls match_products(), formats result.
Task 2.3: quote_insurance() MCP tool — calls quote_product(), formats result.
"""

import pytest

from app.services.recommendation_engine import (
    PRODUCTS,
    RULES,
    COVERAGE_MULTIPLIERS,
    match_products,
    quote_product,
)


# ──────────────────────────────────────────────
# PRODUCTS catalog
# ──────────────────────────────────────────────


class TestProductsCatalog:
    """PRODUCTS dict has exactly 7 products with required keys."""

    def test_product_count(self):
        assert len(PRODUCTS) == 7

    def test_all_product_keys_exist(self):
        expected = {"vida", "accidentes", "viajes", "mascotas", "vida_deudor", "hogar", "movilidad"}
        assert set(PRODUCTS.keys()) == expected

    def test_each_product_has_required_keys(self):
        required = {"nombre", "descripcion", "prima_base", "categoria"}
        for pid, product in PRODUCTS.items():
            missing = required - product.keys()
            assert not missing, f"Product '{pid}' missing keys: {missing}"


# ──────────────────────────────────────────────
# RULES list
# ──────────────────────────────────────────────


class TestRules:
    """All 7 rules are registered in RULES."""

    def test_rule_count(self):
        assert len(RULES) == 7

    def test_all_product_ids_have_rules(self):
        rule_ids = {r[0] for r in RULES}
        assert rule_ids == set(PRODUCTS.keys())


# ──────────────────────────────────────────────
# match_products — 7 rule matching tests
# ──────────────────────────────────────────────


class TestMatchProducts:
    """All 7 rules match correctly given appropriate profiles."""

    # R1: familia_con_hijos + preocupacion=proteger -> Vida
    def test_r1_vida_family_with_children(self):
        profile = {"familia_con_hijos": True, "preocupacion": "proteger"}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "vida" in ids, "R1 failed: Vida should match for family+protect"

    def test_r1_vida_not_matched_without_both_conditions(self):
        profile = {"familia_con_hijos": True}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "vida" not in ids, "R1 failed: Vida without preocupacion should NOT match"

    # R2: edad 18-35 + soltero -> Accidentes Personales
    def test_r2_accidentes_young_single(self):
        profile = {"edad": 25, "estado_civil": "soltero"}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "accidentes" in ids, "R2 failed: Accidentes should match for young single"

    def test_r2_accidentes_not_matched_married(self):
        profile = {"edad": 25, "estado_civil": "casado"}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "accidentes" not in ids, "R2 failed: Married should NOT match accidentes"

    def test_r2_accidentes_not_matched_older(self):
        profile = {"edad": 40, "estado_civil": "soltero"}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "accidentes" not in ids, "R2 failed: Age 40 should NOT match accidentes"

    # R3: viaja_frecuentemente -> Viajes
    def test_r3_viajes_frequent_traveler(self):
        profile = {"viaja_frecuentemente": True}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "viajes" in ids, "R3 failed: Viajes should match for frequent traveler"

    def test_r3_viajes_not_matched_when_false(self):
        profile = {"viaja_frecuentemente": False}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "viajes" not in ids, "R3 failed: viaja_frecuentemente=False should NOT match"

    # R4: tiene_mascota -> Mascotas
    def test_r4_mascotas_has_pet(self):
        profile = {"tiene_mascota": True}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "mascotas" in ids, "R4 failed: Mascotas should match for pet owner"

    def test_r4_mascotas_not_matched_no_pet(self):
        profile = {"tiene_mascota": False}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "mascotas" not in ids, "R4 failed: No pet should NOT match"

    # R5: tiene_deuda_activa -> Vida Deudor
    def test_r5_vida_deudor_has_debt(self):
        profile = {"tiene_deuda_activa": True}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "vida_deudor" in ids, "R5 failed: Vida Deudor should match for active debt"

    def test_r5_vida_deudor_not_matched_no_debt(self):
        profile = {"tiene_deuda_activa": False}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "vida_deudor" not in ids, "R5 failed: No debt should NOT match"

    # R6: es_propietario_vivienda -> Hogar
    def test_r6_hogar_homeowner(self):
        profile = {"es_propietario_vivienda": True}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "hogar" in ids, "R6 failed: Hogar should match for homeowner"

    def test_r6_hogar_not_matched_renter(self):
        profile = {"es_propietario_vivienda": False}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "hogar" not in ids, "R6 failed: Not homeowner should NOT match"

    # R7: tiene_vehiculo -> Movilidad
    def test_r7_movilidad_has_vehicle(self):
        profile = {"tiene_vehiculo": "auto"}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "movilidad" in ids, "R7 failed: Movilidad should match for vehicle owner"

    def test_r7_movilidad_not_matched(self):
        profile = {"tiene_vehiculo": None}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "movilidad" not in ids, "R7 failed: No vehicle should NOT match"


# ──────────────────────────────────────────────
# match_products — edge cases
# ──────────────────────────────────────────────


class TestMatchProductsEdgeCases:
    """Empty profile, multi-match, sorting, unknown keys."""

    def test_empty_profile_returns_empty_list(self):
        result = match_products({})
        assert result == []

    def test_multi_match_returns_all(self):
        profile = {
            "tiene_vehiculo": "auto",
            "tiene_mascota": True,
            "es_propietario_vivienda": True,
        }
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "movilidad" in ids
        assert "mascotas" in ids
        assert "hogar" in ids
        assert len(ids) == 3

    def test_unknown_keys_ignored(self):
        profile = {"unknown_key": "value"}
        result = match_products(profile)
        assert result == []

    def test_sorted_by_confidence_then_prima_base(self):
        profile = {
            "familia_con_hijos": True,
            "preocupacion": "proteger",
            "tiene_vehiculo": "auto",
            "edad": 25,
            "estado_civil": "soltero",
        }
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert ids[0] == "movilidad", f"Expected movilidad first (high, 55000), got {ids}"
        assert ids[1] == "vida", f"Expected vida second (high, 45000), got {ids}"
        assert ids[2] == "accidentes", f"Expected accidentes third (medium, 25000), got {ids}"

    def test_confidence_high_for_direct_match(self):
        profile = {"viaja_frecuentemente": True}
        result = match_products(profile)
        viajes = [p for p in result if p["product_id"] == "viajes"][0]
        assert viajes["confidence"] == "high"

    def test_confidence_medium_for_r2(self):
        profile = {"edad": 25, "estado_civil": "soltero"}
        result = match_products(profile)
        accidentes = [p for p in result if p["product_id"] == "accidentes"][0]
        assert accidentes["confidence"] == "medium"

    def test_match_reason_present(self):
        profile = {"viaja_frecuentemente": True}
        result = match_products(profile)
        for p in result:
            assert "match_reason" in p, f"Missing match_reason for {p['product_id']}"
            assert isinstance(p["match_reason"], str)
            assert len(p["match_reason"]) > 0

    def test_result_includes_all_expected_fields(self):
        profile = {"familia_con_hijos": True, "preocupacion": "proteger"}
        result = match_products(profile)
        for p in result:
            assert "product_id" in p
            assert "nombre" in p
            assert "descripcion" in p
            assert "categoria" in p
            assert "prima_base" in p
            assert "match_reason" in p
            assert "confidence" in p

    def test_r2_with_edad_as_int_string(self):
        profile = {"edad": "25", "estado_civil": "soltero"}
        result = match_products(profile)
        ids = [p["product_id"] for p in result]
        assert "accidentes" in ids


# ──────────────────────────────────────────────
# COVERAGE_MULTIPLIERS
# ──────────────────────────────────────────────


class TestCoverageMultipliers:
    """COVERAGE_MULTIPLIERS has correct values."""

    def test_multipliers_exist(self):
        assert COVERAGE_MULTIPLIERS == {"basica": 0.8, "estandar": 1.0, "premium": 1.5}


# ──────────────────────────────────────────────
# quote_product — pricing tests
# ──────────────────────────────────────────────


class TestQuoteProduct:
    """quote_product() computes correct formulas."""

    def test_quote_estandar_baseline(self):
        result = quote_product("vida", {"edad": 25}, "estandar")
        assert result["product_id"] == "vida"
        assert result["nombre"] == "Seguro de Vida"
        assert result["prima_mensual"] == 45000.0
        assert result["prima_anual"] == 45000.0 * 12

    def test_quote_basica_multiplier(self):
        result = quote_product("vida", {"edad": 25}, "basica")
        assert result["prima_mensual"] == 36000.0

    def test_quote_premium_multiplier(self):
        result = quote_product("vida", {"edad": 25}, "premium")
        assert result["prima_mensual"] == 67500.0

    def test_quote_age_31_45_multiplier(self):
        result = quote_product("vida", {"edad": 35}, "estandar")
        assert result["prima_mensual"] == 54000.0

    def test_quote_age_46_60_multiplier(self):
        result = quote_product("vida", {"edad": 50}, "estandar")
        assert result["prima_mensual"] == 67500.0

    def test_quote_age_61_plus_multiplier(self):
        result = quote_product("vida", {"edad": 65}, "estandar")
        assert result["prima_mensual"] == 90000.0

    def test_quote_movilidad_age_no_age_range(self):
        result = quote_product("movilidad", {"edad": 50}, "estandar")
        assert result["prima_mensual"] == 55000.0

    def test_quote_unknown_product(self):
        result = quote_product("nonexistent", {"edad": 25}, "estandar")
        assert "error" in result
        assert result["error"] == "unknown_product"

    def test_quote_invalid_coverage(self):
        result = quote_product("vida", {"edad": 25}, "super_premium")
        assert "error" in result
        assert result["error"] == "invalid_coverage"

    def test_quote_all_required_keys_present(self):
        result = quote_product("vida", {"edad": 25}, "estandar")
        expected_keys = {
            "product_id", "nombre", "prima_mensual", "prima_anual",
            "cobertura_resumen", "deducible", "vigencia",
        }
        assert expected_keys.issubset(result.keys())

    def test_quote_hogar(self):
        result = quote_product("hogar", {"edad": 30}, "estandar")
        assert result["prima_mensual"] == 35000.0

    def test_quote_accidentes_premium(self):
        result = quote_product("accidentes", {"edad": 25}, "premium")
        assert result["prima_mensual"] == 37500.0


# ──────────────────────────────────────────────
# recommend_insurance MCP tool — Task 2.2
# ──────────────────────────────────────────────


class TestRecommendInsuranceTool:
    """Tests for the recommend_insurance() MCP tool function."""

    def test_import_recommend_insurance(self):
        from app.tools.domain_tools import recommend_insurance
        assert callable(recommend_insurance)

    def test_recommend_insurance_single_match(self):
        from app.tools.domain_tools import recommend_insurance
        result = recommend_insurance({"viaja_frecuentemente": True})
        assert "Asistencia Médica Viajes" in result
        assert "viaja_frecuentemente" in result.lower() or "Viaja" in result

    def test_recommend_insurance_family_protect(self):
        from app.tools.domain_tools import recommend_insurance
        result = recommend_insurance({"familia_con_hijos": True, "preocupacion": "proteger"})
        assert "Seguro de Vida" in result
        assert "alta" in result.lower() or "high" in result.lower()

    def test_recommend_insurance_empty_profile(self):
        from app.tools.domain_tools import recommend_insurance
        result = recommend_insurance({})
        assert "No encontramos productos" in result

    def test_recommend_insurance_multiple_matches(self):
        from app.tools.domain_tools import recommend_insurance
        result = recommend_insurance({
            "tiene_vehiculo": "auto",
            "tiene_mascota": True,
            "es_propietario_vivienda": True,
        })
        assert "Movilidad" in result
        assert "Mascotas" in result
        assert "Hogar" in result

    def test_recommend_insurance_no_match(self):
        from app.tools.domain_tools import recommend_insurance
        result = recommend_insurance({"unknown_attr": True})
        assert "No encontramos productos" in result


# ──────────────────────────────────────────────
# quote_insurance MCP tool — Task 2.3
# ──────────────────────────────────────────────


class TestQuoteInsuranceTool:
    """Tests for the quote_insurance() MCP tool function."""

    def test_import_quote_insurance(self):
        from app.tools.domain_tools import quote_insurance
        assert callable(quote_insurance)

    def test_quote_insurance_basic(self):
        from app.tools.domain_tools import quote_insurance
        result = quote_insurance("vida", {"edad": 25}, "estandar")
        assert "Seguro de Vida" in result
        assert "$45,000" in result or "45.000" in result

    def test_quote_insurance_premium(self):
        from app.tools.domain_tools import quote_insurance
        result = quote_insurance("vida", {"edad": 25}, "premium")
        assert "$67,500" in result or "67.500" in result

    def test_quote_insurance_unknown_product(self):
        from app.tools.domain_tools import quote_insurance
        result = quote_insurance("nonexistent", {"edad": 25})
        assert "error" in result.lower() or "no encontrado" in result.lower()

    def test_quote_insurance_invalid_coverage(self):
        from app.tools.domain_tools import quote_insurance
        result = quote_insurance("vida", {"edad": 25}, "invalid_level")
        assert "error" in result.lower() or "inválido" in result.lower()

    def test_quote_insurance_contains_pricing_breakdown(self):
        from app.tools.domain_tools import quote_insurance
        result = quote_insurance("hogar", {"edad": 30}, "estandar")
        assert "prima" in result.lower() or "mensual" in result.lower()
        assert "anual" in result.lower()


# ──────────────────────────────────────────────
# create_policy MCP tool — Task 2.4
# ──────────────────────────────────────────────


class TestCreatePolicyTool:
    """Tests for the create_policy() MCP tool function."""

    @pytest.mark.asyncio
    async def test_import_create_policy(self):
        from app.tools.domain_tools import create_policy
        assert callable(create_policy)

    @pytest.mark.asyncio
    async def test_create_policy_no_db(self, monkeypatch):
        from app.tools.domain_tools import create_policy
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", None)
        result = await create_policy(
            customer_id="x", form_data={"acepta_terminos": True}, insurance_id="y",
        )
        assert "no está inicializada" in result

    @pytest.mark.asyncio
    async def test_create_policy_terms_not_accepted(self, monkeypatch, domain_db_maker):
        from app.tools.domain_tools import create_policy
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)
        result = await create_policy(
            customer_id="test-customer-uuid",
            form_data={"acepta_terminos": False},
            insurance_id="any-insurance-id",
        )
        assert "términos" in result.lower() or "terms" in result.lower()

    @pytest.mark.asyncio
    async def test_create_policy_success(self, monkeypatch, domain_db_maker):
        from app.tools.domain_tools import create_policy
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)

        # Seed an Insurance product
        from app.models.insurance import Insurance
        async with domain_db_maker() as session:
            ins = Insurance(nombre="Seguro de Vida Test", insurance_category="personal")
            session.add(ins)
            await session.commit()
            insurance_id = ins.id

        result = await create_policy(
            customer_id="test-customer-uuid",
            form_data={"acepta_terminos": True, "nombre": "Juan"},
            insurance_id=insurance_id,
        )
        assert "POL-" in result
        assert "Seguro de Vida Test" in result
        assert "activo" in result.lower() or "Activo" in result or "Activa" in result

    @pytest.mark.asyncio
    async def test_create_policy_without_acepta_terminos(self, monkeypatch, domain_db_maker):
        from app.tools.domain_tools import create_policy
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)

        async with domain_db_maker() as session:
            from app.models.insurance import Insurance
            ins = Insurance(nombre="Test Seguro")
            session.add(ins)
            await session.commit()
            insurance_id = ins.id

        result = await create_policy(
            customer_id="test-customer-uuid",
            form_data={},
            insurance_id=insurance_id,
        )
        assert "términos" in result.lower() or "terms" in result.lower()

    @pytest.mark.asyncio
    async def test_create_policy_customer_not_found(self, monkeypatch, domain_db_maker):
        from app.tools.domain_tools import create_policy
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)

        async with domain_db_maker() as session:
            from app.models.insurance import Insurance
            ins = Insurance(nombre="Test Seguro")
            session.add(ins)
            await session.commit()
            insurance_id = ins.id

        result = await create_policy(
            customer_id="nonexistent",
            form_data={"acepta_terminos": True},
            insurance_id=insurance_id,
        )
        assert "no se encontró" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_create_policy_creates_application_and_policy(self, monkeypatch, domain_db_maker):
        """Verify both Application and Policy are created atomically."""
        from app.tools.domain_tools import create_policy
        from app.tools import domain_tools as dt
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)

        from app.models.insurance import Insurance
        async with domain_db_maker() as session:
            ins = Insurance(nombre="Test Seguro", insurance_category="personal")
            session.add(ins)
            await session.commit()
            insurance_id = ins.id

        result = await create_policy(
            customer_id="test-customer-uuid",
            form_data={"acepta_terminos": True, "nombre": "Juan"},
            insurance_id=insurance_id,
        )
        assert "POL-" in result

        # Verify Application + Policy in DB
        from app.models.application import Application
        from app.models.policy import Policy
        async with domain_db_maker() as session:
            apps = (await session.execute(
                __import__("sqlalchemy").select(Application)
            )).scalars().all()
            assert len(apps) == 1
            assert apps[0].tipo == "seguro"

            policies = (await session.execute(
                __import__("sqlalchemy").select(Policy)
            )).scalars().all()
            assert len(policies) == 1
            assert policies[0].insurance_id == insurance_id
