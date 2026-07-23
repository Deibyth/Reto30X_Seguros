"""Seed script — populates the database with test customers, products, and demo data.

Usage:
    cd backend && venv/bin/python -m app.seed

Add --clear to drop existing data before seeding:
    cd backend && venv/bin/python -m app.seed --clear
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy import text

# Must import the module (not individual names) because async_session_maker
# is set by init_engine() at module level after import.
import app.database as db
from app.models import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("seed")

SMMLV_2026 = 1_750_905


def _calcular_categoria(salario: int | None) -> str:
    """Determina categoría Colsubsidio según salario mensual."""
    if not salario or salario <= 0:
        return "A"
    if salario <= 2 * SMMLV_2026:
        return "A"
    if salario <= 4 * SMMLV_2026:
        return "B"
    return "C"

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

CUSTOMERS = [
    {
        "documento_identidad": "100000001",
        "nombre_completo": "Juan Pérez",
        "email": "devhack1925@gmail.com",
        "telefono": "+573176529013",
        "salario": 3_500_000,
        "tipo_contrato": "Indefinido",
        "antiguedad_meses": 54,
        "score_crediticio": 720,
    },
    {
        "documento_identidad": "100000002",
        "nombre_completo": "Pedro Jiménez",
        "email": "pedro.jimenez@correo.net",
        "telefono": "3007894561",
        "salario": 0,
        "tipo_contrato": None,  # estudiante
        "antiguedad_meses": 0,
        "score_crediticio": None,
    },
]

# Productos reales de Colsubsidio
# Fuente: colsubsidio.com — portafolio oficial de créditos y seguros

CREDIT_PRODUCTS = [
    {
        "nombre": "Crédito Libre Inversión",
        "tipo": "credito",
        "descripcion": "Crédito de consumo sin destinación específica. Tasas según categoría de afiliación (A, B o C).",
        "monto_maximo": 50_000_000,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Compra de Cartera",
        "tipo": "credito",
        "descripcion": "Crédito de consumo para unificar deudas de otros bancos. Tasas preferenciales según categoría de afiliación.",
        "monto_maximo": 80_000_000,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Crédito para Mujeres",
        "tipo": "credito",
        "descripcion": "Crédito de consumo diseñado para proyectos o emprendimientos de mujeres afiliadas.",
        "monto_maximo": 30_000_000,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Crédito Educativo",
        "tipo": "credito",
        "descripcion": "Financiación de carreras, posgrados, cursos libres o diplomados. Desde $300.000 hasta el 100% del valor de la matrícula.",
        "monto_maximo": 50_000_000,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Crédito Hipotecario",
        "tipo": "credito",
        "descripcion": "Compra de vivienda nueva con cuotas fijas, en pesos o UVR. Plazos cómodos.",
        "monto_maximo": 500_000_000,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Cupo de Crédito (Tarjeta Multiservicios)",
        "tipo": "credito",
        "descripcion": "Crédito rotativo para compras en convenio o retiros en efectivo. Renovación automática.",
        "monto_maximo": 20_000_000,
        "modalidad": "Rotativo",
        "activo": True,
    },
    {
        "nombre": "Microcrédito",
        "tipo": "credito",
        "descripcion": "Apoyo al desarrollo de unidades productivas o negocios. Montos accesibles y requisitos flexibles.",
        "monto_maximo": 10_000_000,
        "modalidad": "Mensual",
        "activo": True,
    },
]

INSURANCE_PRODUCTS = [
    {
        "nombre": "Seguro de Vida",
        "tipo": "seguro",
        "descripcion": "Respaldo económico familiar ante casos de fallecimiento, enfermedades o incapacidad.",
        "monto_maximo": None,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Póliza de Salud",
        "tipo": "seguro",
        "descripcion": "Coberturas médicas preferenciales y acceso a especialistas que complementan tu plan básico de salud.",
        "monto_maximo": None,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Accidentes Personales",
        "tipo": "seguro",
        "descripcion": "Cobertura inmediata para lesiones corporales, gastos médicos de emergencia y auxilio funerario.",
        "monto_maximo": None,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Seguro Exequial Familiar",
        "tipo": "seguro",
        "descripcion": "Asistencia integral y cubrimiento de gastos funerarios para la familia.",
        "monto_maximo": None,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Renta por Hospitalización o Cáncer",
        "tipo": "seguro",
        "descripcion": "Apoyo económico directo ante diagnósticos positivos de cáncer o días de internación médica.",
        "monto_maximo": None,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Seguro de Hogar",
        "tipo": "seguro",
        "descripcion": "Respaldo completo para tu vivienda ante robos, incendios o fenómenos naturales.",
        "monto_maximo": None,
        "modalidad": "Anual",
        "activo": True,
    },
    {
        "nombre": "Todo Riesgo Vehículos",
        "tipo": "seguro",
        "descripcion": "Cobertura para carros y motos: choques, hurtos, grúa y conductor elegido. Incluye SOAT.",
        "monto_maximo": None,
        "modalidad": "Anual",
        "activo": True,
    },
    {
        "nombre": "Seguro de Movilidad Sostenible",
        "tipo": "seguro",
        "descripcion": "Pólizas especializadas para proteger bicicletas y patinetas eléctricas.",
        "monto_maximo": None,
        "modalidad": "Anual",
        "activo": True,
    },
    {
        "nombre": "Seguro de Arrendamiento",
        "tipo": "seguro",
        "descripcion": "Respaldo económico ante el incumplimiento en el pago del canon o servicios públicos.",
        "monto_maximo": None,
        "modalidad": "Anual",
        "activo": True,
    },
    {
        "nombre": "Seguro de Vida Deudor",
        "tipo": "seguro",
        "descripcion": "Cancela el saldo de tus deudas vigentes con Colsubsidio en caso de fallecimiento o incapacidad permanente.",
        "monto_maximo": None,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Seguro de Desempleo",
        "tipo": "seguro",
        "descripcion": "Respalda las cuotas de tus créditos contratados en caso de pérdida de empleo o incapacidad temporal.",
        "monto_maximo": None,
        "modalidad": "Mensual",
        "activo": True,
    },
    {
        "nombre": "Seguro de Incendio",
        "tipo": "seguro",
        "descripcion": "Obligatorio para resguardar la infraestructura de los créditos hipotecarios.",
        "monto_maximo": None,
        "modalidad": "Anual",
        "activo": True,
    },
]

PRODUCTS = CREDIT_PRODUCTS + INSURANCE_PRODUCTS

# Sample applications — empty by default. Add manually when needed.
SAMPLE_APPLICATIONS: list[dict] = []


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

async def customer_exists(documento: str) -> bool:
    """Check if a customer with the given document already exists."""
    async with db.async_session_maker() as session:
        result = await session.execute(
            text("SELECT 1 FROM customers WHERE documento_identidad = :doc"),
            {"doc": documento},
        )
        return result.scalar() is not None


async def clear_data() -> None:
    """Delete all data from tables (in dependency order)."""
    logger.info("🧹 Clearing existing data…")
    async with db.async_session_maker() as session:
        tables = [
            "interest_rates", "conversations", "credits", "applications",
            "documents", "sessions", "insurances", "claims", "policies",
            "opportunities", "notifications", "products", "customers",
        ]
        for table in tables:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()
    logger.info("✅ Data cleared")


async def seed() -> None:
    """Main seed routine."""
    # --- Database init ---
    from app.config import Settings

    settings = Settings()
    db.init_engine(settings.database_url, echo=False)

    # Ensure tables exist
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("📦 Tables created / verified")

    parser = argparse.ArgumentParser(description="Seed the database with test data.")
    parser.add_argument("--clear", action="store_true", help="Drop existing data first")
    parser.add_argument("--demo-data", action="store_true", help="Add demo applications, sessions, and policies")
    args, _ = parser.parse_known_args()

    if args.clear:
        await clear_data()

    # --- Customers ---
    created_customers = {}
    for c in CUSTOMERS:
        exists = await customer_exists(c["documento_identidad"])
        if exists:
            logger.info("⏩ Cliente '%s' ya existe — saltando", c["nombre_completo"])
            # Fetch their ID
            async with db.async_session_maker() as session:
                result = await session.execute(
                    text("SELECT id FROM customers WHERE documento_identidad = :doc"),
                    {"doc": c["documento_identidad"]},
                )
                created_customers[c["documento_identidad"]] = result.scalar()
            continue

        async with db.async_session_maker() as session:
            now = datetime.now(timezone.utc)
            categoria = _calcular_categoria(c["salario"])
            result = await session.execute(
                text("""
                    INSERT INTO customers
                        (id, documento_identidad, nombre_completo, email, telefono,
                         salario, tipo_contrato, antiguedad_meses, score_crediticio,
                         categoria_afiliacion, created_at, updated_at)
                    VALUES
                        (lower(hex(randomblob(16))), :doc, :nombre, :email, :tel,
                         :salario, :contrato, :antiguedad, :score,
                         :categoria, :now, :now)
                    RETURNING id
                """),
                {
                    "doc": c["documento_identidad"],
                    "nombre": c["nombre_completo"],
                    "email": c["email"],
                    "tel": c["telefono"],
                    "salario": c["salario"],
                    "contrato": c["tipo_contrato"],
                    "antiguedad": c["antiguedad_meses"],
                    "score": c["score_crediticio"],
                    "categoria": categoria,
                    "now": now,
                },
            )
            cid = result.scalar()
            await session.commit()
            created_customers[c["documento_identidad"]] = cid
            logger.info(
                "✅ Cliente '%s' creado (salario=$%s, antigüedad=%sm, contrato=%s)",
                c["nombre_completo"],
                f"{c['salario']:,.0f}" if c["salario"] else "0",
                c["antiguedad_meses"],
                c["tipo_contrato"] or "N/A",
            )

    # --- Products ---
    product_map = {}
    for p in PRODUCTS:
        async with db.async_session_maker() as session:
            result = await session.execute(
                text("SELECT id FROM products WHERE nombre = :nombre"),
                {"nombre": p["nombre"]},
            )
            existing = result.scalar()
            if existing:
                logger.info("⏩ Producto '%s' ya existe — saltando", p["nombre"])
                product_map[p["nombre"]] = existing
                continue

            now = datetime.now(timezone.utc)
            result = await session.execute(
                text("""
                    INSERT INTO products
                        (id, nombre, tipo, descripcion, monto_maximo, modalidad, activo, created_at, updated_at)
                    VALUES
                        (lower(hex(randomblob(16))), :nombre, :tipo, :desc, :monto_max, :modalidad, 1, :now, :now)
                    RETURNING id
                """),
                {
                    "nombre": p["nombre"],
                    "tipo": p["tipo"],
                    "desc": p["descripcion"],
                    "monto_max": p["monto_maximo"],
                    "modalidad": p["modalidad"],
                    "now": now,
                },
            )
            pid = result.scalar()
            await session.commit()
            product_map[p["nombre"]] = pid
            logger.info("✅ Producto '%s' creado", p["nombre"])

    # --- Interest rates (per category × product) ---
    from datetime import date as _date

    INTEREST_RATES_SEED = [
        ("Crédito Libre Inversión", "libranza", {"A": 12, "B": 15, "C": 18}),
        ("Crédito Libre Inversión", "pago_directo", {"A": 15, "B": 18, "C": 22}),
        ("Compra de Cartera", "libranza", {"A": 12, "B": 15, "C": 18}),
        ("Compra de Cartera", "pago_directo", {"A": 15, "B": 18, "C": 22}),
        ("Crédito para Mujeres", None, {"A": 12, "B": 15, "C": 18}),
        ("Crédito Educativo", None, {"A": 10, "B": 13, "C": 16}),
        ("Crédito Hipotecario", None, {"A": 10.7, "B": 10.7, "C": 10.7}),
        ("Cupo de Crédito (Tarjeta Multiservicios)", None, {"A": 18, "B": 22, "C": 26}),
        ("Microcrédito", None, {"A": 20, "B": 24, "C": 28}),
    ]

    interest_rates_created = 0
    for product_name, modalidad, cats in INTEREST_RATES_SEED:
        pid = product_map.get(product_name)
        if not pid:
            logger.warning("⚠️ Producto '%s' no encontrado — saltando tasas", product_name)
            continue
        for cat, tasa in cats.items():
            # Check if already exists
            async with db.async_session_maker() as session:
                existing = await session.execute(
                    text("""
                        SELECT 1 FROM interest_rates
                        WHERE categoria = :cat
                          AND product_id = :pid
                          AND ((modalidad_pago IS NULL AND :modal IS NULL)
                               OR modalidad_pago = :modal)
                          AND vigencia_desde = :hoy
                    """),
                    {
                        "cat": cat,
                        "pid": pid,
                        "modal": modalidad,
                        "hoy": _date.today(),
                    },
                )
                if existing.scalar():
                    logger.debug(
                        "⏩ InterestRate %s/%s/%s ya existe — saltando",
                        cat, product_name, modalidad or "N/A",
                    )
                    continue

            async with db.async_session_maker() as session:
                await session.execute(
                    text("""
                        INSERT INTO interest_rates
                            (id, categoria, product_id, modalidad_pago,
                             tasa_min, tasa_max, vigencia_desde, activo,
                             created_at, updated_at)
                        VALUES
                            (lower(hex(randomblob(16))), :cat, :pid, :modal,
                             :tasa, :tasa, :hoy, 1, :now, :now)
                    """),
                    {
                        "cat": cat,
                        "pid": pid,
                        "modal": modalidad,
                        "tasa": tasa,
                        "hoy": _date.today(),
                        "now": datetime.now(timezone.utc),
                    },
                )
                await session.commit()
                interest_rates_created += 1

    logger.info("📊 Interest rates creados: %d", interest_rates_created)

    # --- Sample applications (linked to Juan Pérez) ---
    import json as _json

    juan_id = created_customers.get("100000001")
    if juan_id and SAMPLE_APPLICATIONS:
        for i, app_data in enumerate(SAMPLE_APPLICATIONS):
            now = datetime.now(timezone.utc)
            created_at = now.replace(
                day=max(1, min(28, now.day - i * 2))  # spread over the last few days
            )
            async with db.async_session_maker() as session:
                # Use ORM model for proper JSON serialization
                from app.models.application import Application

                app = Application(
                    customer_id=juan_id,
                    tipo=app_data["tipo"],
                    estado=app_data["estado"],
                    form_data=app_data["form_data"],
                    created_at=created_at,
                )
                session.add(app)
                await session.flush()
                app_id = app.id

                # Create linked credit record
                credit = app_data.get("credit")
                if credit:
                    from app.models.credit import Credit

                    cred = Credit(
                        application_id=app_id,
                        monto_solicitado=credit["monto_solicitado"],
                        plazo_meses=credit["plazo_meses"],
                        destino=credit["destino"],
                        tasa_interes=credit["tasa_interes"],
                    )
                    session.add(cred)

                await session.commit()

            logger.info(
                "📄 Solicitud '%s' creada para Juan Pérez (estado=%s, monto=$%s)",
                app_data.get("credit", {}).get("destino", "N/A"),
                app_data["estado"],
                f"{app_data.get('credit', {}).get('monto_solicitado', 0):,.0f}",
            )

    # --- Demo data (optional) ---
    if args.demo_data:
        logger.info("🎲 Sembrando datos demo…")
        await seed_demo_data()

    # --- Summary ---
    async with db.async_session_maker() as session:
        counts = {}
        for table in ["customers", "products", "interest_rates", "applications", "credits", "sessions"]:
            cnt = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = cnt.scalar()

    logger.info("=" * 50)
    logger.info("📊 Resumen final:")
    for table, count in counts.items():
        logger.info(f"   {table}: {count}")
    logger.info("=" * 50)
    logger.info("🌱 Seed completado exitosamente")


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

async def seed_demo_data() -> None:
    """Create demo applications, credits, sessions, conversations, and policies."""
    import random
    from datetime import timedelta as _td
    from app.models.application import Application
    from app.models.credit import Credit
    from app.models.session import Session
    from app.models.conversation import Conversation
    from app.models.policy import Policy
    from app.models.claim import Claim
    from app.models.insurance import Insurance

    # --- Fetch existing customers ---
    async with db.async_session_maker() as session:
        rows = await session.execute(
            text("SELECT id, documento_identidad FROM customers")
        )
        cust_rows = rows.fetchall()
    customer_ids = [r[0] for r in cust_rows]
    if not customer_ids:
        logger.warning("⚠️ No customers found — skipping demo data")
        return
    juan_id = next((r[0] for r in cust_rows if r[1] == "100000001"), customer_ids[0])
    pedro_id = next((r[0] for r in cust_rows if r[1] == "100000002"), customer_ids[-1])

    # --- Fetch credit products ---
    async with db.async_session_maker() as session:
        rows = await session.execute(
            text("SELECT id, nombre FROM products WHERE tipo = 'credito' AND activo = 1")
        )
        credit_products = {r[1]: r[0] for r in rows.fetchall()}

    # --- Generate 25 demo applications ---
    destinos = [
        ("Libre Inversión", 5_000_000, 50_000_000),
        ("Educativo", 3_000_000, 30_000_000),
        ("Vivienda", 20_000_000, 200_000_000),
        ("Compra de Cartera", 10_000_000, 80_000_000),
        ("Mujer Emprendedora", 5_000_000, 30_000_000),
        ("Microcrédito", 1_000_000, 10_000_000),
    ]
    estados = ["iniciada", "iniciada", "iniciada",
               "en_revision", "en_revision",
               "aprobada", "aprobada",
               "rechazada"]

    now = datetime.now(timezone.utc)
    for i in range(25):
        estado = random.choice(estados)
        destino, monto_min, monto_max = random.choice(destinos)
        monto = random.randrange(monto_min, monto_max, 500_000)
        plazo = random.choice([12, 24, 36, 48, 60])
        tasa = round(random.uniform(10.0, 26.0), 2)
        created_at = now - _td(days=random.randint(0, 90))

        # Assign customers: ~60% Juan, ~30% Pedro, ~10% other
        cid = juan_id if random.random() < 0.6 else (pedro_id if random.random() < 0.75 else random.choice(customer_ids))

        async with db.async_session_maker() as session:
            app = Application(
                customer_id=cid,
                tipo="credito",
                estado=estado,
                form_data={
                    "monto_solicitado": monto,
                    "destino": destino,
                    "plazo_meses": plazo,
                },
                created_at=created_at,
            )
            session.add(app)
            await session.flush()

            # Create credit record for approved applications
            if estado == "aprobada":
                cred = Credit(
                    application_id=app.id,
                    monto_solicitado=monto,
                    plazo_meses=plazo,
                    destino=destino,
                    tasa_interes=tasa,
                    modalidad_pago=random.choice(["libranza", "pago_directo"]),
                )
                session.add(cred)

        await session.commit()

    logger.info("📄 25 aplicaciones demo creadas con estados variados")

    # --- Generate 20 sessions with conversations ---
    session_states = ["inicio", "datos_personales", "datos_laborales",
                      "verificacion_identidad", "verificacion_ingresos",
                      "completado"]
    campos_base = {
        "nombre": True, "documento": True, "telefono": True,
        "email": True, "salario": True, "tipo_contrato": True,
        "antiguedad": True, "direccion": True, "ciudad": True,
    }
    section_fields = {
        "inicio": {},
        "datos_personales": {"nombre": True, "documento": True, "telefono": True, "email": True},
        "datos_laborales": {"salario": True, "tipo_contrato": True, "antiguedad": True},
        "verificacion_identidad": {"nombre": True, "documento": True, "telefono": True,
                                    "email": True, "direccion": True, "ciudad": True},
        "verificacion_ingresos": {"nombre": True, "documento": True, "salario": True,
                                   "tipo_contrato": True, "antiguedad": True},
        "completado": dict(campos_base),
    }

    for i in range(20):
        state = random.choice(session_states)
        cid = juan_id if random.random() < 0.6 else (pedro_id if random.random() < 0.75 else random.choice(customer_ids))
        created_at = now - _td(days=random.randint(0, 60))
        campos = section_fields.get(state, {})
        activa = state != "completado"

        async with db.async_session_maker() as session:
            sess = Session(
                customer_id=cid,
                estado_actual=state,
                campos_diligenciados=campos,
                ultima_intencion=random.choice([
                    "solicitar_credito", "consultar_producto",
                    "verificar_estado", "actualizar_datos",
                ]),
                activa=activa,
                created_at=created_at,
            )
            session.add(sess)
            await session.flush()

            # Add 3-8 conversation messages
            msg_count = random.randint(3, 8)
            for mi in range(msg_count):
                rol = "user" if mi % 2 == 0 else "assistant"
                msgs_user = [
                    "Hola, quiero solicitar un crédito",
                    "¿Cuánto puedo pedir?",
                    "Listo, gracias",
                    "Necesito más información",
                    "¿Cuáles son las tasas?",
                    "Quiero comprar vivienda",
                    "Tengo dudas sobre los requisitos",
                    "¿Aceptan libranza?",
                ]
                msgs_assistant = [
                    "¡Claro! Te ayudo a solicitar tu crédito",
                    "Depende de tu capacidad de pago",
                    "Perfecto, continuemos",
                    "Claro, te explico los detalles",
                    "Las tasas dependen de tu categoría",
                    "Excelente, revisemos opciones",
                    "Te cuento los requisitos",
                    "Sí, ofrecemos crédito por libranza",
                ]
                conv = Conversation(
                    session_id=sess.id,
                    rol=rol,
                    mensaje=random.choice(msgs_user if rol == "user" else msgs_assistant),
                    created_at=created_at + _td(minutes=mi * random.randint(1, 5)),
                )
                session.add(conv)

        await session.commit()

    logger.info("💬 20 sesiones demo con conversaciones creadas")

    # --- Seed insurances table ---
    insurance_map = {}
    for ip in INSURANCE_PRODUCTS:
        async with db.async_session_maker() as session:
            existing = await session.execute(
                text("SELECT id FROM insurances WHERE nombre = :nombre"),
                {"nombre": ip["nombre"]},
            )
            row = existing.scalar()
            if row:
                insurance_map[ip["nombre"]] = row
                continue

            ins = Insurance(
                nombre=ip["nombre"],
                cobertura=ip["descripcion"],
                activo=True,
            )
            session.add(ins)
            await session.flush()
            insurance_map[ip["nombre"]] = ins.id
        await session.commit()

    logger.info("🏦 %d seguros registrados en tabla insurances", len(insurance_map))

    # --- Generate 15 policies + claims ---
    policy_states = ["activo", "activo", "activo", "cancelado", "vencido"]
    for i in range(15):
        cid = juan_id if random.random() < 0.6 else (pedro_id if random.random() < 0.75 else random.choice(customer_ids))
        ins_name = random.choice(list(insurance_map.keys()))
        ins_id = insurance_map[ins_name]
        state = random.choice(policy_states)
        created_at = now - _td(days=random.randint(30, 400))

        async with db.async_session_maker() as session:
            policy = Policy(
                customer_id=cid,
                insurance_id=ins_id,
                numero_poliza=f"POL-{1000 + i}",
                prima=round(random.uniform(30_000, 600_000), 2),
                estado=state,
                fecha_inicio=created_at,
                fecha_fin=created_at + _td(days=365) if state == "activo"
                         else created_at + _td(days=random.randint(30, 300)),
            )
            session.add(policy)
            await session.flush()

            # ~30% of active policies have claims
            if state == "activo" and random.random() < 0.3:
                claim = Claim(
                    customer_id=cid,
                    policy_id=policy.id,
                    estado=random.choice(["reportado", "en_estudio", "aprobado", "rechazado"]),
                    descripcion=random.choice([
                        "Accidente personal",
                        "Daños en vivienda",
                        "Gastos médicos",
                        "Hurto de vehículo",
                    ]),
                    monto_reclamado=round(random.uniform(100_000, 5_000_000), 2),
                    fecha_evento=created_at + _td(days=random.randint(30, 200)),
                )
                session.add(claim)

        await session.commit()

    logger.info("🏥 15 pólizas demo + reclamaciones creadas")
    logger.info("🎲 Datos demo completados exitosamente")


if __name__ == "__main__":
    asyncio.run(seed())
