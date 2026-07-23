"""FormSchema — structured definition of the credit application form.

Used by the AI to guide conversational data collection. Each field specifies
its name, type, section, whether required, validation rules, and optional
mapping to Customer columns for pre-filling.
"""

import json
from typing import Literal


class FormField:
    """A single field in the credit application form."""

    def __init__(
        self,
        nombre: str,
        tipo: Literal["string", "number", "date", "email", "select"],
        requerido: bool,
        prompt_question: str,
        seccion: str,
        validaciones: dict | None = None,
        desde_customer: str | None = None,
    ) -> None:
        self.nombre = nombre
        self.tipo = tipo
        self.requerido = requerido
        self.prompt_question = prompt_question
        self.seccion = seccion
        self.validaciones = validaciones
        self.desde_customer = desde_customer

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "tipo": self.tipo,
            "requerido": self.requerido,
            "prompt_question": self.prompt_question,
            "seccion": self.seccion,
            "validaciones": self.validaciones,
            "desde_customer": self.desde_customer,
        }


class FormSeccion:
    """A named section grouping related form fields."""

    def __init__(self, nombre: str, campos: list[FormField]) -> None:
        self.nombre = nombre
        self.campos = campos


class FormSchema:
    """Complete credit application form schema with all sections and fields.

    Usage:
        schema_text = FormSchema.to_prompt_text()
        required = FormSchema.campos_requeridos()
        customer_map = FormSchema.campos_desde_customer()
    """

    VERSION = "1.0"

    secciones: list[FormSeccion] = [
        FormSeccion("Producto Solicitado", [
            FormField("tipo_solicitud", "select", True,
                      "¿Qué tipo de crédito necesitas?",
                      "Producto Solicitado",
                      {"enum": ["Libre Inversión", "Compra Cartera", "Vehículo",
                                "Salud", "Educativo", "Hipotecario", "Otro"]}),
            FormField("valor_solicitado", "number", True,
                      "¿Cuál es el valor que deseas solicitar?",
                      "Producto Solicitado",
                      {"min": 0, "max": 1_000_000_000}),
            FormField("plazo_meses", "number", True,
                      "¿En cuántos meses deseas pagar el crédito?",
                      "Producto Solicitado",
                      {"min": 1, "max": 120}),
            FormField("modalidad_pago", "select", False,
                      "¿Cuál es la modalidad de pago?",
                      "Producto Solicitado",
                      {"enum": ["libranza", "pago_directo"]}),
        ]),
        FormSeccion("Datos Personales", [
            FormField("primer_apellido", "string", True,
                      "¿Cuál es tu primer apellido?",
                      "Datos Personales"),
            FormField("segundo_apellido", "string", False,
                      "¿Cuál es tu segundo apellido?",
                      "Datos Personales"),
            FormField("nombres", "string", True,
                      "¿Cuáles son tus nombres completos?",
                      "Datos Personales",
                      desde_customer="nombre_completo"),
            FormField("tipo_identificacion", "select", True,
                      "¿Cuál es tu tipo de identificación? (CC o CE)",
                      "Datos Personales",
                      {"enum": ["CC", "CE"]}),
            FormField("numero_identificacion", "string", True,
                      "¿Cuál es tu número de identificación?",
                      "Datos Personales",
                      desde_customer="documento_identidad"),
            FormField("fecha_expedicion", "date", False,
                      "¿Cuál es la fecha de expedición de tu documento?",
                      "Datos Personales"),
            FormField("lugar_expedicion", "string", False,
                      "¿En qué lugar fue expedido tu documento?",
                      "Datos Personales"),
            FormField("fecha_nacimiento", "date", True,
                      "¿Cuál es tu fecha de nacimiento?",
                      "Datos Personales"),
            FormField("sexo", "select", False,
                      "¿Cuál es tu sexo? (M o F)",
                      "Datos Personales",
                      {"enum": ["M", "F"]}),
            FormField("estado_civil", "select", False,
                      "¿Cuál es tu estado civil?",
                      "Datos Personales",
                      {"enum": ["Soltero", "Casado", "Divorciado",
                                "Viudo", "Unión Libre"]}),
            FormField("categoria_afiliacion", "select", False,
                      "¿Cuál es tu categoría de afiliación? (A, B o C)",
                      "Datos Personales",
                      {"enum": ["A", "B", "C"]}),
        ]),
        FormSeccion("Ubicación", [
            FormField("direccion_residencia", "string", True,
                      "¿Cuál es tu dirección de residencia?",
                      "Ubicación"),
            FormField("barrio", "string", False,
                      "¿En qué barrio vives?",
                      "Ubicación"),
            FormField("ciudad", "string", True,
                      "¿En qué ciudad vives?",
                      "Ubicación"),
            FormField("estrato", "select", False,
                      "¿Cuál es tu estrato socioeconómico?",
                      "Ubicación",
                      {"enum": ["1", "2", "3", "4", "5", "6"]}),
            FormField("tipo_vivienda", "select", False,
                      "¿Tu vivienda es propia, arrendada o familiar?",
                      "Ubicación",
                      {"enum": ["Propia", "Arrendada", "Familiar"]}),
            FormField("telefono", "string", False,
                      "¿Cuál es tu número de teléfono fijo?",
                      "Ubicación"),
            FormField("celular", "string", True,
                      "¿Cuál es tu número de celular?",
                      "Ubicación"),
            FormField("email", "email", True,
                      "¿Cuál es tu correo electrónico?",
                      "Ubicación",
                      desde_customer="email"),
        ]),
        FormSeccion("Laboral", [
            FormField("nombre_empresa", "string", False,
                      "¿En qué empresa trabajas?",
                      "Laboral"),
            FormField("nit_empresa", "string", False,
                      "¿Cuál es el NIT de la empresa?",
                      "Laboral"),
            FormField("direccion_empresa", "string", False,
                      "¿Cuál es la dirección de la empresa?",
                      "Laboral"),
            FormField("telefono_empresa", "string", False,
                      "¿Cuál es el teléfono de la empresa?",
                      "Laboral"),
            FormField("tipo_contrato", "select", False,
                      "¿Qué tipo de contrato laboral tienes?",
                      "Laboral",
                      {"enum": ["Indefinido", "Temporal",
                                "Prestación Servicios", "Otro"]},
                      desde_customer="tipo_contrato"),
            FormField("cargo", "string", False,
                      "¿Cuál es tu cargo en la empresa?",
                      "Laboral"),
            FormField("fecha_ingreso", "date", False,
                      "¿Desde cuándo trabajas en esa empresa?",
                      "Laboral"),
            FormField("salario_basico", "number", True,
                      "¿Cuál es tu salario básico mensual?",
                      "Laboral",
                      {"min": 0},
                      desde_customer="salario"),
        ]),
        FormSeccion("Financiera", [
            FormField("otros_ingresos", "number", False,
                      "¿Tienes otros ingresos adicionales? ¿De cuánto?",
                      "Financiera",
                      {"min": 0}),
            FormField("gastos_familiares", "number", False,
                      "¿Cuáles son tus gastos familiares mensuales aproximados?",
                      "Financiera",
                      {"min": 0}),
            FormField("valor_arriendo", "number", False,
                      "¿Cuánto pagas de arriendo?",
                      "Financiera",
                      {"min": 0}),
            FormField("cuotas_tarjetas", "number", False,
                      "¿Cuánto pagas mensualmente en cuotas de tarjetas de crédito?",
                      "Financiera",
                      {"min": 0}),
            FormField("total_creditos", "number", False,
                      "¿Cuál es el total de tus créditos actuales?",
                      "Financiera",
                      {"min": 0}),
        ]),
        FormSeccion("Patrimonio", [
            FormField("tipo_inmueble", "select", False,
                      "¿Qué tipo de inmueble posees?",
                      "Patrimonio",
                      {"enum": ["Casa", "Apto", "Lote", "Otro"]}),
            FormField("valor_comercial_inmueble", "number", False,
                      "¿Cuál es el valor comercial de tu inmueble?",
                      "Patrimonio",
                      {"min": 0}),
            FormField("marca_vehiculo", "string", False,
                      "¿Cuál es la marca de tu vehículo?",
                      "Patrimonio"),
            FormField("modelo_vehiculo", "number", False,
                      "¿Cuál es el modelo de tu vehículo?",
                      "Patrimonio"),
            FormField("placa_vehiculo", "string", False,
                      "¿Cuál es la placa de tu vehículo?",
                      "Patrimonio"),
            FormField("valor_comercial_vehiculo", "number", False,
                      "¿Cuál es el valor comercial de tu vehículo?",
                      "Patrimonio",
                      {"min": 0}),
        ]),
        FormSeccion("Cónyuge", [
            FormField("conyuge_nombres", "string", False,
                      "¿Cuáles son los nombres de tu cónyuge?",
                      "Cónyuge"),
            FormField("conyuge_identificacion", "string", False,
                      "¿Cuál es la identificación de tu cónyuge?",
                      "Cónyuge"),
            FormField("conyuge_celular", "string", False,
                      "¿Cuál es el celular de tu cónyuge?",
                      "Cónyuge"),
            FormField("conyuge_trabaja", "select", False,
                      "¿Tu cónyuge trabaja actualmente?",
                      "Cónyuge",
                      {"enum": ["Sí", "No"]}),
            FormField("conyuge_ingresos", "number", False,
                      "¿Cuáles son los ingresos mensuales de tu cónyuge?",
                      "Cónyuge",
                      {"min": 0}),
        ]),
        FormSeccion("Referencias", [
            FormField("ref1_nombre", "string", False,
                      "¿Cuál es el nombre de tu primera referencia personal?",
                      "Referencias"),
            FormField("ref1_telefono", "string", False,
                      "¿Cuál es el teléfono de tu primera referencia?",
                      "Referencias"),
            FormField("ref1_parentesco", "string", False,
                      "¿Qué parentesco tienes con tu primera referencia?",
                      "Referencias"),
            FormField("ref2_nombre", "string", False,
                      "¿Cuál es el nombre de tu segunda referencia personal?",
                      "Referencias"),
            FormField("ref2_telefono", "string", False,
                      "¿Cuál es el teléfono de tu segunda referencia?",
                      "Referencias"),
            FormField("ref2_parentesco", "string", False,
                      "¿Qué parentesco tienes con tu segunda referencia?",
                      "Referencias"),
        ]),
        FormSeccion("Desembolso", [
            FormField("cuenta_numero", "string", True,
                      "¿Cuál es el número de cuenta para el desembolso?",
                      "Desembolso"),
            FormField("cuenta_tipo", "select", True,
                      "¿Tu cuenta es de ahorros o corriente?",
                      "Desembolso",
                      {"enum": ["Ahorros", "Corriente"]}),
            FormField("entidad_bancaria", "string", True,
                      "¿En qué entidad bancaria tienes la cuenta?",
                      "Desembolso"),
        ]),
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
    def campos_desde_customer(cls) -> dict[str, str]:
        """Return mapping of field name → Customer column name.

        Only includes fields that have ``desde_customer`` set.
        """
        mapping: dict[str, str] = {}
        for seccion in cls.secciones:
            for campo in seccion.campos:
                if campo.desde_customer:
                    mapping[campo.nombre] = campo.desde_customer
        return mapping

    @classmethod
    def to_prompt_text(cls) -> str:
        """Serialize the schema to a compact, token-efficient table format.

        Keeps only essential information for the AI: field name, type,
        required/optional, and validations where applicable. Excludes
        prompt_question (the AI already knows how to ask naturally).
        Returns under 3k chars.
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
                        parts2 = []
                        if "min" in v: parts2.append(f"min={v['min']}")
                        if "max" in v: parts2.append(f"max={v['max']}")
                        extra = f" ({', '.join(parts2)})"
                if c.desde_customer:
                    extra += f" ← customer.{c.desde_customer}"
                lines.append(f"  - {c.nombre} ({c.tipo}) [{req}]{extra}")
            lines.append("")
        return "\n".join(lines)
