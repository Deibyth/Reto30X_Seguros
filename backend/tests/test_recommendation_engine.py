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
    SEGMENT_RULES,
    SEGMENT_BOOST,
    SEGMENTO_LABELS,
    match_products,
    match_products_by_segment,
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

    # ── T004: recommend_insurance con documento ──────────────────────

    def test_recommend_insurance_with_documento(self, monkeypatch):
        """Documento encontrado → categoría A en output."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        class MockSegmentService:
            def is_loaded(self):
                return True
            def lookup_by_documento(self, doc):
                return {"categoria": "A", "segmento": "LAMBDA", "segmento_grupo_familiar": "LAMBDA"}

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        result = dt.recommend_insurance({}, "12345")
        assert "categoría A" in result or "categoria A" in result

    def test_recommend_insurance_documento_not_found(self, monkeypatch):
        """Documento no encontrado → fallback a match_products."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        class MockSegmentService:
            def is_loaded(self):
                return True
            def lookup_by_documento(self, doc):
                return None

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        result = dt.recommend_insurance({"viaja_frecuentemente": True}, "99999")
        assert "Asistencia Médica Viajes" in result

    def test_recommend_insurance_no_documento(self):
        """Sin documento ni profile.categoria → match_products (backward compat)."""
        from app.tools.domain_tools import recommend_insurance
        result_viajes = recommend_insurance({"viaja_frecuentemente": True})
        assert "Asistencia Médica Viajes" in result_viajes
        result_empty = recommend_insurance({})
        assert "No encontramos productos" in result_empty

    def test_recommend_insurance_profile_with_categoria(self, monkeypatch):
        """Sin doc pero profile con categoria_afiliacion → usa by_segment."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        # Ensure segment_data is accessible (even if not loaded, should not crash)
        class MockSegmentService:
            def is_loaded(self):
                return False
            def lookup_by_documento(self, doc):
                return None

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        result = dt.recommend_insurance({"categoria_afiliacion": "C"})
        assert "productos" in result.lower()

    def test_recommend_insurance_empty_profile_with_doc(self, monkeypatch):
        """{} + doc (A, LAMBDA) → compound rules still fire (vida + hogar)."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        class MockSegmentService:
            def is_loaded(self):
                return True
            def lookup_by_documento(self, doc):
                return {"categoria": "A", "segmento": "LAMBDA"}

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        result = dt.recommend_insurance({}, "12345")
        assert "Seguro de Vida" in result
        assert "categoría A" in result or "categoria A" in result

    def test_recommend_insurance_salario_inference(self, monkeypatch):
        """Profile con salario 8M → infiere C (R12) → productos en output."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        class MockSegmentService:
            def is_loaded(self):
                return False
            def lookup_by_documento(self, doc):
                return None

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        # salario=8M → >4 SMMLV → categoria C → R12 gives all 6 products
        result = dt.recommend_insurance({"salario": 8000000})
        assert "Recomendación personalizada" in result
        assert "Seguro de Vida" in result


class TestLoadSegmentDataTool:
    """Tests for the load_segment_data() MCP tool."""

    def test_load_segment_data_by_documento(self, monkeypatch):
        """Documento encontrado → texto con 'categoría'."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        class MockSegmentService:
            def is_loaded(self):
                return True
            def lookup_by_documento(self, doc):
                return {"categoria": "A", "segmento": "LAMBDA"}
            def get_aggregate_stats(self, categoria=None, segmento=None):
                return [{
                    "categoria": "A", "segmento": "LAMBDA",
                    "total_afiliados": 1000,
                    "pct_drogueria": 50.0, "pct_hoteles": 10.0,
                    "pct_piscilago": 5.0, "pct_agencias": 3.0,
                    "pct_vivienda": 2.0,
                }]

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        result = dt.load_segment_data("12345")
        assert "categoría" in result.lower() or "categoria" in result.lower()

    def test_load_segment_data_all(self, monkeypatch):
        """Sin documento → múltiples segmentos listados."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        class MockSegmentService:
            def is_loaded(self):
                return True
            def lookup_by_documento(self, doc):
                return None
            def get_aggregate_stats(self, categoria=None, segmento=None):
                return [
                    {"categoria": "A", "segmento": "LAMBDA",
                     "total_afiliados": 500, "pct_drogueria": 50.0,
                     "pct_hoteles": 5.0, "pct_piscilago": 3.0,
                     "pct_agencias": 2.0, "pct_vivienda": 1.0},
                    {"categoria": "B", "segmento": "RHO",
                     "total_afiliados": 300, "pct_drogueria": 40.0,
                     "pct_hoteles": 10.0, "pct_piscilago": 8.0,
                     "pct_agencias": 5.0, "pct_vivienda": 3.0},
                ]

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        result = dt.load_segment_data()
        assert "Sin grupo familiar" in result
        assert "Monoparental" in result

    def test_load_segment_data_not_found(self, monkeypatch):
        """Documento no encontrado → mensaje específico."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        class MockSegmentService:
            def is_loaded(self):
                return True
            def lookup_by_documento(self, doc):
                return None

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        result = dt.load_segment_data("99999")
        assert "No se encontraron datos" in result

    def test_load_segment_data_unavailable(self, monkeypatch):
        """is_loaded=False → 'no disponibles'."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        class MockSegmentService:
            def is_loaded(self):
                return False

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        result = dt.load_segment_data()
        assert "no disponibles" in result.lower()

    def test_load_segment_data_no_instance(self, monkeypatch):
        """get_instance raises RuntimeError → 'no disponibles'."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: (_ for _ in ()).throw(RuntimeError))
        result = dt.load_segment_data()
        assert "no disponibles" in result.lower()


class TestGetCustomerSegment:
    """Tests for get_customer() with segment enrichment."""

    @pytest.mark.asyncio
    async def test_get_customer_with_segmento(self, monkeypatch, domain_db_maker):
        """Cliente encontrado + segmento en CSV → '**Segmento familiar:**'."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService
        from app.models.customer import Customer

        # Seed a customer
        async with domain_db_maker() as session:
            c = Customer(
                nombre_completo="Juan Perez",
                documento_identidad="12345",
                email="juan@test.com",
                salario=2000000,
                tipo_contrato="indefinido",
            )
            session.add(c)
            await session.commit()

        class MockSegmentService:
            def is_loaded(self):
                return True
            def lookup_by_documento(self, doc):
                return {"categoria": "A", "segmento": "LAMBDA", "segmento_grupo_familiar": "LAMBDA"}

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        # Use domain_db_maker as async_session_maker
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)
        result = await dt.get_customer("12345")
        assert "**Segmento familiar:**" in result

    @pytest.mark.asyncio
    async def test_get_customer_without_segmento(self, monkeypatch, domain_db_maker):
        """Cliente sin segmento — sin línea extra."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService
        from app.models.customer import Customer

        async with domain_db_maker() as session:
            c = Customer(
                nombre_completo="Ana Gomez",
                documento_identidad="67890",
                email="ana@test.com",
                salario=2000000,
                tipo_contrato="indefinido",
            )
            session.add(c)
            await session.commit()

        class MockSegmentService:
            def is_loaded(self):
                return True
            def lookup_by_documento(self, doc):
                return {"categoria": "A", "segmento": None}

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)
        result = await dt.get_customer("67890")
        assert "**Segmento familiar:**" not in result

    @pytest.mark.asyncio
    async def test_get_customer_no_csv(self, monkeypatch, domain_db_maker):
        """CSV no cargado → sin segmento line."""
        from app.tools import domain_tools as dt
        from app.services.segment_data import SegmentDataService
        from app.models.customer import Customer

        async with domain_db_maker() as session:
            c = Customer(
                nombre_completo="Luis Mora",
                documento_identidad="11111",
                email="luis@test.com",
                salario=3000000,
                tipo_contrato="indefinido",
            )
            session.add(c)
            await session.commit()

        class MockSegmentService:
            def is_loaded(self):
                return False

        monkeypatch.setattr(SegmentDataService, "get_instance", lambda: MockSegmentService())
        monkeypatch.setattr(dt, "async_session_maker", domain_db_maker)
        result = await dt.get_customer("11111")
        assert "**Segmento familiar:**" not in result


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


# ──────────────────────────────────────────────
# T003 — Compound rules (R8-R13)
# ──────────────────────────────────────────────


class TestCompoundRules:
    """SEGMENT_RULES R8-R13 match correctly per (categoria, segmento)."""

    # R8: (A, LAMBDA) → vida + hogar
    def test_r8_a_lambda(self):
        result = match_products_by_segment({}, "A", "LAMBDA")
        ids = {p["product_id"] for p in result}
        assert "vida" in ids
        assert "hogar" in ids

    # R9: (A, RHO) → vida + accidentes
    def test_r9_a_rho(self):
        result = match_products_by_segment({}, "A", "RHO")
        ids = {p["product_id"] for p in result}
        assert "vida" in ids
        assert "accidentes" in ids

    # R10: (A, EPSILON) → vida + hogar
    def test_r10_a_epsilon(self):
        result = match_products_by_segment({}, "A", "EPSILON")
        ids = {p["product_id"] for p in result}
        assert "vida" in ids
        assert "hogar" in ids

    # R11: (B, any) → accidentes + movilidad
    def test_r11_b_any(self):
        result = match_products_by_segment({}, "B", None)
        ids = {p["product_id"] for p in result}
        assert "accidentes" in ids
        assert "movilidad" in ids

    def test_r11_b_and_rho(self):
        """R11 matches (B, RHO). R13 does NOT match (B, IOTA)."""
        result = match_products_by_segment({}, "B", "RHO")
        ids = {p["product_id"] for p in result}
        assert "accidentes" in ids
        assert "movilidad" in ids
        assert "hogar" not in ids  # R13 only matches IOTA, not RHO

    # R12: (C, any) → all 6 products
    def test_r12_c_all_products(self):
        result = match_products_by_segment({}, "C", None)
        ids = {p["product_id"] for p in result}
        expected = {"vida", "hogar", "movilidad", "accidentes", "viajes", "mascotas"}
        assert ids == expected

    def test_r12_c_life_home_high(self):
        """R12: vida+hogar confidence 'high', rest 'medium'."""
        result = match_products_by_segment({}, "C", None)
        for p in result:
            if p["product_id"] in ("vida", "hogar"):
                assert p["confidence"] == "high", f"{p['product_id']} should be high"
            else:
                assert p["confidence"] == "medium", f"{p['product_id']} should be medium"

    # R13: (any, IOTA) → vida + hogar
    def test_r13_any_iota(self):
        result = match_products_by_segment({}, None, "IOTA")
        ids = {p["product_id"] for p in result}
        assert "vida" in ids
        assert "hogar" in ids

    def test_r13_with_a_and_iota(self):
        """R13 works with categoria A + segment IOTA."""
        result = match_products_by_segment({}, "A", "IOTA")
        ids = {p["product_id"] for p in result}
        assert "vida" in ids
        assert "hogar" in ids

    # MU / None fallback
    def test_mu_fallback(self):
        """MU → no compound rules, only R1-R7 (empty profile = [])."""
        result = match_products_by_segment({}, "MU", None)
        assert result == []

    def test_none_categoria(self):
        """None categoria → no compound rules."""
        result = match_products_by_segment({}, None, None)
        assert result == []

    def test_empty_profile_with_categoria_returns_compound(self):
        """Empty profile + usable categoria → compound rules still fire."""
        result = match_products_by_segment({}, "A", "LAMBDA")
        assert len(result) > 0  # compound rules fire regardless of profile


class TestSegmentBoost:
    """SEGMENT_BOOST reorders, never excludes."""

    def test_boost_reorder_lambda(self):
        """LAMBDA boost: vida/hogar appear in result (boosted products present)."""
        result = match_products_by_segment({}, "C", "LAMBDA")
        ids = {p["product_id"] for p in result}
        assert "vida" in ids
        assert "hogar" in ids

    def test_boost_never_excludes(self):
        """All matched products appear regardless of boost."""
        profile = {
            "viaja_frecuentemente": True,
            "es_propietario_vivienda": True,
            "tiene_mascota": True,
        }
        result = match_products_by_segment(profile, "A", "LAMBDA")
        ids = {p["product_id"] for p in result}
        # Conversational: viajes, hogar, mascotas
        # Compound: vida, hogar
        # So all: viajes, hogar, mascotas, vida
        assert "viajes" in ids
        assert "hogar" in ids
        assert "mascotas" in ids
        assert "vida" in ids

    def test_no_boost_for_unknown_segment(self):
        """CHI/THETA/PI → no boost modifier applied.

        With category C (R12), all 6 products are matched. LAMBDA boosts
        vida/hogar; CHI has no boost — so vida/hogar appear earlier in LAMBDA.
        """
        result_lam = match_products_by_segment({}, "C", "LAMBDA")
        result_chi = match_products_by_segment({}, "C", "CHI")
        ids_lam = [p["product_id"] for p in result_lam]
        ids_chi = [p["product_id"] for p in result_chi]
        # Both have vida at high confidence; in LAMBDA it's boosted (sort key 0),
        # in CHI it's not (sort key 1). Both sort before medium-confidence products.
        # The difference: vida's second-level sort key.
        # For LAMBDA: vida sort key at high is (0, 0, -45000) — boosted
        # For CHI:   vida sort key at high is (0, 1, -45000) — not boosted
        # Within high confidence, vida is first in LAMBDA (boosted) vs
        # hogar first in CHI (same prima_base sorting).
        lam_first = ids_lam[0]
        chi_first = ids_chi[0]
        # Both should start with vida or hogar
        assert lam_first in ("vida", "hogar")
        assert chi_first in ("vida", "hogar")


class TestMergeConfidence:
    """Confidence merging between conversational and compound rules."""

    def test_conversational_wins(self):
        """Conversational high + compound medium → high."""
        # viaja_frecuentemente → conversational high for viajes
        # A+LAMBDA compound → vida, hogar (medium from compound)
        result = match_products_by_segment(
            {"viaja_frecuentemente": True},
            "A",
            "LAMBDA",
        )
        for p in result:
            if p["product_id"] == "viajes":
                assert p["confidence"] == "high", "Conversational high should win"
            elif p["product_id"] in ("vida", "hogar"):
                assert p["confidence"] == "medium", "Compound-only should be medium"

    def test_compound_only(self):
        """Product only from compound → medium confidence."""
        result = match_products_by_segment({}, "A", "LAMBDA")
        for p in result:
            assert p["confidence"] == "medium", f"Compound-only {p['product_id']} should be medium"

    def test_overlap_reason_includes_aligned(self):
        """Overlapping product reason includes 'alineado'."""
        profile = {"viaja_frecuentemente": True, "es_propietario_vivienda": True}
        result = match_products_by_segment(profile, "A", "LAMBDA")
        # hogar could be in both conversational + compound
        for p in result:
            if p["product_id"] == "hogar" and p["confidence"] == "high":
                assert "alineado" in p["match_reason"].lower()

    def test_compound_reason_contains_category(self):
        """Compound-only reason includes category or segment reference."""
        result = match_products_by_segment({}, "A", "LAMBDA")
        for p in result:
            reason = p["match_reason"].lower()
            has_ref = "categoría" in reason or "categoria" in reason or "perfil" in reason
            assert has_ref, (
                f"Compound reason for {p['product_id']} should mention categoría or perfil, "
                f"got: {p['match_reason']}"
            )

    def test_fallback_categoria_medium(self):
        """R1-R7 with None categoria → medium + (perfil general)."""
        profile = {"viaja_frecuentemente": True}
        result = match_products_by_segment(profile, None, None)
        for p in result:
            assert p["confidence"] == "medium", (
                f"Fallback {p['product_id']} should be medium"
            )
            assert "(perfil general)" in p["match_reason"], (
                f"Fallback {p['product_id']} should have '(perfil general)' in reason"
            )


class TestBackwardCompat:
    """match_products_by_segment backward compatibility with match_products."""

    def test_by_segment_no_cat_equals_match(self):
        """match_products_by_segment(profile, None, None) == match_products(profile)."""
        profile = {"viaja_frecuentemente": True, "es_propietario_vivienda": True}
        expected = match_products(profile)
        result = match_products_by_segment(profile, None, None)
        # Both should have same product_ids (but confidence/reasons differ with fallback)
        expected_ids = {p["product_id"] for p in expected}
        result_ids = {p["product_id"] for p in result}
        assert expected_ids == result_ids

    def test_by_segment_empty_still_empty(self):
        assert match_products_by_segment({}, None, None) == []

    def test_profile_without_categoria_key(self):
        """Profile without categoria_afiliacion key → uses match_products internally."""
        profile = {"viaja_frecuentemente": True}
        result = match_products_by_segment(profile, None, None)
        assert len(result) > 0

    def test_segmento_labels_defined(self):
        """SEGMENTO_LABELS maps expected codes."""
        assert SEGMENTO_LABELS["LAMBDA"] == "Sin grupo familiar"
        assert SEGMENTO_LABELS["RHO"] == "Monoparental"
        assert SEGMENTO_LABELS["EPSILON"] == "Nuclear"
        assert SEGMENTO_LABELS["IOTA"] == "Pareja"
        assert None in SEGMENTO_LABELS

    def test_segment_rules_all_present(self):
        """All 6 compound rules are defined."""
        assert len(SEGMENT_RULES) == 6

    def test_segment_boost_keys(self):
        """SEGMENT_BOOST has expected keys."""
        for seg in ("LAMBDA", "RHO", "EPSILON", "IOTA"):
            assert seg in SEGMENT_BOOST, f"Missing SEGMENT_BOOST for {seg}"
        assert "CHI" not in SEGMENT_BOOST
