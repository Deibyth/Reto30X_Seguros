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
# CATALOG PRODUCTS — real Colsubsidio catalog (from catalog.txt)
# ──────────────────────────────────────────────

CATALOG_PRODUCTS: dict[str, dict[str, Any]] = {
    # — Movilidad —
    "movilidad_carro": {
        "nombre": "Seguro de Carro",
        "descripcion": "Cobertura para vehículo particular: daños, robo, lesiones a terceros",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Allianz · Liberty · Sura · AXA Colpatria · Bolívar · Equidad · Mapfre · SBS · Mundial · GEA",
        "prima_base": 65_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/vehiculos/carro",
    },
    "movilidad_bicicleta": {
        "nombre": "Bicicleta y patineta",
        "descripcion": "Cobertura para bicicletas y patinetas eléctricas, con protección contra robo y daños",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Allianz · Liberty · Sura · AXA Colpatria · Bolívar · Equidad · Mapfre · SBS · Mundial · GEA",
        "prima_base": 15_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/vehiculos/carro",
    },
    "movilidad_soat": {
        "nombre": "SOAT",
        "descripcion": "Seguro Obligatorio de Accidentes de Tránsito — obligatorio por ley",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Allianz · Liberty · Sura · AXA Colpatria · Bolívar · Equidad · Mapfre · SBS · Mundial · GEA",
        "prima_base": 0,  # Price depends on vehicle type, not consultive sale
        "canal_venta": "externo",
        "url_compra": "https://www.colsubsidio.com/seguros/vehiculos/soat",
    },
    "movilidad_asistencia_moto": {
        "nombre": "Asistencia moto",
        "descripcion": "Asistencia mecánica y jurídica para motociclistas",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Allianz · Liberty · Sura · AXA Colpatria · Bolívar · Equidad · Mapfre · SBS · Mundial · GEA",
        "prima_base": 25_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/vehiculos/moto",
    },
    # — Mascotas —
    "mascotas_perro_gato": {
        "nombre": "Seguro perro y gato",
        "descripcion": "Cobertura veterinaria integral para perros y gatos",
        "categoria_producto": "Mascotas",
        "aseguradoras": "Sura · HDI · Mundial · GEA · VetPlus",
        "prima_base": 30_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/mascotas/perro-gato",
    },
    "mascotas_asistencias_veterinarias": {
        "nombre": "Asistencias veterinarias",
        "descripcion": "Asistencia veterinaria básica para consultas y emergencias",
        "categoria_producto": "Mascotas",
        "aseguradoras": "Sura · HDI · Mundial · GEA · VetPlus",
        "prima_base": 18_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/mascotas/perro-gato",
    },
    "mascotas_medicina_prepagada": {
        "nombre": "Medicina prepagada (mascota)",
        "descripcion": "Medicina prepagada con cobertura ambulatoria y hospitalaria para mascotas",
        "categoria_producto": "Mascotas",
        "aseguradoras": "Sura · HDI · Mundial · GEA · VetPlus",
        "prima_base": 45_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/mascotas/perro-gato",
    },
    # — Hogar —
    "hogar_contenido": {
        "nombre": "Hogar y contenido",
        "descripcion": "Protección para vivienda y contenido contra daños, robo y siniestros",
        "categoria_producto": "Hogar",
        "aseguradoras": "Allianz · Liberty · Sura · AXA Colpatria · Bolívar · HDI · Mapfre · Estado · BBVA · Mundial",
        "prima_base": 35_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/hogar/contenido",
    },
    "hogar_arrendamiento": {
        "nombre": "Arrendamiento",
        "descripcion": "Protección para inmuebles en arriendo contra daños y siniestros",
        "categoria_producto": "Hogar",
        "aseguradoras": "Allianz · Liberty · Sura · AXA Colpatria · Bolívar · HDI · Mapfre · Estado · BBVA · Mundial",
        "prima_base": 28_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/hogar/arrendamiento",
    },
    # — Personal y familiar —
    "personal_vida": {
        "nombre": "Seguro de Vida",
        "descripcion": "Respaldo económico para beneficiarios en caso de fallecimiento. Incluye auxilio educativo por fallecimiento",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Pan American Life · MetLife · BMI · Chubb · Sura · Allianz",
        "prima_base": 45_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/familiares/vida",
    },
    "personal_vida_ahorro": {
        "nombre": "Vida y ahorro",
        "descripcion": "Seguro de vida con componente de ahorro para protección y futuro financiero",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Pan American Life · MetLife · BMI · Chubb · Sura · Allianz",
        "prima_base": 60_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/familiares/vida-ahorro",
    },
    "personal_accidentes": {
        "nombre": "Accidentes personales",
        "descripcion": "Cobertura completa de accidentes individuales o familiares",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Pan American Life · MetLife · BMI · Chubb · Sura · Allianz",
        "prima_base": 25_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/familiares/accidentes",
    },
    "personal_accidentes_exequial": {
        "nombre": "Accidentes y exequial",
        "descripcion": "Cobertura combinada de accidentes personales y servicios exequiales",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Grupo Recordar · GEA",
        "prima_base": 22_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/personal/vida-exequial/poliza",
    },
    "personal_exequial": {
        "nombre": "Exequial",
        "descripcion": "Servicios exequiales integrales. Extiende cobertura a mascotas",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Grupo Recordar · GEA",
        "prima_base": 12_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/personal/vida-exequial/poliza",
    },
    "personal_salud": {
        "nombre": "Póliza de salud",
        "descripcion": "Póliza integral de salud con cobertura médica, hospitalaria y ambulatoria",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Sura · Allianz · Chubb",
        "prima_base": 80_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/familiares/poliza-salud",
    },
    "personal_asistencias_medicas": {
        "nombre": "Asistencias médicas",
        "descripcion": "Asistencia médica domiciliaria y ambulatoria. Médico a domicilio SOLO en Bogotá",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Sura · Allianz · Mok",
        "prima_base": 20_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/personal/asistencias-multiples",
    },
    "personal_asistencia_viajes": {
        "nombre": "Asistencia en viajes",
        "descripcion": "Emergencias médicas en viajes nacionales e internacionales 24/7",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Chubb · Allianz · Mok",
        "prima_base": 15_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/personal/asistencias-multiples",
    },
    "personal_asistencias_multiples": {
        "nombre": "Asistencias múltiples",
        "descripcion": "Asistencias combinadas: médica, hogar, viajes y jurídica en un solo plan",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Sura · Allianz · Mok",
        "prima_base": 35_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/personal/asistencias-multiples",
    },
    "personal_asesoria_juridica": {
        "nombre": "Asesoría jurídica",
        "descripcion": "Consultoría legal telefónica y presencial con abogados especializados",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Legalcy",
        "prima_base": 10_000,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros",
    },
    # — Crédito —
    "credito_vida_deudor": {
        "nombre": "Vida deudor",
        "descripcion": "Protección de deudas en caso de fallecimiento o incapacidad. SOLO dentro de un crédito",
        "categoria_producto": "Crédito",
        "aseguradoras": "Pan American Life · Sura",
        "prima_base": 20_000,
        "solo_en_credito": True,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/deudores-financieros/vida",
    },
    "credito_desempleo": {
        "nombre": "Desempleo",
        "descripcion": "Cobertura de cuotas de crédito en caso de desempleo involuntario. SOLO dentro de un crédito",
        "categoria_producto": "Crédito",
        "aseguradoras": "Pan American Life · Sura",
        "prima_base": 15_000,
        "solo_en_credito": True,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/creditos",
    },
    "credito_incendio": {
        "nombre": "Incendio",
        "descripcion": "Protección contra incendios para bienes asegurados. SOLO dentro de un crédito",
        "categoria_producto": "Crédito",
        "aseguradoras": "Pan American Life · Sura",
        "prima_base": 10_000,
        "solo_en_credito": True,
        "canal_venta": "colsubsidio",
        "url_compra": "https://www.colsubsidio.com/seguros/creditos",
    },
    # — Externos: Allianz —
    "ext_allianz_autos": {
        "nombre": "Seguro Autos Allianz",
        "descripcion": "Seguro todo riesgo para vehículos con Allianz",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Allianz",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://allianzdigital.co/cotizar",
    },
    "ext_allianz_hogar": {
        "nombre": "Seguro Hogar Allianz",
        "descripcion": "Protección para hogar y contenido con Allianz",
        "categoria_producto": "Hogar",
        "aseguradoras": "Allianz",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://allianzdigital.co/cotizar-hogar",
    },
    # — Externos: HDI (ex-Liberty) —
    "ext_hdi_autos": {
        "nombre": "Seguro Autos HDI",
        "descripcion": "Seguro vehicular con HDI Seguros (antes Liberty)",
        "categoria_producto": "Movilidad",
        "aseguradoras": "HDI (ex-Liberty)",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://tuseguro.hdiseguros.com.co/",
    },
    # — Externos: SURA —
    "ext_sura_soat": {
        "nombre": "SOAT SURA",
        "descripcion": "Seguro Obligatorio de Accidentes de Tránsito con SURA",
        "categoria_producto": "Movilidad",
        "aseguradoras": "SURA",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://www.sura.co/seguros/personas/movilidad/soat",
    },
    "ext_sura_autos": {
        "nombre": "Seguro Autos Digital SURA",
        "descripcion": "Seguro de autos 100% digital con SURA",
        "categoria_producto": "Movilidad",
        "aseguradoras": "SURA",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://www.sura.co/seguros/personas/movilidad/autos/digital",
    },
    # — Externos: AXA Colpatria —
    "ext_axa_autos": {
        "nombre": "Seguro Autos AXA Colpatria",
        "descripcion": "Seguro vehicular digital con AXA Colpatria",
        "categoria_producto": "Movilidad",
        "aseguradoras": "AXA Colpatria",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://digital.axacolpatria.co/seguro-de-autos",
    },
    "ext_axa_salud": {
        "nombre": "Póliza de Salud AXA Colpatria",
        "descripcion": "Póliza de salud integral con AXA Colpatria",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "AXA Colpatria",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://online.axacolpatria.co/salud",
    },
    # — Externos: Seguros Bolívar —
    "ext_bolivar_autos": {
        "nombre": "Seguro Autos Digital Bolívar",
        "descripcion": "Seguro de autos digital con Seguros Bolívar",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Seguros Bolívar",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://www.segurosbolivar.com/seguros-en-linea/seguro-autos-digital/",
    },
    # — Externos: La Equidad —
    "ext_equidad_mascotas": {
        "nombre": "Seguro Mascotas La Equidad",
        "descripcion": "Seguro para mascotas con La Equidad Seguros",
        "categoria_producto": "Mascotas",
        "aseguradoras": "La Equidad",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://servicios.laequidadseguros.coop/store/seguro/mascotas",
    },
    # — Externos: Mapfre —
    "ext_mapfre_autos": {
        "nombre": "Seguro Autos Todo Riesgo Mapfre",
        "descripcion": "Seguro todo riesgo vehicular con Mapfre",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Mapfre",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://digital.mapfre.com.co/iModelWeb/vista/autoscme/autoscmeinicio.jsf",
    },
    # — Externos: Seguros Mundial —
    "ext_mundial_soat": {
        "nombre": "SOAT Seguros Mundial",
        "descripcion": "SOAT con Seguros Mundial — compra 100% en línea",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Seguros Mundial",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://www.soatmundial.com.co",
    },
    # — Externos: Seguros del Estado —
    "ext_estado_soat": {
        "nombre": "SOAT Seguros del Estado",
        "descripcion": "SOAT con Seguros del Estado — compra en línea",
        "categoria_producto": "Movilidad",
        "aseguradoras": "Seguros del Estado",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://www.segurosdelestado.com/productos/productos/1107",
    },
    # — Externos: Pan American Life —
    "ext_palig_vida": {
        "nombre": "Seguro de Vida Pan American Life",
        "descripcion": "Seguro de vida con Pan American Life — cotización en línea",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "Pan American Life",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://paligdirect.com/Quote/Life",
    },
    # — Externos: BMI Seguros —
    "ext_bmi_vida_ahorro": {
        "nombre": "Vida con Ahorro BMI",
        "descripcion": "Seguro de vida con componente de ahorro — BMI Seguros",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "BMI Seguros",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://www.bmiahorro.com.co/seguro-vida/",
    },
    # — Externos: GEA Internacional —
    "ext_gea_asistencias": {
        "nombre": "Asistencias GEA Internacional",
        "descripcion": "Asistencias múltiples con GEA Internacional — alianza Colsubsidio",
        "categoria_producto": "Personal y familiar",
        "aseguradoras": "GEA Internacional",
        "prima_base": 0,
        "canal_venta": "externo",
        "url_compra": "https://colsubsidio.geainternacional.com/",
    },
}

# CATALOG_RULES: (product_id, [allowed_segmentos_vida], confidence, reason_template, restriccion)
# segmento None = todos los segmentos; restriccion None = sin restricción adicional
CATALOG_RULES: list[tuple[str, list[str | None], str, str, str | None]] = [
    # — Movilidad —
    ("movilidad_carro",        ["03"],        "medium", "Indicado para {segmento_label}", None),
    ("movilidad_bicicleta",    ["01"],        "medium", "Ideal para perfil {segmento_label}", "Requiere número de serie visible del vehículo"),
    ("movilidad_soat",         [None],        "low",   "Obligatorio por ley — no es venta consultiva", None),
    ("movilidad_asistencia_moto", ["01"],     "medium", "Recomendado para {segmento_label}", None),
    # — Mascotas —
    ("mascotas_perro_gato",    ["01"],        "high",  "Perfecto para {segmento_label} con mascota", "Cubre ÚNICAMENTE perros y gatos"),
    ("mascotas_asistencias_veterinarias", ["01", "04"], "medium", "Útil para {segmento_label} con mascota", None),
    ("mascotas_medicina_prepagada", ["01"],  "medium", "Pensado para {segmento_label}", None),
    # — Hogar —
    ("hogar_contenido",        ["03"],        "high",  "Esencial para {segmento_label}", None),
    ("hogar_arrendamiento",    ["03"],        "medium", "Protección para {segmento_label} arrendador", "NO ofrecer como propietario al segmento 01"),
    # — Personal y familiar —
    ("personal_vida",          ["02"],        "high",  "Fundamental para {segmento_label}", "NO ofrecer a 01 Joven solo: sin dependientes no protege a nadie"),
    ("personal_vida_ahorro",   ["03"],        "medium", "Ideal para {segmento_label} con visión de futuro", None),
    ("personal_accidentes",    ["01", "02", "05"], "high", "Recomendado para {segmento_label}", None),
    ("personal_accidentes_exequial", ["02", "04"], "medium", "Cobertura combinada para {segmento_label}", None),
    ("personal_exequial",      ["02", "04"],  "medium", "Tranquilidad para {segmento_label}", "Extiende cobertura a mascotas. NO ofrecer a 01 Joven solo"),
    ("personal_salud",         ["02", "03", "04", "05"], "high", "Póliza integral para {segmento_label}", None),
    ("personal_asistencias_medicas", ["04"],  "medium", "Pensado para {segmento_label}", "Médico a domicilio SOLO en Bogotá. Ciudad falta en 58·3% de la base — preguntar antes de prometer"),
    ("personal_asistencia_viajes", [None],    "low",   "No es prioritario por segmento", None),
    ("personal_asistencias_multiples", ["01", "03", "05"], "medium", "Multiasistencias para {segmento_label}", None),
    ("personal_asesoria_juridica", [None],    "low",   "Disponible para todos los afiliados", None),
    # — Crédito —
    ("credito_vida_deudor",    ["01", "02", "03", "04", "05"], "medium",
     "Protección dentro de crédito educativo", "NO se vende suelto: va DENTRO de un crédito"),
    ("credito_desempleo",      ["01", "02", "03", "04", "05"], "medium",
     "Protección dentro de crédito educativo", "NO se vende suelto: va DENTRO de un crédito"),
    ("credito_incendio",       ["01", "02", "03", "04", "05"], "medium",
     "Protección dentro de crédito educativo", "NO se vende suelto: va DENTRO de un crédito"),
    # — Externos: alternativas para que Anna ofrezca con link —
    ("ext_allianz_autos",      ["01", "03"],  "low", "Alternativa externa para {segmento_label}", None),
    ("ext_hdi_autos",          ["01", "03"],  "low", "Alternativa externa para {segmento_label}", None),
    ("ext_sura_autos",         ["01", "03"],  "low", "Alternativa externa para {segmento_label}", None),
    ("ext_sura_soat",          [None],        "low", "SOAT disponible en línea con SURA", None),
    ("ext_axa_autos",          ["01", "03"],  "low", "Alternativa externa para {segmento_label}", None),
    ("ext_axa_salud",          ["02", "03", "04"], "low", "Alternativa externa para {segmento_label}", None),
    ("ext_bolivar_autos",      ["01", "03"],  "low", "Alternativa externa para {segmento_label}", None),
    ("ext_equidad_mascotas",   ["01"],        "low", "Alternativa externa para {segmento_label}", None),
    ("ext_mapfre_autos",       ["01", "03"],  "low", "Alternativa externa para {segmento_label}", None),
    ("ext_mundial_soat",       [None],        "low", "SOAT en línea con Seguros Mundial", None),
    ("ext_estado_soat",        [None],        "low", "SOAT en línea con Seguros del Estado", None),
    ("ext_palig_vida",         ["02", "03"],  "low", "Alternativa externa para {segmento_label}", None),
    ("ext_bmi_vida_ahorro",    ["03"],        "low", "Alternativa externa para {segmento_label}", None),
    ("ext_allianz_hogar",      ["03"],        "low", "Alternativa externa para {segmento_label}", None),
    ("ext_gea_asistencias",    [None],        "low", "Asistencias alianza Colsubsidio–GEA", None),
]

SEGMENTO_VIDA_LABELS: dict[str | None, str] = {
    "01": "Joven solo",
    "02": "Cabeza de familia",
    "03": "Hogar consolidado",
    "04": "Adulto mayor",
    "05": "Independiente",
    None: "No especificado",
}


def derive_segmento_vida(profile: dict) -> str | None:
    """Derive life-stage segment (01-05) from conversational profile and DB data.

    Heuristic priority:
    1.  60+                           → 04 Adulto mayor
    2.  Tipo contrato independiente   → 05 Independiente
    3.  Tiene hijos                   → 02 Cabeza de familia
    4.  Edad < 35, soltero, no hijos  → 01 Joven solo
    5.  Propietario, edad >= 35       → 03 Hogar consolidado
    6.  Fallback                       → None
    """
    if not profile:
        return None

    edad = profile.get("edad")
    try:
        edad = int(edad) if edad is not None else None
    except (ValueError, TypeError):
        edad = None

    tipo_contrato = (profile.get("tipo_contrato") or "").lower()
    estado_civil = (profile.get("estado_civil") or "").lower()
    familia_con_hijos = profile.get("familia_con_hijos") is True
    es_propietario = profile.get("es_propietario_vivienda") is True

    # 04 Adulto mayor
    if edad is not None and edad >= 60:
        return "04"

    # 05 Independiente
    if any(kw in tipo_contrato for kw in ("independiente", "prestación", "freelance", "honorarios")):
        return "05"

    # 02 Cabeza de familia
    if familia_con_hijos:
        return "02"

    # 01 Joven solo
    if edad is not None and edad < 35 and estado_civil in ("soltero", "soltera", ""):
        return "01"

    # 03 Hogar consolidado
    if edad is not None and edad >= 35 and es_propietario:
        return "03"

    return None


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
# MULTIPLIERS
# ──────────────────────────────────────────────

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
                "canal_venta": "colsubsidio",
                "url_compra": product.get("url_compra", "https://www.colsubsidio.com/seguros"),
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
        # Check categoria match
        if rule_cat is not None and rule_cat != categoria:
            continue
        # Check segmento match
        if rule_seg is not None and rule_seg != segmento:
            continue

        seg_label = SEGMENTO_LABELS.get(segmento, "No especificado")
        reason = reason_tpl.format(categoria=categoria or "", segmento_label=seg_label).strip()

        for pid in product_ids:
            # Determine compound-level confidence
            if confidence == "mixed":
                # R12 special case
                conf = "high" if pid in _R12_HIGH_PRODUCTS else "medium"
            else:
                conf = confidence

            # Keep highest confidence from compound rules
            existing_conf = compound.get(pid, (None, ""))[0]
            if existing_conf == "high":
                continue  # already high
            compound[pid] = (conf, reason)

    return compound


def _match_catalog_rules(
    segmento_vida: str | None,
    en_credito: bool = False,
) -> dict[str, tuple[str, str, dict[str, Any]]]:
    """Apply CATALOG_RULES and return ``{product_id: (confidence, reason, product_info)}``.

    ``product_info`` includes the aseguradoras string and any restrictions.
    Credit products are only included when ``en_credito=True``.
    """
    catalog_matches: dict[str, tuple[str, str, dict[str, Any]]] = {}

    for pid, allowed_segs, confidence, reason_tpl, restriccion in CATALOG_RULES:
        product = CATALOG_PRODUCTS.get(pid)
        if not product:
            continue

        # Skip credit products unless in credit context
        if product.get("solo_en_credito") and not en_credito:
            continue

        # Check segmento_vida match
        seg_match = segmento_vida in allowed_segs if segmento_vida else (None in allowed_segs)

        if not seg_match:
            # If no specific segment matches, check if None (all) is allowed
            if None not in allowed_segs:
                continue
            # None means "all", but only if profile has no specific segmento_vida
            # If profile has a segmento_vida, only match if it's in allowed_segs
            if segmento_vida is not None:
                continue

        seg_label = SEGMENTO_VIDA_LABELS.get(segmento_vida, "No especificado")
        reason = reason_tpl.format(segmento_label=seg_label)

        info = {
            "aseguradoras": product.get("aseguradoras", ""),
            "categoria_producto": product.get("categoria_producto", ""),
            "canal_venta": product.get("canal_venta", "colsubsidio"),
            "url_compra": product.get("url_compra", ""),
        }
        if restriccion:
            info["restriccion"] = restriccion

        catalog_matches[pid] = (confidence, reason, info)

    return catalog_matches


def match_products_by_segment(
    profile: dict,
    categoria: str | None = None,
    segmento: str | None = None,
    *,
    segmento_vida: str | None = None,
    en_credito: bool = False,
) -> list[dict[str, Any]]:
    """Apply compound rules (R8-R13) + conversational rules (R1-R7) + catalog rules.

    Parameters
    ----------
    profile : dict
        Conversational profile (same as match_products).
    categoria : str | None
        One of ``"A"``, ``"B"``, ``"C"``, or None/MU for fallback.
    segmento : str | None
        Family segment label, or None if unknown.
    segmento_vida : str | None
        Life-stage segment (01-05) derived from profile, or None.
    en_credito : bool
        Whether the user is in a credit application flow (enables credit products).

    Returns
    -------
    list[dict]
        Merged, sorted product list with catalog info where available.
    """
    # 1. Determine if we should run compound rules
    categoria_usable = categoria in _VALID_CATEGORIAS
    should_run_compound = categoria_usable or segmento is not None

    logger.info(
        "match_products_by_segment: categoria=%s, segmento=%s, segmento_vida=%s, en_credito=%s",
        categoria, segmento, segmento_vida, en_credito,
    )

    # 2. Always run conversational R1-R7
    conversational = match_products(profile)
    conv_by_id: dict[str, dict[str, Any]] = {p["product_id"]: p for p in conversational}

    if not should_run_compound:
        # Fallback: R1-R7 only, all confidence → medium, append "(perfil general)"
        for p in conversational:
            p["confidence"] = "medium"
            p["match_reason"] = f"{p['match_reason']} (perfil general)"
        conversational.sort(key=lambda p: (0 if p["confidence"] == "high" else 1, -p["prima_base"]))

        # 2b. Still run catalog matching for segmento_vida
        if segmento_vida:
            catalog = _match_catalog_rules(segmento_vida, en_credito)
            if catalog:
                result_list = _merge_catalog_with_conversational(conversational, catalog, profile)
                return result_list
        return conversational

    # 3. Run compound rules
    compound: dict[str, tuple[str, str]] = _match_compound_rules(categoria, segmento)

    # 4. Merge conversational + compound
    result: dict[str, dict[str, Any]] = {}

    # Conversational products first
    for pid, p in conv_by_id.items():
        entry = dict(p)  # copy
        if pid in compound:
            # Overlap: keep conversational confidence (high), append alignment reason
            if entry["confidence"] != "high":
                # Conversational medium + compound medium = medium
                pass
            entry["match_reason"] = f"{entry['match_reason']} y está alineado con tu categoría"
        # else: conversational-only, keep as-is
        result[pid] = entry

    # Compound-only products
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
                "canal_venta": "colsubsidio",
                "url_compra": product.get("url_compra", "https://www.colsubsidio.com/seguros"),
            }

    # 5. Add catalog products via segmento_vida
    if segmento_vida:
        catalog = _match_catalog_rules(segmento_vida, en_credito)
        for pid, (conf, reason, info) in catalog.items():
            if pid not in result:
                # New catalog product
                product = CATALOG_PRODUCTS[pid]
                result[pid] = {
                    "product_id": pid,
                    "nombre": product["nombre"],
                    "descripcion": product["descripcion"],
                    "categoria": product.get("categoria_producto", ""),
                    "prima_base": product.get("prima_base", 0),
                    "match_reason": reason,
                    "confidence": conf,
                    "aseguradoras": info["aseguradoras"],
                    "canal_venta": info.get("canal_venta", "colsubsidio"),
                    "url_compra": info.get("url_compra", ""),
                }
                if "restriccion" in info:
                    result[pid]["restriccion"] = info["restriccion"]

    # 6. Segment boost reorder
    result_list = list(result.values())
    boost_products = SEGMENT_BOOST.get(segmento or "", [])

    def _sort_key(p: dict) -> tuple:
        conf_order = 0 if p["confidence"] == "high" else 1
        boosted = 0 if p["product_id"] in boost_products else 1
        return (conf_order, boosted, -p["prima_base"])

    result_list.sort(key=_sort_key)
    return result_list


def _merge_catalog_with_conversational(
    conversational: list[dict[str, Any]],
    catalog: dict[str, tuple[str, str, dict[str, Any]]],
    profile: dict,
) -> list[dict[str, Any]]:
    """Merge catalog products into conversational-only results."""
    result_by_id: dict[str, dict[str, Any]] = {p["product_id"]: p for p in conversational}

    for pid, (conf, reason, info) in catalog.items():
        if pid not in result_by_id:
            product = CATALOG_PRODUCTS[pid]
            result_by_id[pid] = {
                "product_id": pid,
                "nombre": product["nombre"],
                "descripcion": product["descripcion"],
                "categoria": product.get("categoria_producto", ""),
                "prima_base": product.get("prima_base", 0),
                "match_reason": reason,
                "confidence": conf,
                "aseguradoras": info["aseguradoras"],
                "canal_venta": info.get("canal_venta", "colsubsidio"),
                "url_compra": info.get("url_compra", ""),
            }
            if "restriccion" in info:
                result_by_id[pid]["restriccion"] = info["restriccion"]
        # If PID overlaps with conversational, keep conversational as-is (already added)

    return list(result_by_id.values())


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
