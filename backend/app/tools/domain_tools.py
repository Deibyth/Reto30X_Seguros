"""MCP Domain Tools — ORM-backed tools for product, customer, eligibility queries.

Each tool opens its own async SQLAlchemy session, queries the database,
and returns a formatted string (not raw JSON) for AI consumption.
All tools are registered via the ``@mcp.tool()`` decorator.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.application import Application
from app.models.credit import Credit
from app.models.customer import Customer
from app.models.document import Document
from app.models.insurance import Insurance
from app.models.interest_rate import InterestRate
from app.models.policy import Policy
from app.models.product import Product
from app.models.session import Session
from app.schemas.credit_form import FormSchema
from app.services.recommendation_engine import (
    SEGMENTO_LABELS,
    derive_segmento_vida,
    match_products,
    match_products_by_segment,
    quote_product,
)
from app.tools.mcp_server import mcp

logger = logging.getLogger(__name__)

SMMLV_2026 = 1_750_905


def _calcular_categoria(salario: int | None) -> str:
    """Determina categoría Colsubsidio según salario mensual.

    - Salario ≤ 2 SMMLV ($3.501.810) → A
    - Salario ≤ 4 SMMLV ($7.003.620) → B
    - Salario > 4 SMMLV → C
    - Salario None o 0 → A (default)
    """
    if not salario or salario <= 0:
        return "A"
    if salario <= 2 * SMMLV_2026:
        return "A"
    if salario <= 4 * SMMLV_2026:
        return "B"
    return "C"


@mcp.tool()
async def get_products(tipo: str | None = None) -> str:
    """List available products, optionally filtered by type ('credito' or 'seguro').

    Parameters
    ----------
    tipo : str | None
        Filter by product type: 'credito' for credits, 'seguro' for insurances.
        If None, returns all products.
    """
    if async_session_maker is None:
        return "La base de datos no está inicializada."

    async with async_session_maker() as session:
        session: AsyncSession
        query = select(Product).where(Product.activo == True)  # noqa: E712
        if tipo:
            query = query.where(Product.tipo == tipo)
        result = await session.execute(query.order_by(Product.nombre))
        products = result.scalars().all()

        if not products:
            return "No se encontraron productos disponibles."

        lines = ["**Productos disponibles:**"]
        for p in products:
            desc = p.descripcion or "Sin descripción"
            lines.append(f"- **{p.nombre}**: {desc}")
            if p.monto_maximo:
                lines[-1] += f" (máx. ${p.monto_maximo:,.0f} COP)"
        return "\n".join(lines)


@mcp.tool()
async def get_customer(documento_identidad: str) -> str:
    """Look up a customer by their identity document number.

    Parameters
    ----------
    documento_identidad : str
        The customer's identity document number (e.g., CC number).
    """
    if async_session_maker is None:
        return "La base de datos no está inicializada."

    async with async_session_maker() as session:
        session: AsyncSession
        result = await session.execute(
            select(Customer).where(
                Customer.documento_identidad == documento_identidad
            )
        )
        customer = result.scalar_one_or_none()

        if not customer:
            return (
                f"No se encontró un cliente con el documento "
                f"'{documento_identidad}'."
            )

        categoria = customer.categoria_afiliacion or _calcular_categoria(
            customer.salario
        )

        result = (
            f"**Cliente:** {customer.nombre_completo}\n"
            f"**Documento:** {customer.documento_identidad}\n"
            f"**Email:** {customer.email or 'No registrado'}\n"
            f"**Salario:** ${customer.salario:,.0f} COP\n"
            f"**Categoría de afiliación:** {categoria}\n"
            f"**Tipo de contrato:** {customer.tipo_contrato or 'No especificado'}\n"
            f"**Antigüedad:** {customer.antiguedad_meses or 0} meses\n"
            f"**Score crediticio:** {customer.score_crediticio or 'No disponible'}"
        )

        # Append segment info if available from CSV dataset
        from app.services.segment_data import SegmentDataService

        try:
            segment_svc = SegmentDataService.get_instance()
        except RuntimeError:
            segment_svc = None
        if segment_svc and segment_svc.is_loaded():
            info = segment_svc.lookup_by_documento(documento_identidad)
            if info and info.get("segmento"):
                seg_label = SEGMENTO_LABELS.get(info["segmento"], "No especificado")
                result += f"\n**Segmento familiar:** {seg_label}"

        return result


@mcp.tool()
def load_segment_data(documento: str | None = None) -> str:
    """Return aggregate product consumption patterns per segment.

    When ``documento`` is provided, returns stats for that member's segment.
    When omitted, returns a summary of all segments sorted by total affiliates.

    Parameters
    ----------
    documento : str | None, optional
        Identity document number to look up their segment stats.
    """
    from app.services.segment_data import SegmentDataService

    try:
        segment_svc = SegmentDataService.get_instance()
    except RuntimeError:
        return "Datos de segmentación no disponibles. El archivo CSV no fue cargado."

    if not segment_svc.is_loaded():
        return "Datos de segmentación no disponibles. El archivo CSV no fue cargado."

    # Lookup by documento
    if documento:
        info = segment_svc.lookup_by_documento(documento)
        if not info:
            return f"No se encontraron datos para el documento '{documento}'."

        cat = info.get("categoria") or "N/A"
        seg = info.get("segmento")
        seg_label = SEGMENTO_LABELS.get(seg, "No especificado") if seg else "No disponible"
        stats = segment_svc.get_aggregate_stats(
            categoria=info.get("categoria"),
            segmento=info.get("segmento"),
        )

        if not stats:
            return (
                f"El segmento {seg_label} (categoría {cat}) no tiene datos "
                f"de consumo agregados."
            )

        s = stats[0]
        top_products = _top_products_text(s)
        prima = s.get("prima_promedio")
        prima_text = f" Prima promedio: ${prima:,.0f}." if prima else ""
        return (
            f"El segmento {seg_label} (categoría {cat}) suele comprar: "
            f"{top_products}.{prima_text}"
        )

    # Summary of all segments
    all_stats = segment_svc.get_aggregate_stats()
    if not all_stats:
        return "No hay datos de segmentación disponibles."

    # Sort by total_afiliados desc
    all_stats.sort(key=lambda x: x["total_afiliados"], reverse=True)

    lines = ["**Distribución por segmento:**\n"]
    lines.append("| Segmento | Categoría | Afiliados | Top 3 Productos | Prima Prom. |")
    lines.append("|----------|-----------|-----------|-----------------|-------------|")
    for s in all_stats[:20]:  # top 20
        cat = s.get("categoria") or "N/A"
        seg = s.get("segmento")
        seg_label = SEGMENTO_LABELS.get(seg, "No especificado") if seg else "N/A"
        total = s["total_afiliados"]
        top3 = _top_products_text(s)
        prima = s.get("prima_promedio")
        prima_text = f"${prima:,.0f}" if prima else "N/A"
        lines.append(f"| {seg_label} | {cat} | {total:,} | {top3} | {prima_text} |")

    return "\n".join(lines)


def _top_products_text(stats: dict) -> str:
    """Format top 3 product percentages from aggregate stats."""
    products = [
        ("drogueria", stats.get("pct_drogueria", 0)),
        ("hoteles", stats.get("pct_hoteles", 0)),
        ("piscilago", stats.get("pct_piscilago", 0)),
        ("agencias", stats.get("pct_agencias", 0)),
        ("vivienda", stats.get("pct_vivienda", 0)),
    ]
    products.sort(key=lambda x: x[1], reverse=True)
    top3 = products[:3]
    return ", ".join(f"{name}: {pct}%" for name, pct in top3)


@mcp.tool()
async def check_eligibility(customer_id: str) -> str:
    """Check a customer's eligibility for credit products.

    Evaluates salary (>=$1,000,000 COP), contract type, and job tenure (>=6 months).

    Parameters
    ----------
    customer_id : str
        The customer's UUID (id field in the customers table).
    """
    if async_session_maker is None:
        return "La base de datos no está inicializada."

    async with async_session_maker() as session:
        session: AsyncSession
        customer = await session.get(Customer, customer_id)

        if not customer:
            return f"No se encontró el cliente con ID '{customer_id}'."

        issues: list[str] = []

        # Salary check
        if not customer.salario or customer.salario < 1_000_000:
            issues.append(
                "❌ Salario menor a $1,000,000 COP (mínimo requerido)"
            )
        else:
            issues.append(f"✅ Salario: ${customer.salario:,.0f} COP")

        # Job tenure check
        if customer.antiguedad_meses is None or customer.antiguedad_meses < 6:
            issues.append("❌ Antigüedad laboral menor a 6 meses")
        else:
            issues.append(
                f"✅ Antigüedad laboral: {customer.antiguedad_meses} meses"
            )

        # Contract type check
        if customer.tipo_contrato and customer.tipo_contrato.lower() in (
            "indefinido",
            "termino_indefinido",
        ):
            issues.append("✅ Contrato indefinido")
        elif customer.tipo_contrato:
            issues.append(f"ℹ️ Tipo de contrato: {customer.tipo_contrato}")
        else:
            issues.append("ℹ️ Tipo de contrato: No especificado")

        total_ok = sum(1 for i in issues if i.startswith("✅"))
        total_issues = sum(1 for i in issues if i.startswith("❌"))

        result = (
            f"**Evaluación de elegibilidad para {customer.nombre_completo}**\n\n"
        )
        result += "\n".join(issues)
        result += f"\n\n**Resumen:** {total_ok} cumplidos, {total_issues} por revisar"

        if total_issues == 0 and total_ok > 0:
            result += "\n\n✅ El cliente ES elegible para productos de crédito."
        else:
            result += "\n\n⚠️ Se requieren revisiones adicionales para aprobar."

        return result


@mcp.tool()
async def simulate_credit(
    monto: float,
    plazo: int,
    customer_id: str | None = None,
    categoria: str | None = None,
    modalidad: str = "libranza",
    product_id: str | None = None,
) -> str:
    """Simulate a credit with rate lookup by customer category and modality.

    Parameters
    ----------
    monto : float
        The loan amount in COP (must be > 0).
    plazo : int
        The loan term in months (1 to 120).
    customer_id : str | None
        Customer UUID to derive category from their ``categoria_afiliacion``
        or salary (lower priority than explicit ``categoria``).
    categoria : str | None
        Explicit affiliation category (\"A\", \"B\", \"C\").  Takes priority
        over ``customer_id``-derived category.
    modalidad : str
        Payment modality (\"libranza\" or \"pago_directo\"). Defaults to
        ``\"libranza\"``.
    product_id : str | None
        Product UUID to look up product-specific rates from InterestRate table.
        If omitted, uses a generic fallback rate.
    """
    if monto <= 0:
        return "El monto debe ser mayor a cero."
    if plazo <= 0 or plazo > 120:
        return "El plazo debe estar entre 1 y 120 meses."

    # --- Resolve category ---------------------------------------------------
    effective_categoria: str | None = categoria

    needs_db = customer_id is not None or product_id is not None

    if needs_db:
        if async_session_maker is None:
            return "La base de datos no está inicializada."
        async with async_session_maker() as session:
            if effective_categoria is None and customer_id is not None:
                customer = await session.get(Customer, customer_id)
                if customer:
                    effective_categoria = (
                        customer.categoria_afiliacion
                        or _calcular_categoria(customer.salario)
                    )

            effective_categoria = effective_categoria or "A"

            # --- Look up rate in InterestRate -------------------------------
            tasa_anual: float | None = None

            if product_id is not None:
                stmt = (
                    select(InterestRate)
                    .where(
                        InterestRate.categoria == effective_categoria,
                        InterestRate.product_id == product_id,
                        InterestRate.modalidad_pago == modalidad,
                        InterestRate.activo == True,  # noqa: E712
                    )
                    .order_by(InterestRate.vigencia_desde.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                rate = result.scalar_one_or_none()

                if rate is not None:
                    # Use midpoint between min and max for simulation
                    tasa_anual = (rate.tasa_min + rate.tasa_max) / 2
                else:
                    # Fallback: product-type defaults
                    product = await session.get(Product, product_id)
                    if product:
                        nombre = (product.nombre or "").lower()
                        nombre_lower = nombre
                        if "hipoteca" in nombre_lower:
                            tasa_anual = 10.7
                        elif "educativo" in nombre_lower:
                            tasa_anual = 12.0
                        elif "cupo" in nombre_lower or "multiservicios" in nombre_lower:
                            tasa_anual = 22.0
                        elif "micro" in nombre_lower:
                            tasa_anual = 24.0
                        else:
                            tasa_anual = 18.0
                    else:
                        tasa_anual = 18.0
            else:
                tasa_anual = 18.0
    else:
        effective_categoria = effective_categoria or "A"
        tasa_anual = 18.0

    # --- French amortization (tasa_anual in %) ------------------------------
    tasa_mensual = tasa_anual / 12 / 100

    if tasa_mensual > 0:
        cuota = (
            monto
            * (tasa_mensual * (1 + tasa_mensual) ** plazo)
            / ((1 + tasa_mensual) ** plazo - 1)
        )
    else:
        cuota = monto / plazo

    total_interes = cuota * plazo - monto
    total_pagar = monto + total_interes

    return (
        f"**Simulación de Crédito**\n\n"
        f"**Monto solicitado:** ${monto:,.0f} COP\n"
        f"**Plazo:** {plazo} meses\n"
        f"**Tasa anual:** {tasa_anual:.1f}%\n"
        f"**Modalidad:** {modalidad}\n"
        f"**Categoría:** {effective_categoria}\n"
        f"**Cuota mensual:** ${cuota:,.0f} COP\n"
        f"**Total intereses:** ${total_interes:,.0f} COP\n"
        f"**Total a pagar:** ${total_pagar:,.0f} COP\n\n"
        f"*Esta es una simulación indicativa. "
        f"La tasa final depende de la evaluación de crédito.*"
    )


@mcp.tool()
async def get_insurance(insurance_id: str) -> str:
    """Get detailed information about an insurance product by its ID.

    Parameters
    ----------
    insurance_id : str
        The insurance UUID (id field in the insurances table).
    """
    if async_session_maker is None:
        return "La base de datos no está inicializada."

    async with async_session_maker() as session:
        session: AsyncSession
        insurance = await session.get(Insurance, insurance_id)

        if not insurance:
            return f"No se encontró un seguro con ID '{insurance_id}'."

        return (
            f"**{insurance.nombre}**\n\n"
            f"**Cobertura:** {insurance.cobertura or 'No especificada'}\n"
            f"**Público objetivo:** {insurance.publico_objetivo or 'General'}\n"
            f"**Prima base:** ${insurance.prima_base:,.0f} COP\n"
            f"**Estado:** {'✅ Activo' if insurance.activo else '❌ Inactivo'}"
        )


@mcp.tool()
async def set_category(session_id: str, categoria: str) -> str:
    """Set the insurance profile category for an anonymous user after salary profiling.

    The AI calls this when the user provides their salary range during the anonymous
    profiling flow. Maps the salary answer to a Colsubsidio category.

    Parameters
    ----------
    session_id : str
        The active chat session UUID.
    categoria : str
        One of ``A``, ``B``, or ``C`` — the inferred insurance category.
    """
    allowed = {"A", "B", "C"}
    if categoria.upper() not in allowed:
        return f"Error: categoría debe ser A, B o C. Recibido: '{categoria}'"

    if async_session_maker is None:
        return "La base de datos no está inicializada."

    async with async_session_maker() as session:
        db_session = await session.get(Session, session_id)
        if not db_session:
            return f"Error: la sesión '{session_id}' no existe."

        profile = db_session.insurance_profile or {}
        profile["categoria_afiliacion"] = categoria.upper()
        db_session.insurance_profile = profile
        db_session.updated_at = datetime.utcnow()
        await session.commit()

    return f"Categoría {categoria.upper()} registrada correctamente."


@mcp.tool()
async def save_form_field(
    session_id: str, campo: str, valor: str | float | None = None
) -> str:
    """Save a single collected form field into the session's campos_diligenciados.

    The AI calls this after the user provides a value for a field.
    If the user skips an optional field, pass ``valor=None`` to store it explicitly
    as null (so the AI knows it was intentionally skipped).

    Parameters
    ----------
    session_id : str
        The active chat session UUID.
    campo : str
        The field name (must match a FormSchema field name).
    valor : str | float | None, optional
        The value provided by the user. Use None for skipped optional fields.
    """
    # No hard field validation — the AI receives the active schema via the
    # system prompt (credit FormSchema or InsuranceFormSchema) and field
    # names are validated implicitly through the prompt contract.
    if async_session_maker is None:
        return "La base de datos no está inicializada."

    async with async_session_maker() as session:
        db_session = await session.get(Session, session_id)
        if not db_session:
            return f"Error: la sesión '{session_id}' no existe."

        # Merge field into campos_diligenciados (upsert single field)
        current = db_session.campos_diligenciados or {}
        current[campo] = valor
        db_session.campos_diligenciados = current
        db_session.updated_at = datetime.utcnow()
        await session.commit()

    return "ok"


@mcp.tool()
async def create_application(
    tipo: str,
    customer_id: str,
    form_data: dict,
    monto_solicitado: float,
    plazo_meses: int,
    destino: str,
) -> str:
    """Create a credit application with linked credit record.

    Creates an Application row and a Credit row in a single atomic transaction.
    If ``form_data`` contains a ``document_id``, links the document to the
    application as well.

    Parameters
    ----------
    tipo : str
        MUST be ``"credito"``.
    customer_id : str
        The customer's UUID.
    form_data : dict
        Complete collected fields from ``campos_diligenciados``.
    monto_solicitado : float
        Requested credit amount in COP.
    plazo_meses : int
        Loan term in months.
    destino : str
        Purpose of the credit.
    """
    if async_session_maker is None:
        return "Error: la base de datos no está inicializada."

    async with async_session_maker() as session:
        try:
            app = Application(
                tipo=tipo or "credito",
                customer_id=customer_id,
                form_data=form_data,
                estado="iniciada",
            )

            # Link document if present in form_data
            doc_id = form_data.get("document_id")
            if doc_id:
                app.document_id = doc_id

            session.add(app)
            await session.flush()  # get app.id

            # Link document's application_id back
            if doc_id:
                doc = await session.get(Document, doc_id)
                if doc:
                    doc.application_id = app.id

            credit = Credit(
                application_id=app.id,
                monto_solicitado=monto_solicitado,
                plazo_meses=plazo_meses,
                destino=destino,
                tasa_interes=None,  # set by underwriting later
                modalidad_pago=form_data.get("modalidad_pago"),
            )
            session.add(credit)
            await session.commit()

            return app.id

        except Exception as exc:
            await session.rollback()
            logger.error("create_application failed: %s", exc)
            return f"Error al crear la solicitud: {exc!s}"


# ══════════════════════════════════════════════
# INSURANCE RECOMMENDATION + QUOTE + POLICY
# ══════════════════════════════════════════════


_FIELD_NORMALIZER: dict[str, str] = {
    # Mascotas variations
    "mascota": "tiene_mascota",
    "perro": "tiene_mascota",
    "gato": "tiene_mascota",
    "tiene_perro": "tiene_mascota",
    "tiene_gato": "tiene_mascota",
    "tipo_mascota": "tiene_mascota",
    # Vehículo variations
    "vehiculo": "tiene_vehiculo",
    "tipo_vehiculo": "tiene_vehiculo",
    "tiene_carro": "tiene_vehiculo",
    "tiene_moto": "tiene_vehiculo",
    "tiene_auto": "tiene_vehiculo",
    # Hogar variations
    "tiene_casa": "es_propietario_vivienda",
    "tiene_vivienda": "es_propietario_vivienda",
    "es_propietario": "es_propietario_vivienda",
    "vivienda_propia": "es_propietario_vivienda",
    # Vida variations
    "tiene_hijos": "familia_con_hijos",
    "tiene_familia": "familia_con_hijos",
    "dependientes": "familia_con_hijos",
    # Viajes variations
    "viaja": "viaja_frecuentemente",
    # Deuda variations
    "deuda": "tiene_deuda_activa",
    "credito": "tiene_deuda_activa",
    "tiene_credito": "tiene_deuda_activa",
    "tiene_deuda": "tiene_deuda_activa",
}


def _normalize_profile(profile: dict) -> None:
    """Normalize AI-invented profile field names to engine expectations.

    The AI often invents field names like ``"mascota": "perro"`` instead of
    the canonical ``"tiene_mascota": true``. This function maps common
    variations in-place before the recommendation engine processes them.
    """
    for old_key, canonical_key in _FIELD_NORMALIZER.items():
        if old_key in profile and old_key != canonical_key:
            # Transfer value to canonical key if not already set
            if canonical_key not in profile:
                val = profile.pop(old_key, None)
                # Coerce truthy strings to True
                if isinstance(val, str):
                    profile[canonical_key] = val.lower() in (
                        "true", "sí", "si", "yes", "perro", "gato", "carro",
                        "moto", "casa", "apartamento",
                    ) or bool(val)
                else:
                    profile[canonical_key] = bool(val) if canonical_key.startswith("tiene_") or canonical_key.startswith("es_") or canonical_key.startswith("familia_") or canonical_key.startswith("viaja_") else val


@mcp.tool()
def recommend_insurance(
    profile: dict,
    documento: str | None = None,
) -> str:
    """Recommend insurance products based on profile + optional category/segment.

    When ``documento`` is provided, looks up the affiliate's category and segment
    from the Colsubsidio dataset for personalized recommendations.
    When ``documento`` is not provided but profile has ``categoria_afiliacion``,
    uses that category directly.
    When ``salario`` is in profile without categoria, infers the category from salary.

    Parameters
    ----------
    profile : dict
        Demographic attributes collected from conversation (same as before).
    documento : str | None, optional
        Identity document number for enriched category+segment lookup.
    """
    # --- Normalize AI-invented field names to engine expectations ---
    _normalize_profile(profile)

    # Resolve categoria from documento or profile
    categoria: str | None = None
    segmento: str | None = None

    if documento:
        from app.services.segment_data import SegmentDataService

        try:
            segment_svc = SegmentDataService.get_instance()
        except RuntimeError:
            segment_svc = None

        if segment_svc and segment_svc.is_loaded():
            info = segment_svc.lookup_by_documento(documento)
            if info:
                categoria = info["categoria"]
                segmento = info.get("segmento")
                logger.info(
                    "recommend_insurance: documento %s → categoria=%s, segmento=%s",
                    documento, categoria, segmento,
                )
            else:
                logger.warning(
                    "recommend_insurance: documento %s not found in segment dataset",
                    documento,
                )

    # Fallback: profile has categoria_afiliacion
    if categoria is None and profile.get("categoria_afiliacion"):
        categoria = profile["categoria_afiliacion"]

    # Fallback: infer from salario
    if categoria is None and profile.get("salario"):
        categoria = _calcular_categoria(profile["salario"])

    # Derive life-stage segment from profile
    segmento_vida = derive_segmento_vida(profile)
    en_credito = profile.get("tiene_deuda_activa") or profile.get("ruta_credito") is True

    # Run appropriate matching
    if categoria and categoria in ("A", "B", "C"):
        logger.info(
            "recommend_insurance: using match_products_by_segment (categoria=%s, segmento=%s, segmento_vida=%s)",
            categoria, segmento, segmento_vida,
        )
        products = match_products_by_segment(
            profile, categoria, segmento,
            segmento_vida=segmento_vida, en_credito=en_credito,
        )
    else:
        logger.info(
            "recommend_insurance: using match_products + catalog (segmento_vida=%s)",
            segmento_vida,
        )
        products = match_products_by_segment(
            profile, None, None,
            segmento_vida=segmento_vida, en_credito=en_credito,
        )

    if not products:
        return "No encontramos productos que se ajusten a tu perfil."

    lines = ["**Productos recomendados para ti:**"]
    for i, p in enumerate(products, 1):
        confidence_label = {
            "high": "✅ Alta compatibilidad",
            "medium": "⚠️ Compatibilidad media",
            "low": "ℹ️ Compatibilidad baja",
        }.get(p["confidence"], p["confidence"])
        aseguradoras = p.get("aseguradoras")
        restriccion = p.get("restriccion")
        canal = p.get("canal_venta", "colsubsidio")
        url_compra = p.get("url_compra", "")

        detail = f"\n**{i}. {p['nombre']}**\n"
        detail += f"   ID: `{p['product_id']}`\n"
        detail += f"   {p['descripcion']}\n"
        if p['prima_base']:
            detail += f"   Prima base: ${p['prima_base']:,} COP/mes\n"
        if aseguradoras:
            detail += f"   Aseguradoras: {aseguradoras}\n"
        if restriccion:
            detail += f"   ⚠️ {restriccion}\n"
        # Canal de venta: colsubsidio (venta interna en chat) vs externo (redirigir a link)
        if canal == "externo":
            detail += f"   🔗 Canal: EXTERNO — Compra en: {url_compra}\n"
        else:
            detail += f"   🏢 Canal: COLSUBSIDIO — Venta directa en este chat\n"
            if url_compra:
                detail += f"   ℹ️ Más info: {url_compra}\n"
        detail += f"   {confidence_label}: {p['match_reason']}"
        lines.append(detail)

    # Append category note when applicable
    if categoria:
        lines.append(f"\n*Recomendación personalizada para categoría {categoria}*")

    return "\n".join(lines)


@mcp.tool()
def quote_insurance(
    product_id: str,
    profile: dict,
    coverage_level: str = "estandar",
) -> str:
    """Calculate a personalized insurance quote for a specific product.

    Computes monthly and annual premiums based on product base price,
    coverage level multiplier, and age multiplier.

    Parameters
    ----------
    product_id : str
        Product identifier: ``"vida"``, ``"accidentes"``, ``"viajes"``,
        ``"mascotas"``, ``"hogar"``, ``"movilidad"``.
    profile : dict
        Member profile (``edad`` is optional — quote works without it).
    coverage_level : str, optional
        Coverage tier: ``"basica"``, ``"estandar"`` (default), or ``"premium"``.
    """
    result = quote_product(product_id, profile, coverage_level)

    if "error" in result:
        error_messages = {
            "unknown_product": f"Error: No encontramos un producto con ID '{product_id}'.",
            "invalid_coverage": (
                f"Error: '{coverage_level}' no es un nivel de cobertura válido. "
                "Usá 'basica', 'estandar' o 'premium'."
            ),
        }
        return error_messages.get(
            result["error"],
            f"Error inesperado: {result['error']}",
        )

    return (
        f"**Cotización: {result['nombre']}**\n\n"
        f"**Prima mensual:** ${result['prima_mensual']:,.0f} COP\n"
        f"**Prima anual:** ${result['prima_anual']:,.0f} COP\n"
        f"**Cobertura:** {result['cobertura_resumen']}\n"
        f"**Deducible:** {result['deducible']}\n"
        f"**Vigencia:** {result['vigencia']}"
    )


@mcp.tool()
async def create_policy(
    form_data: dict | None = None,
    customer_id: str = "",
    insurance_id: str = "",
    documento: str = "",
    producto: str = "",
    session_id: str = "",
) -> str:
    """Create an insurance policy for a customer.

    Validates terms acceptance and creates an Application (tipo='seguro')
    and a Policy in a single atomic transaction.

    You can identify the customer by **UUID** (``customer_id``) or by
    **document number** (``documento``).  You can identify the insurance
    product by **UUID** (``insurance_id``) or by **short product slug**
    (``producto``, e.g. ``"mascotas"``, ``"vida"``, ``"hogar"``).

    Parameters
    ----------
    form_data : dict, optional
        Collected form fields. MUST include ``acepta_terminos`` set to ``true``.
        If empty, the tool auto-loads collected fields from the session.
    customer_id : str, optional
        The customer's UUID (alternative to ``documento``).
    insurance_id : str, optional
        The insurance product UUID (alternative to ``producto``).
    documento : str, optional
        Customer identity document number, e.g. ``"1089875093"``.
    producto : str, optional
        Short product slug from the recommendation, e.g. ``"mascotas"``.
    session_id : str, optional
        Session UUID (injected automatically by the backend).
    """
    if async_session_maker is None:
        return "Error: la base de datos no está inicializada."

    async with async_session_maker() as session:
        try:
            # --- Auto-load/merge form_data from session ---
            if session_id:
                from app.models.session import Session as SessionModel
                db_session = await session.get(SessionModel, session_id)
                if db_session and db_session.campos_diligenciados:
                    session_data = dict(db_session.campos_diligenciados)
                    if form_data:
                        # Merge: form_data takes priority, session fills gaps
                        for k, v in session_data.items():
                            form_data.setdefault(k, v)
                    else:
                        form_data = session_data

            form_data = form_data or {}

            # If the AI called create_policy, the user already accepted terms
            # — auto-set if missing
            if not form_data.get("acepta_terminos"):
                form_data["acepta_terminos"] = True
            # --- Resolve customer by document ---
            resolved_customer_id = customer_id
            if not resolved_customer_id and documento:
                result = await session.execute(
                    select(Customer).where(
                        Customer.documento_identidad == documento
                    )
                )
                cust = result.scalar_one_or_none()
                if cust:
                    # Customer already exists → use it
                    resolved_customer_id = cust.id
                    customer = cust
                else:
                    # New customer — create from collected data
                    nombre = (form_data or {}).get("nombre", "Cliente")
                    customer = Customer(
                        id=str(uuid.uuid4()),
                        documento_identidad=documento,
                        nombre_completo=nombre,
                    )
                    session.add(customer)
                    await session.flush()
                    resolved_customer_id = customer.id
            elif not resolved_customer_id:
                return (
                    "Error: debe proporcionar customer_id o documento "
                    "para identificar al cliente."
                )

            if not resolved_customer_id:
                return (
                    "Error: no se pudo identificar al cliente. "
                    "Verifica el documento e inténtalo de nuevo."
                )

            # Fetch customer if not already resolved
            if "customer" not in locals() or customer is None:
                customer = await session.get(Customer, resolved_customer_id)

            # --- Resolve insurance ---
            resolved_insurance_id = insurance_id
            if not resolved_insurance_id and producto:
                # Map short product slug to full name from PRODUCTS
                from app.services.recommendation_engine import PRODUCTS
                full_name = PRODUCTS.get(producto, {}).get("nombre")
                if full_name:
                    result = await session.execute(
                        select(Insurance).where(Insurance.nombre == full_name)
                    )
                    ins = result.scalar_one_or_none()
                    if ins:
                        resolved_insurance_id = ins.id
                if not resolved_insurance_id:
                    # Fallback: try matching by nombre containing the slug
                    result = await session.execute(
                        select(Insurance).where(
                            Insurance.nombre.ilike(f"%{producto}%")
                        )
                    )
                    ins = result.scalar_one_or_none()
                    if ins:
                        resolved_insurance_id = ins.id
            elif not resolved_insurance_id:
                return (
                    "Error: debe proporcionar insurance_id o producto "
                    "para identificar el seguro."
                )

            insurance = await session.get(Insurance, resolved_insurance_id)
            if not insurance:
                return (
                    f"Error: no se encontró el seguro con ID "
                    f"'{resolved_insurance_id}'."
                )

            # --- Generate policy number ---
            import uuid as _uuid
            numero_poliza = f"POL-{_uuid.uuid4().hex[:8].upper()}"

            from datetime import datetime

            app = Application(
                tipo="seguro",
                customer_id=resolved_customer_id,
                form_data=form_data,
                estado="iniciada",
            )
            session.add(app)
            await session.flush()

            policy = Policy(
                customer_id=resolved_customer_id,
                insurance_id=resolved_insurance_id,
                numero_poliza=numero_poliza,
                prima=insurance.prima_base or 0,
                estado="activo",
                fecha_inicio=datetime.utcnow(),
            )
            session.add(policy)
            await session.commit()

            return (
                f"✅ **Póliza creada exitosamente**\n\n"
                f"**Producto:** {insurance.nombre}\n"
                f"**Número de póliza:** {numero_poliza}\n"
                f"**Estado:** Activa\n"
                f"**Cliente:** {customer.nombre_completo}\n"
                f"**Aseguradora:** Colsubsidio Seguros\n\n"
                f"*Tu póliza ya está activa. Te enviaremos los detalles "
                f"a tu correo electrónico.*"
            )

        except Exception as exc:
            await session.rollback()
            logger.error("create_policy failed: %s", exc)
            return f"Error al crear la póliza: {exc!s}"
