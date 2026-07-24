"""Tests for InsuranceFormSchema and data model extensions.

Phase 1 of the insurance conversational flow includes:
- Session model insurance_profile JSON field
- Insurance model insurance_category String field
- InsuranceFormSchema with 4 sections, product variants, conditional beneficiary
"""

import pytest
from sqlalchemy import select

from app.models.session import Session
from app.models.insurance import Insurance
from app.schemas.insurance_schema import InsuranceFormSchema, FormField, PRODUCT_FIELD_VARIANTS


# ──────────────────────────────────────────────
# Task 1.1 — Session.insurance_profile field
# ──────────────────────────────────────────────


class TestSessionInsuranceProfile:
    """Insurance profile JSON field on Session model."""

    async def test_insurance_profile_column_exists(self, db_session):
        """Session model has insurance_profile JSON column defaulting to None."""
        session = Session(
            id="test-ins-profile",
            estado_actual="perfilando",
            campos_diligenciados={},
            activa=True,
            insurance_profile=None,
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert hasattr(session, "insurance_profile")
        assert session.insurance_profile is None

    async def test_insurance_profile_stores_dict(self, db_session):
        """JSON dict is stored and retrievable."""
        profile = {"edad": 35, "familia_con_hijos": True}
        session = Session(
            id="test-ins-profile-2",
            estado_actual="perfilando",
            campos_diligenciados={},
            activa=True,
            insurance_profile=profile,
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert session.insurance_profile == profile
        assert session.insurance_profile["edad"] == 35
        assert session.insurance_profile["familia_con_hijos"] is True


# ──────────────────────────────────────────────
# Task 1.2 — Insurance.insurance_category field
# ──────────────────────────────────────────────


class TestInsuranceCategory:
    """Insurance category String column on Insurance model."""

    async def test_insurance_category_column_exists(self, db_session):
        """Insurance model has insurance_category nullable column."""
        ins = Insurance(
            nombre="Seguro de Vida",
            insurance_category=None,
        )
        db_session.add(ins)
        await db_session.commit()
        await db_session.refresh(ins)

        assert hasattr(ins, "insurance_category")
        assert ins.insurance_category is None

    async def test_insurance_category_stores_value(self, db_session):
        """String category value is stored and retrievable."""
        ins = Insurance(
            nombre="Seguro Hogar",
            insurance_category="hogar",
        )
        db_session.add(ins)
        await db_session.commit()
        await db_session.refresh(ins)

        assert ins.insurance_category == "hogar"

    async def test_insurance_category_queryable(self, db_session):
        """Can filter insurance by category."""
        for cat in ("personal", "hogar", "movilidad", "mascotas", "credito"):
            db_session.add(Insurance(
                nombre=f"Insurance {cat}",
                insurance_category=cat,
            ))
        await db_session.commit()

        result = await db_session.execute(
            select(Insurance).where(Insurance.insurance_category == "hogar")
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].insurance_category == "hogar"


# ──────────────────────────────────────────────
# Task 1.3 — InsuranceFormSchema
# ──────────────────────────────────────────────


class TestInsuranceFormSchema:
    """InsuranceFormSchema structural and behavioral tests."""

    def test_schema_loaded(self):
        """InsuranceFormSchema is importable and has 4 sections."""
        assert len(InsuranceFormSchema.secciones) == 4

    def test_all_standard_fields_present(self):
        """All expected insurance fields are present in the schema."""
        field_names = set()
        for section in InsuranceFormSchema.secciones:
            for field in section.campos:
                field_names.add(field.nombre)
        expected = {
            "nombre", "documento", "email", "telefono", "fecha_nacimiento",
            "tipo_cobertura", "suma_asegurada", "coberturas_adicionales",
            "beneficiario_nombre", "beneficiario_parentesco",
            "forma_pago", "cuenta_pago", "acepta_terminos",
        }
        missing = expected - field_names
        assert not missing, f"Missing fields: {missing}"
        extras = field_names - expected
        assert not extras, f"Unexpected fields: {extras}"
        assert len(field_names) == len(expected)

    def test_section_names(self):
        """Sections are in the correct order with correct names."""
        names = [s.nombre for s in InsuranceFormSchema.secciones]
        assert names == [
            "Datos del Tomador",
            "Cobertura",
            "Beneficiario",
            "Pago",
        ]

    def test_required_fields(self):
        """Required fields include all mandatory ones."""
        required = InsuranceFormSchema.campos_requeridos()
        req_names = {c.nombre for c in required}
        assert "nombre" in req_names
        assert "documento" in req_names
        assert "email" in req_names
        assert "telefono" in req_names
        assert "fecha_nacimiento" in req_names
        assert "tipo_cobertura" in req_names
        assert "suma_asegurada" in req_names
        assert "forma_pago" in req_names
        assert "acepta_terminos" in req_names
        assert all(c.requerido for c in required)

    def test_optional_fields(self):
        """Optional fields are correctly marked."""
        optional = [c for s in InsuranceFormSchema.secciones
                    for c in s.campos if not c.requerido]
        opt_names = {c.nombre for c in optional}
        assert "cuenta_pago" in opt_names
        assert "coberturas_adicionales" in opt_names
        assert "beneficiario_parentesco" in opt_names
        assert all(not c.requerido for c in optional)

    def test_product_field_variants_structure(self):
        """Each product variant has correct keys."""
        for prod_id, variants in PRODUCT_FIELD_VARIANTS.items():
            assert "has_beneficiario" in variants
            assert "suma_asegurada" in variants
            assert "min" in variants["suma_asegurada"]
            assert "max" in variants["suma_asegurada"]
            assert "tipo_cobertura" in variants
            assert "enum" in variants["tipo_cobertura"]

    def test_suma_asegurada_ranges_differ_per_product(self):
        """Product-specific suma_asegurada ranges are correct."""
        ranges = {}
        for prod_id, variants in PRODUCT_FIELD_VARIANTS.items():
            sa = variants["suma_asegurada"]
            ranges[prod_id] = (sa["min"], sa["max"])

        assert ranges["vida"] == (10_000_000, 200_000_000)
        assert ranges["mascotas"] == (500_000, 5_000_000)
        assert ranges["hogar"] == (20_000_000, 150_000_000)
        assert ranges["viajes"] == (1_000_000, 30_000_000)
        assert ranges["accidentes"] == (1_000_000, 50_000_000)
        assert ranges["movilidad"] == (5_000_000, 80_000_000)

    def test_has_beneficiario_only_for_vida(self):
        """Only Vida product has beneficiary section."""
        assert PRODUCT_FIELD_VARIANTS["vida"]["has_beneficiario"] is True
        for prod_id in ("accidentes", "viajes", "mascotas", "hogar", "movilidad"):
            assert PRODUCT_FIELD_VARIANTS[prod_id]["has_beneficiario"] is False, (
                f"{prod_id} should not have beneficiario"
            )

    def test_beneficiario_section_conditional_on_vida(self):
        """Beneficiario section is present (AI decides when to show it)."""
        nombres = [s.nombre for s in InsuranceFormSchema.secciones]
        assert "Beneficiario" in nombres

    def test_to_prompt_text_contains_all_sections(self):
        """to_prompt_text() includes all 4 section headers."""
        text = InsuranceFormSchema.to_prompt_text()
        assert "[Datos del Tomador]" in text
        assert "[Cobertura]" in text
        assert "[Beneficiario]" in text
        assert "[Pago]" in text
        assert "REQ" in text

    def test_to_prompt_text_structure(self):
        """to_prompt_text() has field lines with correct format."""
        text = InsuranceFormSchema.to_prompt_text()
        lines = text.strip().splitlines()
        non_empty = [l for l in lines if l.strip()]
        assert len(non_empty) > 15, "to_prompt_text() is too short"
        field_lines = [l for l in non_empty if l.startswith("  - ")]
        assert len(field_lines) >= 10, (
            f"Expected at least 10 field lines, got {len(field_lines)}"
        )

    def test_campos_requeridos_are_field_objects(self):
        """campos_requeridos() returns FormField instances."""
        required = InsuranceFormSchema.campos_requeridos()
        assert len(required) >= 8
        assert all(isinstance(f, FormField) for f in required)

    def test_field_types(self):
        """All fields have valid type values."""
        valid_types = {"string", "text", "select", "boolean", "date", "email", "number"}
        for section in InsuranceFormSchema.secciones:
            for campo in section.campos:
                assert campo.tipo in valid_types, (
                    f"{campo.nombre} has invalid type: {campo.tipo}"
                )

    def test_form_field_to_dict(self):
        """FormField serializes correctly."""
        field = FormField("test_field", "string", True, "Test prompt?", "Testing")
        d = field.to_dict()
        assert d["nombre"] == "test_field"
        assert d["tipo"] == "string"
        assert d["requerido"] is True
        assert d["prompt_question"] == "Test prompt?"
        assert d["seccion"] == "Testing"

    def test_product_variants_method(self):
        """product_variants() returns correct data or empty dict."""
        vida = InsuranceFormSchema.product_variants("vida")
        assert vida["has_beneficiario"] is True
        unknown = InsuranceFormSchema.product_variants("unknown")
        assert unknown == {}

    def test_campos_opcionales(self):
        """campos_opcionales() only returns non-required fields."""
        optional = InsuranceFormSchema.campos_opcionales()
        assert all(not c.requerido for c in optional)
        opt_names = {c.nombre for c in optional}
        # required fields should NOT be in optional
        assert "nombre" not in opt_names
        assert "documento" not in opt_names
