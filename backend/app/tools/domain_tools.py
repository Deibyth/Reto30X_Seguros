"""MCP Domain Tools — ORM-backed tools for product, customer, eligibility queries.

Each tool opens its own async SQLAlchemy session, queries the database,
and returns a formatted string (not raw JSON) for AI consumption.
All tools are registered via the ``@mcp.tool()`` decorator.
"""

import logging
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
from app.services.recommendation_engine import match_products, quote_product
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

        return (
            f"**Cliente:** {customer.nombre_completo}\n"
            f"**Documento:** {customer.documento_identidad}\n"
            f"**Email:** {customer.email or 'No registrado'}\n"
            f"**Salario:** ${customer.salario:,.0f} COP\n"
            f"**Categoría de afiliación:** {categoria}\n"
            f"**Tipo de contrato:** {customer.tipo_contrato or 'No especificado'}\n"
            f"**Antigüedad:** {customer.antiguedad_meses or 0} meses\n"
            f"**Score crediticio:** {customer.score_crediticio or 'No disponible'}"
        )


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


@mcp.tool()
def recommend_insurance(profile: dict) -> str:
    """Recommend insurance products based on a member's demographic profile.

    Applies deterministic rules against the profile attributes and returns
    an ordered list of matching products with descriptions and confidence levels.

    Parameters
    ----------
    profile : dict
        Demographic attributes collected from conversation
        (e.g., ``{{"familia_con_hijos": true, "preocupacion": "proteger"}}``).
    """
    products = match_products(profile)

    if not products:
        return "No encontramos productos que se ajusten a tu perfil."

    lines = ["**Productos recomendados para ti:**"]
    for i, p in enumerate(products, 1):
        confidence_label = {
            "high": "✅ Alta compatibilidad",
            "medium": "⚠️ Compatibilidad media",
            "low": "ℹ️ Compatibilidad baja",
        }.get(p["confidence"], p["confidence"])
        lines.append(
            f"\n**{i}. {p['nombre']}**\n"
            f"   {p['descripcion']}\n"
            f"   Prima base: ${p['prima_base']:,} COP/mes\n"
            f"   {confidence_label}: {p['match_reason']}"
        )
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
        Member profile including ``edad``, used for age-based pricing.
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
    customer_id: str,
    form_data: dict,
    insurance_id: str,
) -> str:
    """Create an insurance policy for a customer.

    Validates terms acceptance and creates an Application (tipo='seguro')
    and a Policy in a single atomic transaction.

    Parameters
    ----------
    customer_id : str
        The customer's UUID.
    form_data : dict
        Collected form fields. MUST include ``acepta_terminos`` set to ``true``.
    insurance_id : str
        The insurance product UUID from the insurances table.
    """
    if async_session_maker is None:
        return "Error: la base de datos no está inicializada."

    # Validate terms acceptance
    if not form_data.get("acepta_terminos"):
        return "Error: debe aceptar los términos y condiciones para crear la póliza."

    async with async_session_maker() as session:
        try:
            # Verify customer exists
            customer = await session.get(Customer, customer_id)
            if not customer:
                return f"Error: no se encontró el cliente con ID '{customer_id}'."

            # Verify insurance exists
            insurance = await session.get(Insurance, insurance_id)
            if not insurance:
                return f"Error: no se encontró el seguro con ID '{insurance_id}'."

            # Generate policy number
            import uuid as _uuid
            numero_poliza = f"POL-{_uuid.uuid4().hex[:8].upper()}"

            from datetime import datetime

            app = Application(
                tipo="seguro",
                customer_id=customer_id,
                form_data=form_data,
                estado="iniciada",
            )
            session.add(app)
            await session.flush()

            policy = Policy(
                customer_id=customer_id,
                insurance_id=insurance_id,
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
