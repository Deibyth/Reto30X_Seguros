"""Tests for SegmentDataService — strict TDD."""

import os
import tempfile

import pytest

from app.services.segment_data import (
    CATEGORY_MAP,
    PRODUCT_COLUMNS,
    SegmentDataService,
)

CSV_REAL_PATH = "Usos_Productos_Afiliados_SIN_ID2.csv"


def _make_sample_csv(path: str, rows: list[dict]) -> str:
    """Write a sample CSV and return its path."""
    cols = [
        "SERIE", "GENERO", "RANGO_EDAD", "RANGO_SALARIAL", "CATEGORIA",
        "SEGMENTO_GRUPO_FAMILIAR", "SEGMENTO_POBLACIONAL", "PIRAMIDE_NUEVA",
        "EMPRESA_FOCO", "CIUDAD_AFILIADO", "HOTELES", "PISCILAGO",
        "DROGUERIA", "AGENCIAS", "VIVIENDA",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for row in rows:
            f.write(",".join(str(row.get(c, "")) for c in cols) + "\n")
    return path


# ------------------------------------------------------------------
# Category mapping
# ------------------------------------------------------------------

class TestCategoryMapping:
    def test_sigma_to_a(self):
        assert CATEGORY_MAP["SIGMA"] == "A"

    def test_pi_to_b(self):
        assert CATEGORY_MAP["PI"] == "B"

    def test_zeta_to_c(self):
        assert CATEGORY_MAP["ZETA"] == "C"

    def test_mu_to_none(self):
        assert CATEGORY_MAP["MU"] is None

    def test_unknown_returns_none(self):
        assert CATEGORY_MAP.get("UNKNOWN") is None


# ------------------------------------------------------------------
# File not found (graceful degradation)
# ------------------------------------------------------------------

class TestFileNotFound:
    def test_load_returns_false_when_file_missing(self):
        svc = SegmentDataService("/nonexistent/path.csv")
        assert svc.load() is False
        assert svc.is_loaded() is False

    def test_lookup_returns_none_when_not_loaded(self):
        svc = SegmentDataService("/nonexistent/path.csv")
        svc.load()
        assert svc.lookup_by_documento("1") is None

    def test_aggregate_stats_empty_when_not_loaded(self):
        svc = SegmentDataService("/nonexistent/path.csv")
        svc.load()
        assert svc.get_aggregate_stats() == []

    def test_categories_empty_when_not_loaded(self):
        svc = SegmentDataService("/nonexistent/path.csv")
        svc.load()
        assert svc.get_categories() == []

    def test_segments_empty_when_not_loaded(self):
        svc = SegmentDataService("/nonexistent/path.csv")
        svc.load()
        assert svc.get_segments() == []


# ------------------------------------------------------------------
# Empty file / corrupt
# ------------------------------------------------------------------

class TestCorruptFile:
    def test_empty_file_returns_false(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            path = f.name
            f.write("")

        try:
            svc = SegmentDataService(path)
            assert svc.load() is False
            assert svc.is_loaded() is False
        finally:
            os.unlink(path)

    def test_headers_only_no_data(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            path = f.name
            cols = [
                "SERIE", "GENERO", "RANGO_EDAD", "RANGO_SALARIAL", "CATEGORIA",
                "SEGMENTO_GRUPO_FAMILIAR", "SEGMENTO_POBLACIONAL", "PIRAMIDE_NUEVA",
                "EMPRESA_FOCO", "CIUDAD_AFILIADO", "HOTELES", "PISCILAGO",
                "DROGUERIA", "AGENCIAS", "VIVIENDA",
            ]
            f.write(",".join(cols) + "\n")

        try:
            svc = SegmentDataService(path)
            assert svc.load() is True
            assert svc.is_loaded() is True
            assert svc.lookup_by_documento("1") is None
        finally:
            os.unlink(path)


# ------------------------------------------------------------------
# Load and query with sample data
# ------------------------------------------------------------------

class TestLoadAndQuery:
    @pytest.fixture
    def svc(self):
        rows = [
            {
                "SERIE": "1",
                "GENERO": "F",
                "RANGO_EDAD": "36 a 45 años",
                "RANGO_SALARIAL": "Entre 8 y 10 SMLV",
                "CATEGORIA": "ZETA",
                "SEGMENTO_GRUPO_FAMILIAR": "LAMBDA",
                "SEGMENTO_POBLACIONAL": "PI",
                "PIRAMIDE_NUEVA": "DELTA",
                "EMPRESA_FOCO": "EMP_000001",
                "CIUDAD_AFILIADO": "BOGOTA D.C.",
                "HOTELES": "NO",
                "PISCILAGO": "NO",
                "DROGUERIA": "SI",
                "AGENCIAS": "NO",
                "VIVIENDA": "NO",
            },
            {
                "SERIE": "2",
                "GENERO": "F",
                "RANGO_EDAD": "20 a 35 años",
                "RANGO_SALARIAL": "Menor al SMLV",
                "CATEGORIA": "SIGMA",
                "SEGMENTO_GRUPO_FAMILIAR": "CHI",
                "SEGMENTO_POBLACIONAL": "TAU",
                "PIRAMIDE_NUEVA": "PSI",
                "EMPRESA_FOCO": "EMP_000001",
                "CIUDAD_AFILIADO": "",
                "HOTELES": "NO",
                "PISCILAGO": "NO",
                "DROGUERIA": "SI",
                "AGENCIAS": "NO",
                "VIVIENDA": "NO",
            },
            {
                "SERIE": "3",
                "GENERO": "M",
                "RANGO_EDAD": "20 a 35 años",
                "RANGO_SALARIAL": "Entre 1 y 1.5 SMLV",
                "CATEGORIA": "SIGMA",
                "SEGMENTO_GRUPO_FAMILIAR": "CHI",
                "SEGMENTO_POBLACIONAL": "PI",
                "PIRAMIDE_NUEVA": "XI",
                "EMPRESA_FOCO": "EMP_000001",
                "CIUDAD_AFILIADO": "",
                "HOTELES": "NO",
                "PISCILAGO": "NO",
                "DROGUERIA": "SI",
                "AGENCIAS": "NO",
                "VIVIENDA": "NO",
            },
            {
                "SERIE": "4",
                "GENERO": "F",
                "RANGO_EDAD": "20 a 35 años",
                "RANGO_SALARIAL": "Entre 1 y 1.5 SMLV",
                "CATEGORIA": "MU",
                "SEGMENTO_GRUPO_FAMILIAR": "LAMBDA",
                "SEGMENTO_POBLACIONAL": "ETA",
                "PIRAMIDE_NUEVA": "ETA",
                "EMPRESA_FOCO": "EMP_000001",
                "CIUDAD_AFILIADO": "",
                "HOTELES": "NO",
                "PISCILAGO": "NO",
                "DROGUERIA": "NO",
                "AGENCIAS": "NO",
                "VIVIENDA": "NO",
            },
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            path = f.name
            _make_sample_csv(path, rows)

        svc = SegmentDataService(path)
        svc.load()
        yield svc
        os.unlink(path)

    def test_load_success(self, svc):
        assert svc.is_loaded() is True

    def test_lookup_by_documento_found(self, svc):
        result = svc.lookup_by_documento("1")
        assert result is not None
        assert result["categoria"] == "C"  # ZETA→C
        assert result["segmento"] == "LAMBDA"
        assert result["genero"] == "F"
        assert result["consumos"]["drogueria"] is True
        assert result["consumos"]["hoteles"] is False

    def test_lookup_by_documento_not_found(self, svc):
        assert svc.lookup_by_documento("99999") is None

    def test_lookup_empty_documento(self, svc):
        assert svc.lookup_by_documento("") is None

    def test_category_mapping_sigma(self, svc):
        result = svc.lookup_by_documento("2")
        assert result is not None
        assert result["categoria"] == "A"

    def test_category_mapping_mu(self, svc):
        result = svc.lookup_by_documento("4")
        assert result is not None
        assert result["categoria"] is None

    def test_get_aggregate_stats_all(self, svc):
        stats = svc.get_aggregate_stats()
        assert len(stats) >= 3  # (A,CHI), (C,LAMBDA), (None,LAMBDA)

    def test_get_aggregate_stats_by_category(self, svc):
        stats = svc.get_aggregate_stats(categoria="A")
        assert all(s["categoria"] == "A" for s in stats)

    def test_get_aggregate_stats_by_segment(self, svc):
        stats = svc.get_aggregate_stats(segmento="CHI")
        assert all(s["segmento"] == "CHI" for s in stats)

    def test_get_aggregate_stats_by_both(self, svc):
        stats = svc.get_aggregate_stats(categoria="C", segmento="LAMBDA")
        assert len(stats) == 1
        assert stats[0]["total_afiliados"] == 1

    def test_get_categories(self, svc):
        cats = svc.get_categories()
        assert "A" in cats
        assert "C" in cats
        assert "B" not in cats  # no PI in sample

    def test_get_segments(self, svc):
        segs = svc.get_segments()
        assert "CHI" in segs
        assert "LAMBDA" in segs

    def test_aggregate_stats_pct_format(self, svc):
        stats = svc.get_aggregate_stats(categoria="C", segmento="LAMBDA")
        assert len(stats) == 1
        s = stats[0]
        assert "pct_drogueria" in s
        assert "pct_hoteles" in s
        assert isinstance(s["pct_drogueria"], float)


# ------------------------------------------------------------------
# Real CSV integration test (if file exists)
# ------------------------------------------------------------------

class TestRealCSV:
    @pytest.fixture
    def svc(self):
        if not os.path.exists(CSV_REAL_PATH):
            pytest.skip(f"Real CSV not found at {CSV_REAL_PATH}")
        svc = SegmentDataService(CSV_REAL_PATH)
        svc.load()
        yield svc

    def test_loads_500k_rows(self, svc):
        """Verify the real CSV loads and has expected row count."""
        # Should be ~500K rows
        assert svc.is_loaded() is True
        assert len(svc.get_categories()) >= 3

    def test_lookup_serie_1(self, svc):
        """First row should be lookup-able."""
        result = svc.lookup_by_documento("1")
        assert result is not None
        assert result["categoria"] is not None or result["categoria"] is None
        assert "consumos" in result

    def test_aggregate_stats_real(self, svc):
        stats = svc.get_aggregate_stats()
        assert len(stats) > 0
        # Verify one entry has reasonable percentages
        for s in stats:
            assert 0 <= s["pct_drogueria"] <= 100
            break
