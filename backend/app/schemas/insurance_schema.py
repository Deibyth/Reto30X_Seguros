"""InsuranceFormSchema — structured definition of the insurance policy form.

Follows the same pattern as credit_form.py. The AI uses this schema to
collect policy holder data, coverage selections, beneficiary info, and
payment method before policy creation.

Product-specific field variants adapt suma_asegurada ranges and
tipo_cobertura options per product.
"""

import json
from typing import Literal


class FormField:
    """A single field in the insurance application form."""

    def __init__(
        self,
        nombre: str,
        tipo: Literal["string", "number", "date", "email", "select", "boolean", "text"],
        requerido: bool,
        prompt_question: str,
        seccion: str,
        validaciones: dict | None = None,
        options: list[str] | None = None,
    ) -> None:
        self.nombre = nombre
        self.tipo = tipo
        self.requerido = requerido
        self.prompt_question = prompt_question
        self.seccion = seccion
        self.validaciones = validaciones
        self.options = options

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "tipo": self.tipo,
            "requerido": self.requerido,
            "prompt_question": self.prompt_question,
            "seccion": self.seccion,
            "validaciones": self.validaciones,
            "options": self.options,
        }


class FormSeccion:
    """A named section grouping related form fields."""

    def __init__(self, nombre: str, campos: list[FormField]) -> None:
        self.nombre = nombre
        self.campos = campos


# Product-specific field variants.
#
# Each entry defines how suma_asegurada ranges and tipo_cobertura enums
# differ per product. Also controls whether the Beneficiario section is
# shown (has_beneficiario).
PRODUCT_FIELD_VARIANTS: dict[str, dict] = {
    "vida": {
        "suma_asegurada": {"min": 10_000_000, "max": 200_000_000},
        "tipo_cobertura": {
            "enum": [
                "Fallecimiento",
                "Fallecimiento + Incapacidad",
                "Fallecimiento + Enfermedades Graves",
            ],
        },
        "has_beneficiario": True,
    },
    "accidentes": {
        "suma_asegurada": {"min": 1_000_000, "max": 50_000_000},
        "tipo_cobertura": {
            "enum": [
                "Fallecimiento Accidental",
                "Incapacidad Total",
                "Cobertura Médica",
            ],
        },
        "has_beneficiario": False,
    },
    "viajes": {
        "suma_asegurada": {"min": 1_000_000, "max": 30_000_000},
        "tipo_cobertura": {
            "enum": [
                "Básica",
                "Ejecutiva",
                "Full",
            ],
        },
        "has_beneficiario": False,
    },
    "mascotas": {
        "suma_asegurada": {"min": 500_000, "max": 5_000_000},
        "tipo_cobertura": {
            "enum": [
                "Básica",
                "Completa",
            ],
        },
        "has_beneficiario": False,
    },
    "hogar": {
        "suma_asegurada": {"min": 20_000_000, "max": 150_000_000},
        "tipo_cobertura": {
            "enum": [
                "Básica",
                "Amplia",
                "Todo Riesgo",
            ],
        },
        "has_beneficiario": False,
    },
    "movilidad": {
        "suma_asegurada": {"min": 5_000_000, "max": 80_000_000},
        "tipo_cobertura": {
            "enum": [
                "Responsabilidad Civil",
                "Todo Riesgo",
                "Protección Total",
            ],
        },
        "has_beneficiario": False,
    },
}

# All insurance products use the same base fields per section
SECTION_TOMADOR = FormSeccion("Datos del Tomador", [
    FormField("nombre", "string", True,
              "¿Cuál es tu nombre completo? (como figura en el documento)",
              "Datos del Tomador"),
    FormField("documento", "string", True,
              "¿Cuál es tu número de documento de identidad?",
              "Datos del Tomador"),
    FormField("email", "email", True,
              "¿Cuál es tu correo electrónico?",
              "Datos del Tomador"),
    FormField("telefono", "string", True,
              "¿Cuál es tu número de teléfono celular?",
              "Datos del Tomador"),
    FormField("fecha_nacimiento", "date", True,
              "¿Cuál es tu fecha de nacimiento?",
              "Datos del Tomador"),
])

SECTION_COBERTURA = FormSeccion("Cobertura", [
    FormField("tipo_cobertura", "select", True,
              "¿Qué tipo de cobertura necesitas?",
              "Cobertura",
              options=[
                  "Fallecimiento",
                  "Fallecimiento + Incapacidad",
                  "Básica",
              ]),
    FormField("suma_asegurada", "number", True,
              "¿Cuál es el monto que quieres asegurar?",
              "Cobertura",
              validaciones={"min": 500_000, "max": 200_000_000}),
    FormField("coberturas_adicionales", "text", False,
              "¿Quieres incluir coberturas adicionales? Describe cuáles.",
              "Cobertura"),
])

SECTION_BENEFICIARIO = FormSeccion("Beneficiario", [
    FormField("beneficiario_nombre", "string", True,
              "¿Quién será el beneficiario del seguro? (nombre completo)",
              "Beneficiario"),
    FormField("beneficiario_parentesco", "select", False,
              "¿Qué parentesco tienes con el beneficiario?",
              "Beneficiario",
              options=["Cónyuge", "Hijo/a", "Padre", "Madre", "Hermano/a", "Otro"]),
])

SECTION_PAGO = FormSeccion("Pago", [
    FormField("forma_pago", "select", True,
              "¿Cómo quieres pagar la prima?",
              "Pago",
              options=["Mensual", "Trimestral", "Semestral", "Anual", "Único"]),
    FormField("cuenta_pago", "string", False,
              "¿Cuál es el número de cuenta para el débito?",
              "Pago"),
    FormField("acepta_terminos", "boolean", True,
              "¿Aceptas los términos y condiciones del seguro?",
              "Pago"),
    FormField("acepta_tratamiento_datos", "boolean", True,
              "Autorización de tratamiento de datos personales (Ley 1581 de 2012)",
              "Pago"),
])


class InsuranceFormSchema:
    """Complete insurance policy form schema with all sections and fields.

    Usage:
        schema_text = InsuranceFormSchema.to_prompt_text()
        required = InsuranceFormSchema.campos_requeridos()
        variants = InsuranceFormSchema.product_variants(product_id)
    """

    VERSION = "1.0"

    secciones: list[FormSeccion] = [
        SECTION_TOMADOR,
        SECTION_COBERTURA,
        SECTION_BENEFICIARIO,
        SECTION_PAGO,
    ]

    @classmethod
    def campos_requeridos(cls) -> list[FormField]:
        """Return only fields where ``requerido=True``."""
        result: list[FormField] = []
        for seccion in cls.secciones:
            for campo in seccion.campos:
                if campo.requerido:
                    result.append(campo)
        return result

    @classmethod
    def campos_opcionales(cls) -> list[FormField]:
        """Return only fields where ``requerido=False``."""
        result: list[FormField] = []
        for seccion in cls.secciones:
            for campo in seccion.campos:
                if not campo.requerido:
                    result.append(campo)
        return result

    @classmethod
    def product_variants(cls, product_id: str) -> dict:
        """Return field variants for a specific product, or defaults."""
        return PRODUCT_FIELD_VARIANTS.get(product_id, {})

    @classmethod
    def to_prompt_text(cls) -> str:
        """Serialize the schema to a compact, token-efficient table format.

        Includes field name, type, required/optional, and validation hints.
        Returns under 2k chars.
        """
        lines: list[str] = []
        for seccion in cls.secciones:
            lines.append(f"[{seccion.nombre}]")
            for c in seccion.campos:
                req = "REQ" if c.requerido else "opt"
                extra = ""
                if c.validaciones:
                    v = c.validaciones
                    if "enum" in v:
                        extra = f" ({', '.join(v['enum'])})"
                    elif "min" in v or "max" in v:
                        parts = []
                        if "min" in v:
                            parts.append(f"min={v['min']}")
                        if "max" in v:
                            parts.append(f"max={v['max']}")
                        extra = f" ({', '.join(parts)})"
                if c.options:
                    extra = f" ({', '.join(c.options)})"
                lines.append(f"  - {c.nombre} ({c.tipo}) [{req}]{extra}")
            lines.append("")
        return "\n".join(lines)
