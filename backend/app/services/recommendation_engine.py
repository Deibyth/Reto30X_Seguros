"""Insurance recommendation engine — pure functions, no DB dependency.

Provides deterministic rule-based product matching and pricing for
Colsubsidio insurance products. Used by MCP tools in domain_tools.py.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# PRODUCTS catalog — 7 products, hardcoded
# ──────────────────────────────────────────────

PRODUCTS: dict[str, dict[str, Any]] = {
    "vida": {
        "nombre": "Seguro de Vida",
        "descripcion": "Respaldo económico para beneficiarios en caso de fallecimiento",
        "prima_base": 45_000,
        "cobertura_max": 200_000_000,
        "categoria": "personal",
        "edad_min": 18,
        "edad_max": 70,
    },
    "accidentes": {
        "nombre": "Accidentes Personales",
        "descripcion": "Cobertura completa de accidentes individuales o familiares",
        "prima_base": 25_000,
        "cobertura_max": 50_000_000,
        "categoria": "personal",
        "edad_min": 18,
        "edad_max": 65,
    },
    "viajes": {
        "nombre": "Asistencia Médica Viajes",
        "descripcion": "Emergencias médicas en viajes nacionales e internacionales 24/7",
        "prima_base": 15_000,
        "cobertura_max": 30_000_000,
        "categoria": "personal",
    },
    "mascotas": {
        "nombre": "Seguro Mascotas",
        "descripcion": "Cobertura veterinaria y protección de daños para perros y gatos",
        "prima_base": 30_000,
        "cobertura_max": 5_000_000,
        "categoria": "mascotas",
    },
    "hogar": {
        "nombre": "Seguro Hogar",
        "descripcion": "Protección para vivienda contra daños y siniestros",
        "prima_base": 35_000,
        "cobertura_max": 150_000_000,
        "categoria": "hogar",
    },
    "movilidad": {
        "nombre": "Seguro Movilidad",
        "descripcion": "Cobertura para vehículos: daños, robo, lesiones a terceros",
        "prima_base": 55_000,
        "cobertura_max": 80_000_000,
        "categoria": "movilidad",
    },
    "vida_deudor": {
        "nombre": "Vida Deudor",
        "descripcion": "Protección de deudas en caso de fallecimiento o incapacidad",
        "prima_base": 20_000,
        "cobertura_max": 100_000_000,
        "categoria": "personal",
        "edad_min": 18,
        "edad_max": 70,
    },
}
 
# ──────────────────────────────────────────────
# RULES — 7 deterministic rules
# ──────────────────────────────────────────────
 
RULES: list[tuple[str, Any]] = [
    ("vida", lambda p: p.get("familia_con_hijos") is True and p.get("preocupacion") == "proteger"),
    ("accidentes", lambda p: _edad_in_range(p.get("edad"), 18, 35) and p.get("estado_civil") == "soltero"),
    ("viajes", lambda p: p.get("viaja_frecuentemente") is True),
    ("mascotas", lambda p: p.get("tiene_mascota") is True),
    ("hogar", lambda p: p.get("es_propietario_vivienda") is True),
    ("movilidad", lambda p: p.get("tiene_vehiculo") is not None),
    ("vida_deudor", lambda p: p.get("tiene_deuda_activa") is True),
]

# ──────────────────────────────────────────────
# CONFIDENCE mapping
# ──────────────────────────────────────────────

_RULE_CONFIDENCE: dict[str, str] = {
    "vida": "high",
    "accidentes": "medium",
    "viajes": "high",
    "mascotas": "high",
    "hogar": "high",
    "movilidad": "high",
    "vida_deudor": "high",
}

_RULE_REASONS: dict[str, str] = {
    "vida": "Tiene hijos y le preocupa protegerlos",
    "accidentes": "Perfil joven y soltero, ideal para protección personal",
    "viajes": "Viaja frecuentemente y necesita asistencia médica",
    "mascotas": "Tiene mascota(s) y desea protegerlas",
    "hogar": "Es propietario de vivienda y desea protegerla",
    "movilidad": "Tiene vehículo y desea protegerlo",
    "vida_deudor": "Tiene deuda activa y desea proteger a sus beneficiarios",
}

# ──────────────────────────────────────────────
# COMPOUND RULES — R8-R13
# ──────────────────────────────────────────────

SEGMENTO_LABELS: dict[str | None, str] = {
    "LAMBDA": "Sin grupo familiar",
    "RHO": "Monoparental",
    "EPSILON": "Nuclear",
    "IOTA": "Pareja",
    "CHI": "No especificado",
    "THETA": "No especificado",
    "PI": "No especificado",
    None: "No disponible",
}

SEGMENT_BOOST: dict[str, list[str]] = {
    "LAMBDA": ["vida", "hogar"],
    "RHO": ["vida", "accidentes"],
    "EPSILON": ["vida", "hogar"],
    "IOTA": ["vida", "hogar"],
}

# Each tuple: (categoria, segmento, [product_ids], confidence, reason_template)
# None in categoria/segmento = any match
SEGMENT_RULES: list[tuple[str | None, str | None, list[str], str, str]] = [
    # R8:  A + LAMBDA  → vida, hogar
    ("A", "LAMBDA", ["vida", "hogar"], "medium",
     "Común en afiliados {categoria} con perfil {segmento_label}"),
    # R9:  A + RHO     → vida, accidentes
    ("A", "RHO", ["vida", "accidentes"], "medium",
     "Común en afiliados {categoria} con perfil {segmento_label}"),
    # R10: A + EPSILON → vida, hogar
    ("A", "EPSILON", ["vida", "hogar"], "medium",
     "Común en afiliados {categoria} con perfil {segmento_label}"),
    # R11: B + any     → accidentes, movilidad
    ("B", None, ["accidentes", "movilidad"], "medium",
     "Producto popular en tu categoría de afiliación ({categoria})"),
    # R12: C + any     → all 6 (vida+hogar high, rest medium)
    ("C", None, ["vida", "hogar", "movilidad", "accidentes", "viajes", "mascotas"],
     "mixed",  # special handling in code
     "Cobertura premium disponible para tu categoría ({categoria})"),
    # R13: any + IOTA  → vida, hogar
    (None, "IOTA", ["vida", "hogar"], "medium",
     "Común en afiliados con perfil de {segmento_label}"),
]

# Products whose compound confidence is "high" in R12
_R12_HIGH_PRODUCTS: set[str] = {"vida", "hogar"}

_VALID_CATEGORIAS: set[str] = {"A", "B", "C"}


# ──────────────────────────────────────────────
# MULTIPLIERS
# ──────────────────────────────────────────────

COVERAGE_MULTIPLIERS: dict[str, float] = {
    "basica": 0.8,
    "estandar": 1.0,
    "premium": 1.5,
}

DEDUCIBLES: dict[str, str] = {
    "basica": "$0",
    "estandar": "$0",
    "premium": "$0",
}


def _age_multiplier(edad: int | None, product: dict[str, Any]) -> float:
    """Compute age-based multiplier for a product with edad_min/edad_max.

    Only applies to products that define edad_min/edad_max.
    """
    if edad is None or "edad_min" not in product:
        return 1.0
    if edad <= 30:
        return 1.0
    if edad <= 45:
        return 1.2
    if edad <= 60:
        return 1.5
    return 2.0


def _edad_in_range(edad: Any, min_val: int, max_val: int) -> bool:
    """Check if edad (int or str) falls in [min_val, max_val]."""
    if edad is None:
        return False
    try:
        return min_val <= int(edad) <= max_val
    except (ValueError, TypeError):
        return False


def _cobertura_summary(product_id: str, coverage_level: str) -> str:
    """Generate a human-readable coverage summary string."""
    product = PRODUCTS.get(product_id)
    if not product:
        return "No disponible"
    cobertura_max = product.get("cobertura_max", 0)
    level_label = coverage_level.capitalize()
    return f"Cobertura {level_label}: hasta ${cobertura_max:,} COP".replace(",", ".")


# ──────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────


def match_products(profile: dict) -> list[dict[str, Any]]:
    """Apply all rules against *profile* and return matched products sorted by relevance.

    Returns a list of dicts sorted by confidence (high first) then prima_base descending.
    Empty profile returns ``[]``.
    """
    if not profile:
        return []

    matched: list[dict[str, Any]] = []
    for product_id, rule_fn in RULES:
        if rule_fn(profile):
            product = PRODUCTS[product_id]
            matched.append({
                "product_id": product_id,
                "nombre": product["nombre"],
                "descripcion": product["descripcion"],
                "categoria": product["categoria"],
                "prima_base": product["prima_base"],
                "match_reason": _RULE_REASONS[product_id],
                "confidence": _RULE_CONFIDENCE[product_id],
            })

    # Sort: high confidence first, then prima_base descending
    matched.sort(key=lambda p: (0 if p["confidence"] == "high" else 1, -p["prima_base"]))
    return matched


# ──────────────────────────────────────────────
# COMPOUND MATCHING (R8-R13 + R1-R7 merge)
# ──────────────────────────────────────────────


def _match_compound_rules(
    categoria: str | None,
    segmento: str | None,
) -> dict[str, tuple[str, str]]:
    """Apply SEGMENT_RULES and return ``{product_id: (confidence, reason)}``.

    confidence is "high" or "medium" as determined by compound rules alone.
    """
    compound: dict[str, tuple[str, str]] = {}

    for rule_cat, rule_seg, product_ids, confidence, reason_tpl in SEGMENT_RULES:
        if rule_cat is not None and rule_cat != categoria:
            continue
        if rule_seg is not None and rule_seg != segmento:
            continue

        seg_label = SEGMENTO_LABELS.get(segmento, "No especificado")
        reason = reason_tpl.format(categoria=categoria or "", segmento_label=seg_label).strip()

        for pid in product_ids:
            if confidence == "mixed":
                conf = "high" if pid in _R12_HIGH_PRODUCTS else "medium"
            else:
                conf = confidence

            existing_conf = compound.get(pid, (None, ""))[0]
            if existing_conf == "high":
                continue
            compound[pid] = (conf, reason)

    return compound


def match_products_by_segment(
    profile: dict,
    categoria: str | None = None,
    segmento: str | None = None,
) -> list[dict[str, Any]]:
    """Apply compound rules (R8-R13) + conversational rules (R1-R7).

    Parameters
    ----------
    profile : dict
        Conversational profile (same as match_products).
    categoria : str | None
        One of ``"A"``, ``"B"``, ``"C"``, or None/MU for fallback.
    segmento : str | None
        Family segment label, or None if unknown.

    Returns
    -------
    list[dict]
        Merged, sorted product list. Same schema as ``match_products()``.
    """
    categoria_usable = categoria in _VALID_CATEGORIAS
    should_run_compound = categoria_usable or segmento is not None

    logger.info(
        "match_products_by_segment: categoria=%s, segmento=%s, compound=%s",
        categoria, segmento, should_run_compound,
    )

    conversational = match_products(profile)
    conv_by_id: dict[str, dict[str, Any]] = {p["product_id"]: p for p in conversational}

    if not should_run_compound:
        for p in conversational:
            p["confidence"] = "medium"
            p["match_reason"] = f"{p['match_reason']} (perfil general)"
        conversational.sort(key=lambda p: (0 if p["confidence"] == "high" else 1, -p["prima_base"]))
        return conversational

    compound: dict[str, tuple[str, str]] = _match_compound_rules(categoria, segmento)

    result: dict[str, dict[str, Any]] = {}

    for pid, p in conv_by_id.items():
        entry = dict(p)
        if pid in compound:
            if entry["confidence"] != "high":
                pass
            entry["match_reason"] = f"{entry['match_reason']} y está alineado con tu categoría"
        result[pid] = entry

    for pid, (conf, reason) in compound.items():
        if pid not in result and pid in PRODUCTS:
            product = PRODUCTS[pid]
            result[pid] = {
                "product_id": pid,
                "nombre": product["nombre"],
                "descripcion": product["descripcion"],
                "categoria": product["categoria"],
                "prima_base": product["prima_base"],
                "match_reason": reason,
                "confidence": conf,
            }

    result_list = list(result.values())
    boost_products = SEGMENT_BOOST.get(segmento or "", [])

    def _sort_key(p: dict) -> tuple:
        conf_order = 0 if p["confidence"] == "high" else 1
        boosted = 0 if p["product_id"] in boost_products else 1
        return (conf_order, boosted, -p["prima_base"])

    result_list.sort(key=_sort_key)
    return result_list


def quote_product(
    product_id: str,
    profile: dict,
    coverage_level: str = "estandar",
) -> dict[str, Any]:
    """Compute a personalized quote for the given product and profile.

    Formula: prima_mensual = prima_base * coverage_multiplier * age_multiplier

    Returns a dict with pricing breakdown, or an error dict if the product
    or coverage level is invalid.
    """
    product = PRODUCTS.get(product_id)
    if not product:
        return {"error": "unknown_product"}

    if coverage_level not in COVERAGE_MULTIPLIERS:
        return {"error": "invalid_coverage"}

    prima = product["prima_base"]
    prima *= COVERAGE_MULTIPLIERS[coverage_level]

    edad = profile.get("edad")
    if edad is not None:
        prima *= _age_multiplier(int(edad) if not isinstance(edad, int) else edad, product)

    prima_mensual = round(prima, 0)

    return {
        "product_id": product_id,
        "nombre": product["nombre"],
        "prima_mensual": prima_mensual,
        "prima_anual": prima_mensual * 12,
        "cobertura_resumen": _cobertura_summary(product_id, coverage_level),
        "deducible": DEDUCIBLES.get(coverage_level, "N/A"),
        "vigencia": "Anual renovable",
    }
