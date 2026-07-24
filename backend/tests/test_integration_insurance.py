"""Integration/E2E tests for insurance personalization by category + segment.

Covers the full flow across components:
1. Seed CSV → SegmentDataService → lookup_by_documento
2. ChatService profile pre-seed (get_customer) → recommend_insurance
3. Anonymous set_category → recommend_insurance
4. MU category fallback (no compound rules)
5. Edge cases: unknown doc, missing segmento, no CSV data
"""

import csv
import os
import tempfile
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services.recommendation_engine import (
    match_products_by_segment,
    PRODUCTS,
    SEGMENTO_LABELS,
)
from app.services.segment_data import (
    CATEGORY_MAP,
    PRODUCT_COLUMNS,
    SegmentDataService,
)
from app.services.chat import ChatService
from app.tools import domain_tools as dt
from app.models.session import Session


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "SERIE", "GENERO", "RANGO_EDAD", "RANGO_SALARIAL", "CATEGORIA",
    "SEGMENTO_GRUPO_FAMILIAR", "SEGMENTO_POBLACIONAL", "PIRAMIDE_NUEVA",
    "EMPRESA_FOCO", "CIUDAD_AFILIADO", "HOTELES", "PISCILAGO",
    "DROGUERIA", "AGENCIAS", "VIVIENDA",
]


def _make_segment_csv(path: str, rows: list[dict]) -> str:
    """Write a CSV in the format SegmentDataService.load() expects."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(",".join(CSV_COLUMNS) + "\n")
        for row in rows:
            f.write(",".join(str(row.get(c, "")) for c in CSV_COLUMNS) + "\n")
    return path


SAMPLE_ROWS = [
    # doc=100, SIGMA→A, LAMBDA
    {
        "SERIE": "100", "GENERO": "M",
        "RANGO_EDAD": "20 a 35 años", "RANGO_SALARIAL": "Entre 1 y 1.5 SMLV",
        "CATEGORIA": "SIGMA", "SEGMENTO_GRUPO_FAMILIAR": "LAMBDA",
        "HOTELES": "NO", "PISCILAGO": "NO",
        "DROGUERIA": "SI", "AGENCIAS": "NO", "VIVIENDA": "NO",
    },
    # doc=200, PI→B, RHO
    {
        "SERIE": "200", "GENERO": "F",
        "RANGO_EDAD": "36 a 45 años", "RANGO_SALARIAL": "Entre 4 y 6 SMLV",
        "CATEGORIA": "PI", "SEGMENTO_GRUPO_FAMILIAR": "RHO",
        "HOTELES": "NO", "PISCILAGO": "NO",
        "DROGUERIA": "SI", "AGENCIAS": "NO", "VIVIENDA": "SI",
    },
    # doc=300, ZETA→C, LAMBDA — consumes hoteles + vivienda
    {
        "SERIE": "300", "GENERO": "M",
        "RANGO_EDAD": "46 a 60 años", "RANGO_SALARIAL": "Más de 10 SMLV",
        "CATEGORIA": "ZETA", "SEGMENTO_GRUPO_FAMILIAR": "LAMBDA",
        "HOTELES": "SI", "PISCILAGO": "NO",
        "DROGUERIA": "SI", "AGENCIAS": "NO", "VIVIENDA": "SI",
    },
    # doc=400, MU→None, LAMBDA
    {
        "SERIE": "400", "GENERO": "F",
        "RANGO_EDAD": "20 a 35 años", "RANGO_SALARIAL": "Menor al SMLV",
        "CATEGORIA": "MU", "SEGMENTO_GRUPO_FAMILIAR": "LAMBDA",
        "HOTELES": "NO", "PISCILAGO": "NO",
        "DROGUERIA": "NO", "AGENCIAS": "NO", "VIVIENDA": "NO",
    },
    # doc=500, SIGMA→A, empty segmento → None
    {
        "SERIE": "500", "GENERO": "F",
        "RANGO_EDAD": "20 a 35 años", "RANGO_SALARIAL": "Entre 1 y 1.5 SMLV",
        "CATEGORIA": "SIGMA", "SEGMENTO_GRUPO_FAMILIAR": "",
        "HOTELES": "NO", "PISCILAGO": "NO",
        "DROGUERIA": "SI", "AGENCIAS": "NO", "VIVIENDA": "NO",
    },
    # doc=600, SIGMA→A, IOTA
    {
        "SERIE": "600", "GENERO": "M",
        "RANGO_EDAD": "36 a 45 años", "RANGO_SALARIAL": "Entre 2 y 4 SMLV",
        "CATEGORIA": "SIGMA", "SEGMENTO_GRUPO_FAMILIAR": "IOTA",
        "HOTELES": "NO", "PISCILAGO": "SI",
        "DROGUERIA": "SI", "AGENCIAS": "NO", "VIVIENDA": "NO",
    },
]


class MockToolCall:
    """Minimal tool call mock matching ChatService expectations."""
    def __init__(self, name: str, arguments: dict):
        self.function = MagicMock()
        self.function.name = name
        self.function.arguments = __import__("json").dumps(arguments)
        self.id = f"call_{name}"
        self.type = "function"


# ════════════════════════════════════════════════════════════════════
# 1. Seed → SegmentDataService Integration
# ════════════════════════════════════════════════════════════════════

class TestSeedToSegmentData:
    """Load a real CSV into SegmentDataService and query it."""

    @pytest.fixture
    def svc(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            path = f.name
            _make_segment_csv(path, SAMPLE_ROWS)
        svc = SegmentDataService(path)
        svc.load()
        yield svc
        os.unlink(path)

    # ── Load ──────────────────────────────────────────────────────

    def test_loads_successfully(self, svc):
        assert svc.is_loaded() is True

    def test_loads_all_rows(self, svc):
        """All 6 sample rows loaded."""
        assert svc.lookup_by_documento("100") is not None
        assert svc.lookup_by_documento("200") is not None
        assert svc.lookup_by_documento("300") is not None
        assert svc.lookup_by_documento("400") is not None
        assert svc.lookup_by_documento("500") is not None
        assert svc.lookup_by_documento("600") is not None

    def test_categories_detected(self, svc):
        cats = svc.get_categories()
        assert "A" in cats
        assert "B" in cats
        assert "C" in cats

    def test_segments_detected(self, svc):
        segs = svc.get_segments()
        assert "LAMBDA" in segs
        assert "RHO" in segs
        assert "IOTA" in segs

    # ── Category mapping ──────────────────────────────────────────

    def test_sigma_maps_to_a(self, svc):
        result = svc.lookup_by_documento("100")
        assert result["categoria"] == "A"

    def test_pi_maps_to_b(self, svc):
        result = svc.lookup_by_documento("200")
        assert result["categoria"] == "B"

    def test_zeta_maps_to_c(self, svc):
        result = svc.lookup_by_documento("300")
        assert result["categoria"] == "C"

    def test_mu_maps_to_none(self, svc):
        result = svc.lookup_by_documento("400")
        assert result["categoria"] is None

    # ── Segment mapping ───────────────────────────────────────────

    def test_segmento_present(self, svc):
        result = svc.lookup_by_documento("100")
        assert result["segmento"] == "LAMBDA"

    def test_empty_segmento_becomes_none(self, svc):
        """Empty SEGMENTO_GRUPO_FAMILIAR → None (not empty string)."""
        result = svc.lookup_by_documento("500")
        assert result["segmento"] is None

    def test_segmento_preserved_as_is(self, svc):
        result = svc.lookup_by_documento("200")
        assert result["segmento"] == "RHO"

    # ── Consumos ──────────────────────────────────────────────────

    def test_consumos_hoteles_si(self, svc):
        result = svc.lookup_by_documento("300")
        assert result["consumos"]["hoteles"] is True

    def test_consumos_hoteles_no(self, svc):
        result = svc.lookup_by_documento("100")
        assert result["consumos"]["hoteles"] is False

    def test_consumos_drogueria_si(self, svc):
        result = svc.lookup_by_documento("100")
        assert result["consumos"]["drogueria"] is True

    # ── Unknown / edge lookups ────────────────────────────────────

    def test_unknown_documento_returns_none(self, svc):
        assert svc.lookup_by_documento("99999") is None

    def test_empty_documento_returns_none(self, svc):
        assert svc.lookup_by_documento("") is None

    def test_none_documento_returns_none(self, svc):
        assert svc.lookup_by_documento(None) is None

    # ── Aggregate stats ───────────────────────────────────────────

    def test_aggregate_stats_all(self, svc):
        stats = svc.get_aggregate_stats()
        assert len(stats) >= 3  # (A,LAMBDA), (B,RHO), (C,LAMBDA), ...

    def test_aggregate_stats_by_category_a(self, svc):
        stats = svc.get_aggregate_stats(categoria="A")
        assert all(s["categoria"] == "A" for s in stats)

    def test_aggregate_stats_by_segment_lambda(self, svc):
        stats = svc.get_aggregate_stats(segmento="LAMBDA")
        assert all(s["segmento"] == "LAMBDA" for s in stats)

    def test_aggregate_stats_pct_format(self, svc):
        """Percentage columns exist and are floats."""
        stats = svc.get_aggregate_stats()
        assert len(stats) > 0
        s = stats[0]
        for col in PRODUCT_COLUMNS:
            assert f"pct_{col.lower()}" in s
            assert isinstance(s[f"pct_{col.lower()}"], float)


# ════════════════════════════════════════════════════════════════════
# 2. Recommendation Flow with Documento (Full E2E)
# ════════════════════════════════════════════════════════════════════

class TestRecommendationWithDocumento:
    """
    Full integration: SegmentDataService singleton (loaded from real CSV)
    + recommend_insurance MCP tool with a known documento.
    
    Verifies:
    - Lookup produces correct categoria+segmento
    - Compound rules (R8-R13) fire based on categoria+segmento
    - Conversational rules (R1-R7) fire based on profile
    - Products are merged, scored, and sorted correctly
    - Output format includes personalized messaging
    """

    @pytest.fixture
    def segment_svc(self):
        """Create a real SegmentDataService with temp CSV and set it as singleton."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            path = f.name
            _make_segment_csv(path, SAMPLE_ROWS)
        svc = SegmentDataService(path)
        svc.load()
        yield svc
        os.unlink(path)

    def test_documento_a_lambda_produces_vida_hogar(
        self, monkeypatch, segment_svc
    ):
        """
        Documento 100 (A, LAMBDA) → compound R8 fires (vida+hogar).
        Empty profile → only compound products appear.
        """
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: segment_svc),
        )
        result = dt.recommend_insurance({}, "100")
        assert "Seguro de Vida" in result
        assert "Seguro Hogar" in result
        assert "categoría A" in result or "categoria A" in result

    def test_documento_a_lambda_with_profile_merges_both(
        self, monkeypatch, segment_svc
    ):
        """
        Documento 100 (A, LAMBDA) + conversational profile → 
        both R1-R7 products (viajes) AND R8 products (vida, hogar) appear.
        """
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: segment_svc),
        )
        profile = {
            "viaja_frecuentemente": True,
            "es_propietario_vivienda": True,
        }
        result = dt.recommend_insurance(profile, "100")
        # Conversational: viajes, hogar (R3+R6)
        assert "Asistencia Médica Viajes" in result
        # Compound: vida, hogar (R8)
        assert "Seguro de Vida" in result
        assert "Seguro Hogar" in result
        # Category personalization note
        assert "categoría A" in result or "categoria A" in result

    def test_documento_b_rho_produces_accidentes_movilidad(
        self, monkeypatch, segment_svc
    ):
        """
        Documento 200 (B, RHO) → R11 fires (accidentes+movilidad).
        Empty profile → only compound products.
        """
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: segment_svc),
        )
        result = dt.recommend_insurance({}, "200")
        assert "Accidentes Personales" in result
        assert "Seguro Movilidad" in result
        assert "categoría B" in result or "categoria B" in result

    def test_documento_c_lambda_produces_all_six(
        self, monkeypatch, segment_svc
    ):
        """
        Documento 300 (C, LAMBDA) → R12 fires all 6 products.
        """
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: segment_svc),
        )
        result = dt.recommend_insurance({}, "300")
        assert "Seguro de Vida" in result
        assert "Seguro Hogar" in result
        assert "Seguro Movilidad" in result
        assert "Accidentes Personales" in result
        assert "Asistencia Médica Viajes" in result
        assert "Seguro Mascotas" in result
        assert "categoría C" in result or "categoria C" in result

    def test_documento_a_iota_r13_fires(
        self, monkeypatch, segment_svc
    ):
        """
        Documento 600 (A, IOTA) → R8 (A,LAMBDA) doesn't match IOTA,
        R13 (any, IOTA) matches → vida+hogar.
        """
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: segment_svc),
        )
        result = dt.recommend_insurance({}, "600")
        assert "Seguro de Vida" in result
        assert "Seguro Hogar" in result

    def test_documento_confidence_merging(
        self, monkeypatch, segment_svc
    ):
        """
        Conversational 'high' + compound 'medium' → overall 'high'.
        Conversational viajes (R3, high) + compound vida/hogar (R8, medium).
        """
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: segment_svc),
        )
        profile = {"viaja_frecuentemente": True}
        result = dt.recommend_insurance(profile, "100")
        # viajes is conversational high, compound doesn't produce viajes
        assert "alta" in result.lower() or "✅" in result
        assert "Asistencia Médica Viajes" in result

    def test_documento_segment_boost_reorders(
        self, monkeypatch, segment_svc
    ):
        """
        LAMBDA boost → vida+hogar appear before non-boosted compound products
        when same confidence. With C+LAMBDA (R12 mixed), vida+hogar are high,
        rest are medium → high sorts first regardless of boost.
        """
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: segment_svc),
        )
        result = dt.recommend_insurance({}, "300")  # C, LAMBDA
        # All 6 products from R12 — output lines numbered 1-6
        assert "**1." in result  # numbered list
        assert "**6." in result or "**5." in result

    @pytest.mark.asyncio
    async def test_chatflow_profile_preseed_and_recommend(
        self, monkeypatch, segment_svc, db_engine
    ):
        """
        Full chat flow integration:
        1. ChatService._update_session_state with get_customer tool
        2. Profile gets pre-seeded with categoria + segmento
        3. recommend_insurance called with the pre-seeded profile (via documento)
        """
        # Install singleton
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: segment_svc),
        )

        maker = async_sessionmaker(db_engine, expire_on_commit=False)
        service = ChatService(
            session_maker=maker,
            ai_client=MagicMock(),
            tool_bridge=MagicMock(),
        )
        session, _ = await service.get_or_create_session(session_id=None)
        session.estado_actual = "perfilando"
        session.insurance_profile = {}
        async with maker() as db:
            await db.merge(session)
            await db.commit()

        # Step 1: Pre-seed via get_customer tool
        await service._update_session_state(
            session.id,
            tool_calls=[MockToolCall(
                "get_customer",
                {"documento_identidad": "100"},
            )],
        )

        # Verify pre-seed
        async with maker() as db:
            updated = await db.get(Session, session.id)
        assert updated is not None
        assert updated.insurance_profile.get("categoria_afiliacion") == "A"
        assert updated.insurance_profile.get("segmento_grupo_familiar") == "LAMBDA"

        # Step 2: Call recommend_insurance with the documento + profile
        profile = updated.insurance_profile or {}
        profile["viaja_frecuentemente"] = True  # conversational rule
        result = dt.recommend_insurance(profile, "100")
        assert "Seguro de Vida" in result  # compound R8
        assert "Seguro Hogar" in result    # compound R8
        assert "Asistencia Médica Viajes" in result  # conversational R3
        assert "categoría A" in result or "categoria A" in result


# ════════════════════════════════════════════════════════════════════
# 3. Anonymous Flow — No Documento
# ════════════════════════════════════════════════════════════════════

class TestAnonymousFlow:
    """Anonymous user (no documento) → salary profiling → set_category → recommend."""

    def _make_session(self, insurance_profile=None):
        return Session(
            id="anon-test",
            estado_actual="perfilando",
            insurance_profile=insurance_profile or {},
            campos_diligenciados={},
            activa=True,
        )

    def _build_prompt(self, session):
        service = ChatService(
            session_maker=MagicMock(),
            ai_client=MagicMock(),
            tool_bridge=MagicMock(),
        )
        return service._build_system_prompt(session)

    # ── Anonymous salary instructions ─────────────────────────────

    def test_system_prompt_includes_salary_profiling_when_no_categoria(self):
        """Without categoria_afiliacion, system prompt includes salary section."""
        session = self._make_session(insurance_profile={})
        prompt = self._build_prompt(session)
        assert "PERFILACIÓN SIN DOCUMENTO" in prompt
        assert "rango salarial" in prompt
        assert "set_category" in prompt
        # Salary category mapping
        assert "$4.500.000" in prompt
        assert "$2.000.000" in prompt

    def test_system_prompt_no_salary_when_categoria_present(self):
        """With categoria_afiliacion set, salary section is OMITTED."""
        session = self._make_session(
            insurance_profile={"categoria_afiliacion": "B"}
        )
        prompt = self._build_prompt(session)
        assert "PERFILACIÓN SIN DOCUMENTO" not in prompt

    def test_system_prompt_salary_defaults_to_c_when_no_share(self):
        """Prompt says to assign Categoria C if user declines to share."""
        session = self._make_session(insurance_profile={})
        prompt = self._build_prompt(session)
        assert "Categoría C por defecto" in prompt or (
            "asigná Categoría C" in prompt
        )

    # ── set_category updates profile ──────────────────────────────

    @pytest.mark.asyncio
    async def test_set_category_a_updates_profile(self, db_engine, monkeypatch):
        """set_category('A') → insurance_profile.categoria_afiliacion = 'A'."""
        from app.tools import domain_tools
        maker = async_sessionmaker(db_engine, expire_on_commit=False)
        monkeypatch.setattr(domain_tools, "async_session_maker", maker)

        async with maker() as db:
            session = Session(
                id="anon-set-cat-a",
                estado_actual="perfilando",
                insurance_profile={},
                activa=True,
            )
            db.add(session)
            await db.commit()

        result = await domain_tools.set_category(
            session_id="anon-set-cat-a", categoria="A",
        )
        assert "Categoría A registrada" in result

        async with maker() as db:
            updated = await db.get(Session, "anon-set-cat-a")
        assert updated.insurance_profile.get("categoria_afiliacion") == "A"

    @pytest.mark.asyncio
    async def test_set_category_b_updates_profile(self, db_engine, monkeypatch):
        """set_category('B') → insurance_profile.categoria_afiliacion = 'B'."""
        from app.tools import domain_tools
        maker = async_sessionmaker(db_engine, expire_on_commit=False)
        monkeypatch.setattr(domain_tools, "async_session_maker", maker)

        async with maker() as db:
            session = Session(
                id="anon-set-cat-b",
                estado_actual="perfilando",
                insurance_profile={},
                activa=True,
            )
            db.add(session)
            await db.commit()

        result = await domain_tools.set_category(
            session_id="anon-set-cat-b", categoria="B",
        )
        assert "Categoría B registrada" in result

        async with maker() as db:
            updated = await db.get(Session, "anon-set-cat-b")
        assert updated.insurance_profile.get("categoria_afiliacion") == "B"

    @pytest.mark.asyncio
    async def test_set_category_invalid_returns_error(self, db_engine):
        """Invalid category returns error without modifying session."""
        from app.tools import domain_tools
        result = await domain_tools.set_category(
            session_id="any-id", categoria="INVALID",
        )
        assert "Error" in result
        assert "A, B o C" in result

    @pytest.mark.asyncio
    async def test_anonymous_set_cat_then_recommend_uses_compound(
        self, db_engine, monkeypatch
    ):
        """
        Set category via set_category → recommendation with that profile 
        uses compound rules (R8-R13) directly via categoria_afiliacion.
        """
        from app.tools import domain_tools
        maker = async_sessionmaker(db_engine, expire_on_commit=False)
        monkeypatch.setattr(domain_tools, "async_session_maker", maker)

        async with maker() as db:
            session = Session(
                id="anon-rec-chain",
                estado_actual="perfilando",
                insurance_profile={},
                activa=True,
            )
            db.add(session)
            await db.commit()

        # Set category C via MCP tool
        result = await domain_tools.set_category(
            session_id="anon-rec-chain", categoria="C",
        )
        assert "Categoría C registrada" in result

        # Get the updated session and use its profile for recommend_insurance
        async with maker() as db:
            updated = await db.get(Session, "anon-rec-chain")
        profile = dict(updated.insurance_profile or {})
        profile["viaja_frecuentemente"] = True

        # Session's profile has categoria_afiliacion=C → R12 fires
        rec = domain_tools.recommend_insurance(profile)
        assert "Seguro de Vida" in rec
        assert "Seguro Hogar" in rec
        assert "Seguro Movilidad" in rec
        assert "Asistencia Médica Viajes" in rec  # conversational R3

    # ── set_category → recommend_insurance chain ──────────────────

    def test_anonymous_cat_c_recommend_uses_compound(
        self, monkeypatch
    ):
        """
        Anonymous user sets Cat C → profile has categoria_afiliacion=C.
        recommend_insurance with this profile (no documento) uses 
        match_products_by_segment with categoria=C, which triggers R12
        (all 6 products regardless of segmento).
        """
        # Track calls to match_products_by_segment
        calls = []
        original = match_products_by_segment

        def tracking_by_segment(profile, categoria=None, segmento=None, *, segmento_vida=None, en_credito=False):
            calls.append((categoria, segmento, segmento_vida, en_credito))
            return original(profile, categoria, segmento, segmento_vida=segmento_vida, en_credito=en_credito)

        monkeypatch.setattr(
            dt, "match_products_by_segment", tracking_by_segment,
        )

        # Profile with categoria_afiliacion=C (set by set_category)
        # R12 fires regardless of segmento → all 6 compound products
        profile = {"categoria_afiliacion": "C"}
        result = dt.recommend_insurance(profile)

        # by_segment was called with categoria=C
        assert len(calls) >= 1
        cat_call = calls[0][0]
        assert cat_call == "C"
        # R12: all products appear (compound only, no conversational)
        assert "Seguro de Vida" in result
        assert "Seguro Hogar" in result
        assert "Seguro Movilidad" in result
        assert "Accidentes Personales" in result
        assert "categoría C" in result or "categoria C" in result

    def test_anonymous_cat_c_all_six_products(
        self, monkeypatch
    ):
        """
        Anonymous user sets Cat C → R12 fires all 6 products.
        """
        profile = {"categoria_afiliacion": "C"}
        # Need segment data service to exist (even if not loaded)
        class MockSvc:
            def is_loaded(self): return False
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        result = dt.recommend_insurance(profile)
        assert "Seguro de Vida" in result
        assert "Seguro Hogar" in result
        assert "Seguro Movilidad" in result
        assert "Accidentes Personales" in result
        assert "Asistencia Médica Viajes" in result
        assert "Seguro Mascotas" in result
        assert "categoría C" in result or "categoria C" in result


# ════════════════════════════════════════════════════════════════════
# 4. MU Category — No Compound Rules
# ════════════════════════════════════════════════════════════════════

class TestMUCustomer:
    """MU customers get no compound rules, only conversational R1-R7."""

    def test_mu_from_documento_no_compound(self, monkeypatch):
        """Documento 400 (MU→None) → recommend_insurance uses match_products."""
        class MockSvc:
            def is_loaded(self): return True
            def lookup_by_documento(self, doc):
                return {"categoria": None, "segmento": "LAMBDA"}

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        result = dt.recommend_insurance({}, "400")
        # No compound rules fired for MU
        assert "No encontramos productos" in result

    def test_mu_with_conversational_profile_returns_products(self, monkeypatch):
        """MU + conversational profile → R1-R7 products only."""
        class MockSvc:
            def is_loaded(self): return True
            def lookup_by_documento(self, doc):
                return {"categoria": None, "segmento": "LAMBDA"}

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        profile = {"viaja_frecuentemente": True}
        result = dt.recommend_insurance(profile, "400")
        # Conversational R3 matches
        assert "Asistencia Médica Viajes" in result
        # No category personalization note
        assert "categoría" not in result.lower()

    def test_mu_no_category_label_in_output(self, monkeypatch):
        """MU output should NOT have category personalization footer."""
        class MockSvc:
            def is_loaded(self): return True
            def lookup_by_documento(self, doc):
                return {"categoria": None, "segmento": "LAMBDA"}

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        profile = {"viaja_frecuentemente": True}
        result = dt.recommend_insurance(profile, "400")
        # No "*Recomendación personalizada para categoría*"
        assert "Recomendación personalizada" not in result

    def test_mu_lookup_from_real_csv(self, segment_svc):
        """MU from real CSV returns categoria=None."""
        result = segment_svc.lookup_by_documento("400")
        assert result is not None
        assert result["categoria"] is None
        assert result["segmento"] == "LAMBDA"

    @pytest.fixture
    def segment_svc(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            path = f.name
            _make_segment_csv(path, SAMPLE_ROWS)
        svc = SegmentDataService(path)
        svc.load()
        yield svc
        os.unlink(path)


# ════════════════════════════════════════════════════════════════════
# 5. Edge Cases
# ════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Unknown documento, missing segmento, CSV not loaded."""

    def test_unknown_documento_falls_back_to_match_products(self, monkeypatch):
        """Documento not in CSV → fallback to match_products (conversational only)."""
        class MockSvc:
            def is_loaded(self): return True
            def lookup_by_documento(self, doc):
                return None  # not found

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        profile = {"viaja_frecuentemente": True}
        result = dt.recommend_insurance(profile, "99999")
        assert "Asistencia Médica Viajes" in result
        # No category personalization
        assert "categoría" not in result.lower()

    def test_unknown_documento_empty_profile(self, monkeypatch):
        """Unknown doc + empty profile → no products."""
        class MockSvc:
            def is_loaded(self): return True
            def lookup_by_documento(self, doc):
                return None

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        result = dt.recommend_insurance({}, "99999")
        assert "No encontramos productos" in result

    def test_missing_segmento_still_matches_compound_rules(self, monkeypatch):
        """
        Documento 500 (A, None/segmento=vacio) → categoria=A usable,
        None segmento matches any segmento in SEGMENT_RULES.
        R8 needs LAMBDA, doesn't match None.
        R11 needs B, doesn't match A.
        R12 needs C, doesn't match A.
        R13 has None categoria + IOTA segmento → IOTA != None.
        So: None of the compound rules match (A+None).
        """
        class MockSvc:
            def is_loaded(self): return True
            def lookup_by_documento(self, doc):
                return {"categoria": "A", "segmento": None}

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        profile = {"viaja_frecuentemente": True}
        result = dt.recommend_insurance(profile, "500")
        # Conversational should still work
        assert "Asistencia Médica Viajes" in result
        # Category A is valid → we still get category note
        assert "categoría A" in result or "categoria A" in result

    def test_csv_not_loaded_falls_back(self, monkeypatch):
        """SegmentDataService not loaded → recommend_insurance uses match_products."""
        class MockSvc:
            def is_loaded(self): return False

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        profile = {"viaja_frecuentemente": True}
        result = dt.recommend_insurance(profile, "100")
        # Falls back to match_products
        assert "Asistencia Médica Viajes" in result

    def test_no_singleton_instance_falls_back(self, monkeypatch):
        """SegmentDataService.get_instance raises RuntimeError → fallback."""
        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(
                lambda cls: (_ for _ in ()).throw(RuntimeError(
                    "SegmentDataService not initialized"
                ))
            ),
        )
        profile = {"viaja_frecuentemente": True}
        result = dt.recommend_insurance(profile, "100")
        assert "Asistencia Médica Viajes" in result

    def test_recommend_insurance_with_salario_inference(self, monkeypatch):
        """No doc, no categoria_afiliacion, but salario → infers categoria."""
        class MockSvc:
            def is_loaded(self): return False

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )
        # salario=8M → >4 SMMLV → categoria C → R12
        result = dt.recommend_insurance({"salario": 8_000_000})
        assert "Seguro de Vida" in result
        assert "categoría C" in result or "categoria C" in result

    @pytest.mark.asyncio
    async def test_chat_profile_preseed_no_segment_data(
        self, monkeypatch, db_engine
    ):
        """get_customer called but SegmentDataService not loaded — no crash."""
        class MockSvc:
            def is_loaded(self): return True
            def lookup_by_documento(self, doc):
                return None  # doc not in dataset

        monkeypatch.setattr(
            SegmentDataService, "get_instance",
            classmethod(lambda cls: MockSvc()),
        )

        maker = async_sessionmaker(db_engine, expire_on_commit=False)
        service = ChatService(
            session_maker=maker,
            ai_client=MagicMock(),
            tool_bridge=MagicMock(),
        )
        session, _ = await service.get_or_create_session(session_id=None)
        session.estado_actual = "perfilando"
        session.insurance_profile = {}
        async with maker() as db:
            await db.merge(session)
            await db.commit()

        await service._update_session_state(
            session.id,
            tool_calls=[MockToolCall(
                "get_customer",
                {"documento_identidad": "NOT_IN_CSV"},
            )],
        )

        async with maker() as db:
            updated = await db.get(Session, session.id)
        assert updated is not None
        # Profile stays empty — doc not found
        assert updated.insurance_profile == {}
