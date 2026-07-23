from app.schemas.credit_form import FormSchema, FormField


class TestFormSchema:
    def test_version_exists(self):
        assert FormSchema.VERSION == "1.0"

    def test_total_fields_count(self):
        total = sum(len(s.campos) for s in FormSchema.secciones)
        assert total == 56

    def test_total_secciones_count(self):
        assert len(FormSchema.secciones) == 9

    def test_campos_requeridos(self):
        requeridos = FormSchema.campos_requeridos()
        nombres = {c.nombre for c in requeridos}
        esperados = {
            "tipo_solicitud",
            "valor_solicitado",
            "plazo_meses",
            "primer_apellido",
            "nombres",
            "tipo_identificacion",
            "numero_identificacion",
            "fecha_nacimiento",
            "direccion_residencia",
            "ciudad",
            "celular",
            "email",
            "salario_basico",
            "cuenta_numero",
            "cuenta_tipo",
            "entidad_bancaria",
        }
        assert nombres == esperados
        assert all(c.requerido for c in requeridos)

    def test_campos_opcionales(self):
        opcionales = FormSchema.campos_opcionales()
        assert all(c.requerido is False for c in opcionales)
        assert len(opcionales) == 56 - 16

    def test_campos_desde_customer(self):
        mapping = FormSchema.campos_desde_customer()
        assert mapping["nombres"] == "nombre_completo"
        assert mapping["numero_identificacion"] == "documento_identidad"
        assert mapping["email"] == "email"
        assert mapping["tipo_contrato"] == "tipo_contrato"
        assert mapping["salario_basico"] == "salario"
        assert "ciudad" not in mapping

    def test_to_prompt_text(self):
        text = FormSchema.to_prompt_text()
        assert isinstance(text, str)
        assert "[Producto Solicitado]" in text
        assert "[Datos Personales]" in text
        assert "[Ubicación]" in text
        assert "[Laboral]" in text
        assert "[Financiera]" in text
        assert "[Patrimonio]" in text
        assert "[Cónyuge]" in text
        assert "[Referencias]" in text
        assert "[Desembolso]" in text
        assert "REQ" in text

    def test_to_prompt_text_not_empty(self):
        text = FormSchema.to_prompt_text()
        assert len(text.strip()) > 0

    def test_field_validation_types(self):
        for seccion in FormSchema.secciones:
            for campo in seccion.campos:
                assert campo.tipo in (
                    "string", "number", "date", "email", "select"
                ), f"{campo.nombre} tiene tipo inválido: {campo.tipo}"
