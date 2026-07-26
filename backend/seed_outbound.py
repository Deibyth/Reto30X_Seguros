#!/usr/bin/env python3
"""
Seed script for outbound testing — creates diverse customers, insurance products,
opportunities, and policies to test specific product mentions in outbound messages.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.database as db
from app.config import Settings
from app.models.customer import Customer
from app.models.insurance import Insurance
from app.models.opportunity import Opportunity
from app.models.policy import Policy
from app.models.product import Product


async def seed_outbound_data():
    settings = Settings()
    db.init_engine(settings.database_url, echo=False)

    async with db.async_session_maker() as session:
        # ─── Clean up existing test data ───
        print("Cleaning up existing data...")
        await session.execute(delete(Notification))
        await session.execute(delete(Policy))
        await session.execute(delete(Opportunity))
        await session.execute(delete(Insurance))
        await session.execute(delete(Product))
        await session.execute(delete(Customer))
        await session.commit()

        # ─── Create Insurance Products (one per category) ───
        print("Creating insurance products...")
        insurances = [
            Insurance(
                id=str(uuid.uuid4()),
                nombre="Seguro de Movilidad Total",
                cobertura="Cobertura para vehículo, moto y bicicleta. Daños a terceros, robo total/parcial, asistencia en ruta.",
                publico_objetivo="Propietarios de vehículos y motos",
                insurance_category="movilidad",
                prima_base=45000,
                activo=True,
            ),
            Insurance(
                id=str(uuid.uuid4()),
                nombre="Seguro de Vida Familiar",
                cobertura="Fallecimiento, invalidez total/parcial, auxilio funerario, enfermedades graves. Cobertura familiar opcional.",
                publico_objetivo="Jefes de hogar, padres de familia",
                insurance_category="vida",
                prima_base=38000,
                activo=True,
            ),
            Insurance(
                id=str(uuid.uuid4()),
                nombre="Seguro de Hogar Completo",
                cobertura="Incendio, robo, daños por agua, responsabilidad civil, asistencia hogar 24/7. Casa o apartamento.",
                publico_objetivo="Propietarios y arrendatarios",
                insurance_category="hogar",
                prima_base=28000,
                activo=True,
            ),
            Insurance(
                id=str(uuid.uuid4()),
                nombre="Seguro para Mascotas Premium",
                cobertura="Veterinaria, cirugías, medicamentos, vacunas, responsabilidad civil. Perros y gatos hasta 10 años.",
                publico_objetivo="Dueños de perros y gatos",
                insurance_category="mascotas",
                prima_base=32000,
                activo=True,
            ),
            Insurance(
                id=str(uuid.uuid4()),
                nombre="Seguro de Viajes Internacional",
                cobertura="Asistencia médica internacional, cancelación de viaje, equipaje, repatriación. Mundial exceptuar países en conflicto.",
                publico_objetivo="Viajeros frecuentes, familias en vacaciones",
                insurance_category="viajes",
                prima_base=25000,
                activo=True,
            ),
            Insurance(
                id=str(uuid.uuid4()),
                nombre="Seguro de Accidentes Personales",
                cobertura="Muerte accidental, invalidez total/parcial, gastos médicos por accidente, auxilio funerario. 24/7 mundial.",
                publico_objetivo="Trabajadores independientes, deportistas, cabeza de familia",
                insurance_category="accidentes",
                prima_base=22000,
                activo=True,
            ),
        ]

        for ins in insurances:
            session.add(ins)
        await session.commit()
        print(f"Created {len(insurances)} insurance products")

        # ─── Create Financial Products ───
        print("Creating financial products...")
        products = [
            Product(
                id=str(uuid.uuid4()),
                nombre="Crédito Libre Inversión",
                tipo="credito",
                descripcion="Crédito de libre destino, hasta $50M, plazo hasta 72 meses",
                monto_maximo=50000000,
                modalidad="libre_inversion",
                activo=True,
            ),
            Product(
                id=str(uuid.uuid4()),
                nombre="Crédito Vehículo",
                tipo="credito",
                descripcion="Financiación para compra de carro o moto nuevo/usado",
                monto_maximo=120000000,
                modalidad="vehiculo",
                activo=True,
            ),
        ]

        for prod in products:
            session.add(prod)
        await session.commit()

        # ─── Create Diverse Customers ───
        print("Creating customers...")
        customers_data = [
            # 1. Cliente con hijos - ideal para vida
            Customer(
                id="cust-vida-001",
                documento_identidad="1001001001",
                nombre_completo="María González",
                email="maria.gonzalez@email.com",
                telefono="+573101234567",
                salario=3500000,
                tipo_contrato="indefinido",
                antiguedad_meses=36,
                score_crediticio=0.82,
                categoria_afiliacion="B",
                ocupacion="Profesora",
                numero_hijos=2,
                estado_civil="casado",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="familia_4",
            ),
            # 2. Cliente con mascota
            Customer(
                id="cust-mascota-001",
                documento_identidad="1001001002",
                nombre_completo="Carlos Rodríguez",
                email="carlos.rodriguez@email.com",
                telefono="+573112345678",
                salario=2800000,
                tipo_contrato="indefinido",
                antiguedad_meses=24,
                score_crediticio=0.75,
                categoria_afiliacion="B",
                ocupacion="Ingeniero",
                numero_hijos=0,
                estado_civil="soltero",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="single",
            ),
            # 3. Cliente con vehículo
            Customer(
                id="cust-movilidad-001",
                documento_identidad="1001001003",
                nombre_completo="Ana Martínez",
                email="ana.martinez@email.com",
                telefono="+573123456789",
                salario=4200000,
                tipo_contrato="indefinido",
                antiguedad_meses=48,
                score_crediticio=0.88,
                categoria_afiliacion="A",
                ocupacion="Gerente",
                numero_hijos=1,
                estado_civil="casado",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="familia_3",
            ),
            # 4. Cliente con hogar propio
            Customer(
                id="cust-hogar-001",
                documento_identidad="1001001004",
                nombre_completo="Luis Fernando",
                email="luis.fernando@email.com",
                telefono="+573134567890",
                salario=5500000,
                tipo_contrato="indefinido",
                antiguedad_meses=60,
                score_crediticio=0.91,
                categoria_afiliacion="A",
                ocupacion="Arquitecto",
                numero_hijos=2,
                estado_civil="casado",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="familia_4",
            ),
            # 5. Cliente viajero
            Customer(
                id="cust-viajes-001",
                documento_identidad="1001001005",
                nombre_completo="Sofía Herrera",
                email="sofia.herrera@email.com",
                telefono="+573145678901",
                salario=3800000,
                tipo_contrato="indefinido",
                antiguedad_meses=18,
                score_crediticio=0.78,
                categoria_afiliacion="B",
                ocupacion="Consultora",
                numero_hijos=0,
                estado_civil="soltera",
                tipo_empleado="independiente",
                segmento_grupo_familiar="single",
            ),
            # 6. Cliente para accidentes (trabajo riesgo)
            Customer(
                id="cust-accidentes-001",
                documento_identidad="1001001006",
                nombre_completo="Jorge Ramírez",
                email="jorge.ramirez@email.com",
                telefono="+573156789012",
                salario=3200000,
                tipo_contrato="indefinido",
                antiguedad_meses=30,
                score_crediticio=0.72,
                categoria_afiliacion="B",
                ocupacion="Técnico en mantenimiento",
                numero_hijos=1,
                estado_civil="casado",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="familia_3",
            ),
            # 7. Cliente sin hijos, soltero - crédito
            Customer(
                id="cust-credito-001",
                documento_identidad="1001001007",
                nombre_completo="Valentina Pérez",
                email="valentina.perez@email.com",
                telefono="+573167890123",
                salario=4800000,
                tipo_contrato="indefinido",
                antiguedad_meses=42,
                score_crediticio=0.85,
                categoria_afiliacion="A",
                ocupacion="Abogada",
                numero_hijos=0,
                estado_civil="soltera",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="single",
            ),
            # 8. Cliente con contrato fijo - antigüedad justa
            Customer(
                id="cust-credito-002",
                documento_identidad="1001001008",
                nombre_completo="Andrés López",
                email="andres.lopez@email.com",
                telefono="+573178901234",
                salario=2600000,
                tipo_contrato="termino_fijo",
                antiguedad_meses=8,
                score_crediticio=0.68,
                categoria_afiliacion="C",
                ocupacion="Operario",
                numero_hijos=1,
                estado_civil="union_libre",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="familia_3",
            ),
            # 9. Cliente que ya tiene seguro de vida (para testear filtro)
            Customer(
                id="cust-con-vida-001",
                documento_identidad="1001001009",
                nombre_completo="Patricia Silva",
                email="patricia.silva@email.com",
                telefono="+573189012345",
                salario=4100000,
                tipo_contrato="indefinido",
                antiguedad_meses=54,
                score_crediticio=0.87,
                categoria_afiliacion="A",
                ocupacion="Médica",
                numero_hijos=2,
                estado_civil="casado",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="familia_4",
            ),
            # 10. Cliente original (Deibith) - mantener
            Customer(
                id="deibith-001",
                documento_identidad="1001001010",
                nombre_completo="Deibith",
                email="deibith@email.com",
                telefono="+573176529013",
                salario=2500000,
                tipo_contrato="indefinido",
                antiguedad_meses=12,
                score_crediticio=0.85,
                categoria_afiliacion="B",
                ocupacion="Empleado",
                numero_hijos=0,
                estado_civil="soltero",
                tipo_empleado="dependiente",
                segmento_grupo_familiar="single",
            ),
        ]

        for cust in customers_data:
            session.add(cust)
        await session.commit()
        print(f"Created {len(customers_data)} customers")

        # ─── Create Opportunities (one per customer, matching their profile) ───
        print("Creating opportunities...")
        opportunities = [
            # María → Vida (tiene hijos)
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-vida-001",
                tipo="vida",
                estado="pendiente",
                descripcion="Cliente con hijos, ideal para seguro de vida familiar",
                score=0.92,
            ),
            # Carlos → Mascotas
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-mascota-001",
                tipo="mascotas",
                estado="pendiente",
                descripcion="Cliente soltero, probable dueño de mascota",
                score=0.85,
            ),
            # Ana → Movilidad
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-movilidad-001",
                tipo="movilidad",
                estado="pendiente",
                descripcion="Cliente con buen ingreso, probable propietario de vehículo",
                score=0.88,
            ),
            # Luis → Hogar
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-hogar-001",
                tipo="hogar",
                estado="pendiente",
                descripcion="Cliente propietario, ingreso alto",
                score=0.90,
            ),
            # Sofía → Viajes
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-viajes-001",
                tipo="viajes",
                estado="pendiente",
                descripcion="Cliente viajero frecuente, independiente",
                score=0.83,
            ),
            # Jorge → Accidentes
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-accidentes-001",
                tipo="accidentes",
                estado="pendiente",
                descripcion="Trabajo con riesgo físico, necesita protección",
                score=0.87,
            ),
            # Valentina → Crédito
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-credito-001",
                tipo="credito",
                estado="pendiente",
                descripcion="Buen perfil crediticio, sin deudas",
                score=0.89,
            ),
            # Andrés → Crédito (contrato fijo, pero antigüedad ok)
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-credito-002",
                tipo="credito",
                estado="pendiente",
                descripcion="Perfil moderado, contrato a término fijo",
                score=0.70,
            ),
            # Patricia ya tiene vida → Crédito
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="cust-con-vida-001",
                tipo="credito",
                estado="pendiente",
                descripcion="Ya tiene seguro de vida, ofrecer crédito",
                score=0.86,
            ),
            # Deibith → Seguro (genérico)
            Opportunity(
                id=str(uuid.uuid4()),
                customer_id="deibith-001",
                tipo="seguro",
                estado="pendiente",
                descripcion="Cliente base, ofrecer seguro según perfil",
                score=0.75,
            ),
        ]

        for opp in opportunities:
            session.add(opp)
        await session.commit()
        print(f"Created {len(opportunities)} opportunities")

        # ─── Create Policies (some customers already have insurance) ───
        print("Creating policies...")
        # Patricia ya tiene seguro de vida
        vida_insurance = await session.execute(
            select(Insurance).where(Insurance.insurance_category == "vida")
        )
        vida_ins = vida_insurance.scalar_one()

        policies = [
            Policy(
                id=str(uuid.uuid4()),
                customer_id="cust-con-vida-001",
                insurance_id=vida_ins.id,
                numero_poliza=f"POL-VIDA-{uuid.uuid4().hex[:8].upper()}",
                prima=38000,
                estado="activo",
                fecha_inicio=datetime.utcnow() - timedelta(days=120),
            ),
        ]

        for pol in policies:
            session.add(pol)
        await session.commit()
        print(f"Created {len(policies)} policies")

        # ─── Verify outbound will work ───
        print("\n=== OUTBOUND PREVIEW ===")
        for cust in customers_data:
            # Check what opportunity they have
            opp_result = await session.execute(
                select(Opportunity).where(Opportunity.customer_id == cust.id)
            )
            opp = opp_result.scalar_one_or_none()
            
            # Check if they have policies
            pol_result = await session.execute(
                select(Policy).where(Policy.customer_id == cust.id)
            )
            has_policy = pol_result.scalar_one_or_none() is not None
            
            product_type = opp.tipo if opp else "seguro"
            label = {
                "movilidad": "seguro de movilidad (vehículo/moto)",
                "vida": "seguro de vida",
                "hogar": "seguro de hogar",
                "mascotas": "seguro para mascotas",
                "viajes": "seguro de viajes",
                "accidentes": "seguro de accidentes personales",
                "credito": "crédito",
                "seguro": "seguro",
            }.get(product_type, "seguro")
            
            status = "TIENE PÓLIZA" if has_policy else "SIN PÓLIZA"
            print(f"  {cust.nombre_completo:20s} → {label:40s} [{status}]")

    await db.dispose_engine()
    print("\n✅ Seed completed successfully!")


# Import here to avoid circular
from app.models.notification import Notification

if __name__ == "__main__":
    asyncio.run(seed_outbound_data())