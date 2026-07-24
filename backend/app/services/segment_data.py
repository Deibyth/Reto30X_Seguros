"""SegmentDataService — loads Colsubsidio affiliate dataset at startup.

Singleton service that provides:
- Lookup by documento_identidad → profile with categoria, segmento, consumos
- Aggregate stats by (categoria, segmento) for conversational context
- Graceful degradation when the CSV file is missing or corrupt
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

CSV_PATH = "Usos_Productos_Afiliados_SIN_ID2.csv"

CATEGORY_MAP: dict[str, str | None] = {
    "SIGMA": "A",
    "PI": "B",
    "ZETA": "C",
    "MU": None,
}

PRODUCT_COLUMNS = ["HOTELES", "PISCILAGO", "DROGUERIA", "AGENCIAS", "VIVIENDA"]

# Type aliases
DocumentoIndex = dict[str, dict[str, Any]]
AggregateKey = tuple[str | None, str | None]
AggregateStats = dict[AggregateKey, dict[str, Any]]


class SegmentDataService:
    """Singleton service that loads the 500K affiliate CSV at startup.

    Usage::

        svc = SegmentDataService.get_instance()
        if svc.is_loaded():
            profile = svc.lookup_by_documento("100000001")
            stats = svc.get_aggregate_stats(categoria="A", segmento="LAMBDA")
    """

    _instance: SegmentDataService | None = None

    def __init__(self, csv_path: str = CSV_PATH) -> None:
        self._csv_path = csv_path
        self._documento_index: DocumentoIndex = {}
        self._aggregate_index: AggregateStats = {}
        self._loaded = False
        self._categories: list[str] = []
        self._segments: list[str] = []

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> SegmentDataService:
        """Return the singleton instance. Raises RuntimeError if not set."""
        if cls._instance is None:
            raise RuntimeError(
                "SegmentDataService not initialized. Call _set_instance() first."
            )
        return cls._instance

    @classmethod
    def _set_instance(cls, instance: SegmentDataService | None) -> None:
        """Set the singleton instance (used during startup and tests)."""
        cls._instance = instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Load the CSV into memory.

        Returns True on success, False if the file is missing or corrupt.
        Logs a warning on failure — never raises.
        """
        try:
            with open(self._csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    logger.warning("SegmentDataService: CSV has no headers")
                    return False

                doc_index: DocumentoIndex = {}
                agg: AggregateStats = defaultdict(
                    lambda: {
                        "total_afiliados": 0,
                        "total_hoteles": 0,
                        "total_piscilago": 0,
                        "total_drogueria": 0,
                        "total_agencias": 0,
                        "total_vivienda": 0,
                    }
                )
                seen_categories: set[str] = set()
                seen_segments: set[str] = set()

                expected_columns = {
                    "SERIE", "CATEGORIA", "SEGMENTO_GRUPO_FAMILIAR", "GENERO",
                    "RANGO_EDAD", "RANGO_SALARIAL",
                } | set(PRODUCT_COLUMNS)
                missing_columns = expected_columns - set(reader.fieldnames or [])
                if missing_columns:
                    logger.warning(
                        "SegmentDataService: CSV missing columns: %s",
                        ", ".join(sorted(missing_columns)),
                    )

                malformed_rows = 0
                row_count = 0
                for row in reader:
                    serie = row.get("SERIE", "").strip()
                    if not serie:
                        continue

                    row_count += 1
                    if row_count % 100_000 == 0:
                        logger.info(
                            "SegmentDataService: loaded %d rows so far...",
                            row_count,
                        )

                    categoria_raw = row.get("CATEGORIA", "").strip().upper()
                    if not row.get("CATEGORIA", "").strip():
                        malformed_rows += 1
                        if malformed_rows <= 5:
                            logger.warning(
                                "SegmentDataService: row %d has missing CATEGORIA (SERIE=%s)",
                                row_count, serie,
                            )

                    categoria = CATEGORY_MAP.get(categoria_raw)

                    segmento = row.get("SEGMENTO_GRUPO_FAMILIAR", "").strip().upper() or None
                    genero = row.get("GENERO", "").strip() or None
                    rango_edad = row.get("RANGO_EDAD", "").strip() or None
                    rango_salarial = row.get("RANGO_SALARIAL", "").strip() or None

                    consumos: dict[str, bool] = {}
                    for col in PRODUCT_COLUMNS:
                        val = row.get(col, "").strip().upper()
                        consumos[col.lower()] = val == "SI"

                    # Index by SERIE as pseudo-documento
                    doc_index[serie] = {
                        "categoria": categoria,
                        "segmento": segmento,
                        "genero": genero,
                        "rango_edad": rango_edad,
                        "rango_salarial": rango_salarial,
                        "consumos": consumos,
                    }

                    # Aggregate stats key
                    agg_key = (categoria, segmento)
                    entry = agg[agg_key]
                    entry["total_afiliados"] += 1
                    for col in PRODUCT_COLUMNS:
                        if consumos[col.lower()]:
                            entry[f"total_{col.lower()}"] += 1

                    if categoria:
                        seen_categories.add(categoria)
                    if segmento:
                        seen_segments.add(segmento)

                self._documento_index = doc_index
                self._aggregate_index = dict(agg)
                self._categories = sorted(seen_categories)
                self._segments = sorted(seen_segments)
                self._loaded = True

                if malformed_rows:
                    logger.warning(
                        "SegmentDataService: %d rows had missing CATEGORIA (total: %d rows)",
                        malformed_rows, row_count,
                    )

                logger.info(
                    "SegmentDataService: loaded %d affiliates in %d rows, %d categories, %d segments",
                    len(doc_index), row_count,
                    len(self._categories),
                    len(self._segments),
                )
                return True

        except FileNotFoundError:
            logger.warning(
                "SegmentDataService: CSV not found at '%s' — running without segment data",
                self._csv_path,
            )
            self._loaded = False
            return False
        except Exception as exc:
            logger.warning(
                "SegmentDataService: failed to load CSV '%s': %s — running without segment data",
                self._csv_path,
                exc,
            )
            self._loaded = False
            return False

    def is_loaded(self) -> bool:
        """Return True if the CSV was loaded successfully."""
        return self._loaded

    def lookup_by_documento(self, documento: str) -> dict[str, Any] | None:
        """Look up an affiliate by document number (SERIE).

        Returns a dict with categoria, segmento, genero, rango_edad,
        rango_salarial, and consumos, or None if not found.
        """
        if not self._loaded or not documento:
            return None
        return self._documento_index.get(documento.strip())

    def get_aggregate_stats(
        self, categoria: str | None = None, segmento: str | None = None
    ) -> list[dict[str, Any]]:
        """Return aggregate stats optionally filtered by category and/or segment.

        Each entry::
            {
                "categoria": "A" | None,
                "segmento": "LAMBDA" | None,
                "total_afiliados": 12345,
                "pct_drogueria": 31.9,
                "pct_hoteles": 0.1,
                ...
            }
        """
        if not self._loaded:
            return []

        results: list[dict[str, Any]] = []
        for (cat, seg), data in self._aggregate_index.items():
            if categoria is not None and cat != categoria:
                continue
            if segmento is not None and seg != segmento:
                continue

            total = data["total_afiliados"]
            entry: dict[str, Any] = {
                "categoria": cat,
                "segmento": seg,
                "total_afiliados": total,
            }
            for col in PRODUCT_COLUMNS:
                col_key = col.lower()
                count = data[f"total_{col_key}"]
                entry[f"pct_{col_key}"] = round(count / total * 100, 1) if total else 0.0

            results.append(entry)

        return results

    def get_categories(self) -> list[str]:
        """Return sorted list of unique category values (A, B, C)."""
        return list(self._categories) if self._loaded else []

    def get_segments(self) -> list[str]:
        """Return sorted list of unique segment values."""
        return list(self._segments) if self._loaded else []
