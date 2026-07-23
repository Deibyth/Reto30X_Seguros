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
}

_RULE_REASONS: dict[str, str] = {
    "vida": "Tiene hijos y le preocupa protegerlos",
    "accidentes": "Perfil joven y soltero, ideal para protección personal",
    "viajes": "Viaja frecuentemente y necesita asistencia médica",
    "mascotas": "Tiene mascota(s) y desea protegerlas",
    "hogar": "Es propietario de vivienda y desea protegerla",
    "movilidad": "Tiene vehículo y desea protegerlo",
}

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
