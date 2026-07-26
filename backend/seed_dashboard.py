#!/usr/bin/env python3
"""
Seed script for dashboard — creates 100+ realistic customers with active policies
as if they were attended via chat with Anna. Populates all dashboard metrics.
"""

import asyncio
import uuid
import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select, func

import app.database as db
from app.config import Settings
from app.models.customer import Customer
from app.models.insurance import Insurance
from app.models.policy import Policy
from app.models.product import Product
from app.models.opportunity import Opportunity
from app.models.notification import Notification
from app.models.conversation import Conversation
from app.models.session import Session
from app.models.claim import Claim
from app.models.application import Application
from app.models.credit import Credit
from app.models.document import Document


async def seed_dashboard():
    settings = Settings()
    db.init_engine(settings.database_url, echo=False)

    # Colombian names for realism
    nombres = [
        "María", "Carlos", "Ana", "Luis", "Sofía", "Jorge", "Patricia", "Andrés",
        "Valentina", "Miguel", "Camila", "Alejandro", "Isabella", "Diego", "Mariana",
        "Sebastián", "Daniela", "Felipe", "Gabriela", "Ricardo", "Natalia", "Fernando",
        "Paula", "Julián", "Laura", "Santiago", "Carolina", "Nicolás", "Andrea", "Martín",
        "Juliana", "Samuel", "Victoria", "Emilio", "Ana María", "Juan", "Claudia", "Roberto",
        "Adriana", "Óscar", "Mónica", "Hernando", "Sandra", "Gustavo", "Liliana", "Jaime",
        "Yolanda", "Álvaro", "Beatriz", "Raúl", "Gloria", "Eduardo", "Teresa", "Víctor",
        "Rosa", "Javier", "Amparo", "Guillermo", "Inés", "Mauricio", "Pilar", "Rodrigo",
        "Silvia", "Alberto", "Norma", "César", "Alicia", "Rafael", "Estela", "Antonio",
        "Miriam", "Gerardo", "Consuelo", "Enrique", "Luz", "Pablo", "Marta", "Ignacio",
        "Aurora", "Alfredo", "Nancy", "Fernando", "Elena", "Domingo", "Rita", "Salvador",
        "Irene", "Ramón", "Celia", "Ángel", "Mercedes", "Roberto", "Flor", "Joaquín"
    ]
    
    apellidos = [
        "García", "Rodríguez", "González", "Martínez", "López", "Hernández", "Pérez",
        "Sánchez", "Ramírez", "Torres", "Flores", "Rivera", "Gómez", "Díaz", "Reyes",
        "Moreno", "Álvarez", "Romero", "Herrera", "Medina", "Castro", "Ortiz", "Rubio",
        "Delgado", "Suárez", "Ortega", "Jiménez", "Molina", "Navarro", "Guerrero", "Rojas",
        "Cabrera", "Fuentes", "Carrillo", "Aguilar", "Santana", "Vargas", "Mendoza",
        "Cortés", "Cruz", "Peña", "Flores", "Herrera", "Medina", "Vega", "Mora"
    ]

    ciudades = [
        ("Bogotá", "+57310", "Cundinamarca"),
        ("Medellín", "+57311", "Antioquia"),
        ("Cali", "+57312", "Valle"),
        ("Barranquilla", "+57313", "Atlántico"),
        ("Cartagena", "+57314", "Bolívar"),
        ("Bucaramanga", "+57315", "Santander"),
        ("Pereira", "+57316", "Risaralda"),
        ("Manizales", "+57317", "Caldas"),
        ("Cúcuta", "+57318", "Norte Santander"),
        ("Ibagué", "+57319", "Tolima"),
    ]

    tipos_contrato = ["indefinido", "termino_fijo", "obra_labor", "prestacion_servicios"]
    ocupaciones = [
        "Ingeniero", "Profesor", "Contador", "Abogado", "Médico", "Enfermero",
        "Administrador", "Arquitecto", "Diseñador", "Programador", "Analista",
        "Gerente", "Supervisor", "Técnico", "Operario", "Conductor", "Vendedor",
        "Comerciante", "Ama de casa", "Estudiante", "Pensionado", "Independiente"
    ]
    estados_civiles = ["soltero", "casado", "union_libre", "divorciado", "viudo"]
    segmentos = ["A1", "A2", "B1", "B2", "B3", "C1", "C2", "C3"]

    async with db.async_session_maker() as session:
        # ─── Clean test data ───
        print("Cleaning test data...")
        await session.execute(delete(Notification))
        await session.execute(delete(Opportunity))
        await session.execute(delete(Claim))
        await session.execute(delete(Credit))
        await session.execute(delete(Application))
        await session.execute(delete(Document))
        await session.execute(delete(Conversation))
        await session.execute(delete(Session))
        await session.execute(delete(Policy))
        await session.execute(delete(Customer))
        await session.commit()

        # ─── Create Insurance Products ───
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
            Product(
                id=str(uuid.uuid4()),
                nombre="Crédito Hipotecario",
                tipo="credito",
                descripcion="Crédito para compra de vivienda nueva o usada",
                monto_maximo=500000000,
                modalidad="hipotecario",
                activo=True,
            ),
        ]
        for prod in products:
            session.add(prod)
        await session.commit()

        # ─── Create 100+ Customers with Policies ───
        print("Creating 120 customers with active policies...")
        
        customers = []
        policies = []
        conversations = []
        sessions = []
        claims = []
        
        # Pre-fetch insurance IDs by category
        ins_by_cat = {ins.insurance_category: ins.id for ins in insurances}
        
        for i in range(120):
            # Pick name
            nombre = random.choice(nombres)
            apellido = f"{random.choice(apellidos)} {random.choice(apellidos)}"
            nombre_completo = f"{nombre} {apellido}"
            
            # City
            ciudad, tel_prefijo, depto = random.choice(ciudades)
            
            # Documento (Colombian format)
            doc = f"{random.randint(10000000, 99999999)}"
            
            # Phone
            telefono = f"{tel_prefijo}{random.randint(1000000, 9999999)}"
            
            # Email
            email_base = f"{nombre.lower()}.{apellido.lower().replace(' ', '.')}"
            email = f"{email_base}{random.randint(1, 999)}@email.com"
            
            # Financial profile
            salario = round(random.uniform(1500000, 12000000), -3)  # 1.5M - 12M
            tipo_contrato = random.choices(tipos_contrato, weights=[0.6, 0.2, 0.1, 0.1])[0]
            if tipo_contrato == "indefinido":
                antiguedad = random.randint(2, 240)  # 2 months to 20 years
            else:
                antiguedad = random.randint(6, 120)
            
            score = round(random.uniform(0.55, 0.98), 2)
            
            # Category based on salary
            if salario > 4500000:
                categoria = "A"
            elif salario > 2000000:
                categoria = "B"
            else:
                categoria = "C"
            
            ocupacion = random.choice(ocupaciones)
            num_hijos = random.randint(0, 4)
            estado_civil = random.choices(estados_civiles, weights=[0.45, 0.4, 0.1, 0.03, 0.02])[0]
            segmento = random.choice(segmentos)
            
            customer = Customer(
                id=str(uuid.uuid4()),
                documento_identidad=doc,
                nombre_completo=nombre_completo,
                email=email,
                telefono=telefono,
                salario=salario,
                tipo_contrato=tipo_contrato,
                antiguedad_meses=antiguedad,
                score_crediticio=score,
                categoria_afiliacion=categoria,
                ocupacion=ocupacion,
                numero_hijos=num_hijos,
                estado_civil=estado_civil,
                tipo_empleado="dependiente" if tipo_contrato != "prestacion_servicios" else "independiente",
                segmento_grupo_familiar=segmento,
            )
            customers.append(customer)
            session.add(customer)
        
        await session.commit()
        print(f"Created {len(customers)} customers")

        # ─── Create Policies (most customers have 1-2 policies) ───
        print("Creating active policies...")
        for customer in customers:
            # 85% have at least one policy
            if random.random() < 0.85:
                num_policies = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
                chosen_cats = random.sample(list(ins_by_cat.keys()), min(num_policies, len(ins_by_cat)))
                
                for cat in chosen_cats:
                    ins_id = ins_by_cat[cat]
                    ins = next(i for i in insurances if i.id == ins_id)
                    
                    # Policy start: 1-24 months ago
                    days_ago = random.randint(30, 730)
                    fecha_inicio = datetime.utcnow() - timedelta(days=days_ago)
                    
                    # Some policies expired (10%)
                    if random.random() < 0.1:
                        estado = "vencido"
                        fecha_fin = fecha_inicio + timedelta(days=random.randint(30, 365))
                    else:
                        estado = "activo"
                        fecha_fin = fecha_inicio + timedelta(days=365 * random.randint(1, 3))
                    
                    # Prima varies ±20% from base
                    prima = int(ins.prima_base * random.uniform(0.8, 1.2))
                    
                    policy = Policy(
                        id=str(uuid.uuid4()),
                        customer_id=customer.id,
                        insurance_id=ins_id,
                        numero_poliza=f"POL-{cat[:3].upper()}-{random.randint(100000, 999999)}",
                        prima=prima,
                        estado=estado,
                        fecha_inicio=fecha_inicio,
                        fecha_fin=fecha_fin if estado == "vencido" else None,
                    )
                    policies.append(policy)
                    session.add(policy)
            
            # 30% also have a credit
            if random.random() < 0.30:
                prod_credito = random.choice(products)
                monto = random.randint(5000000, min(int(customer.salario * 15), prod_credito.monto_maximo or 50000000))
                plazo = random.choice([12, 18, 24, 36, 48, 60, 72])
                
                app = Application(
                    id=str(uuid.uuid4()),
                    customer_id=customer.id,
                    product_id=prod_credito.id,
                    tipo="credito",
                    estado="aprobado",
                    form_data={
                        "monto_solicitado": monto,
                        "plazo_meses": plazo,
                        "destino": prod_credito.modalidad
                    },
                    created_at=datetime.utcnow() - timedelta(days=random.randint(30, 500)),
                )
                session.add(app)
                await session.flush()
                
                credit = Credit(
                    id=str(uuid.uuid4()),
                    application_id=app.id,
                    monto_solicitado=monto,
                    plazo_meses=plazo,
                    destino=prod_credito.modalidad,
                    tasa_interes=round(random.uniform(0.18, 0.32), 4),
                    modalidad_pago="mensual",
                )
                session.add(credit)
        
        await session.commit()
        print(f"Created {len(policies)} policies")

        # ─── Create Conversation History (simulate chat with Anna) ───
        print("Creating conversation history...")
        for customer in customers:
            # 70% have chat history
            if random.random() < 0.7:
                num_sessions = random.randint(1, 3)
                for _ in range(num_sessions):
                    sess = Session(
                        id=str(uuid.uuid4()),
                        customer_id=customer.id,
                        estado_actual=random.choice(["perfilando", "recomendando", "cotizando", "recopilando_datos_seguro", "completado_seguro"]),
                        activa=random.random() < 0.2,  # 20% active
                        insurance_profile={"product_context": random.choice(list(ins_by_cat.keys()))},
                        campos_diligenciados={},
                        ultima_intencion="recopilando_datos_seguro",
                    )
                    sessions.append(sess)
                    session.add(sess)
                
                await session.flush()
                
                # Create conversations for each session
                for sess in sessions[-num_sessions:]:
                    num_msgs = random.randint(4, 12)
                    for j in range(num_msgs):
                        if j % 2 == 0:
                            # User message
                            rol = "user"
                            msgs_user = [
                                "Hola", "Quiero un seguro", "Para mi familia", "Mi nombre es " + customer.nombre_completo.split()[0],
                                "Tengo 2 hijos", "Vivo en casa propia", "Mi salario es " + str(int(customer.salario)),
                                "Quiero saber precios", "Me interesa ese", "Sí acepto", "Mi documento es " + customer.documento_identidad
                            ]
                            contenido = random.choice(msgs_user)
                        else:
                            # Assistant (Anna) message
                            rol = "assistant"
                            msgs_anna = [
                                f"¡Hola! Soy Anna, tu asesora de Colsubsidio. ¿En qué te puedo ayudar?",
                                f"¿Qué te gustaría proteger? Tu familia, tu vehículo, tu hogar...",
                                f"Perfecto, {customer.nombre_completo.split()[0]}. Para recomendarte lo mejor necesito saber un poco más.",
                                f"Entendido. Teniendo en cuenta tu perfil, te recomiendo un seguro de vida familiar.",
                                f"El plan estándar sale a $38.000 mensuales. ¿Te gustaría cotizar?",
                                f"Genial. Para la póliza necesito tu número de documento.",
                                f"Gracias. Antes de continuar, debes aceptar el tratamiento de datos... ¿Aceptas?",
                                f"¡Listo, {customer.nombre_completo.split()[0]}! Tu póliza ya está activa.",
                            ]
                            contenido = random.choice(msgs_anna)
                        
                        conv = Conversation(
                            session_id=sess.id,
                            rol=rol,
                            mensaje=contenido,
                        )
                        conversations.append(conv)
                        session.add(conv)
        
        await session.commit()
        print(f"Created {len(sessions)} sessions and {len(conversations)} messages")

        # ─── Create some Claims (siniestros) ───
        print("Creating claims...")
        active_policies = [p for p in policies if p.estado == "activo"]
        for policy in random.sample(active_policies, min(15, len(active_policies))):
            claim = Claim(
                id=str(uuid.uuid4()),
                customer_id=policy.customer_id,
                policy_id=policy.id,
                estado=random.choice(["reportado", "en_revision", "aprobado", "pagado", "rechazado"]),
                descripcion=f"Siniestro reportado el {datetime.now().strftime('%Y-%m-%d')}",
                monto_reclamado=random.randint(500000, 50000000),
                fecha_evento=datetime.now() - timedelta(days=random.randint(1, 180)),
            )
            claims.append(claim)
            session.add(claim)
        
        await session.commit()
        print(f"Created {len(claims)} claims")

        # ─── Summary for Dashboard ───
        print("\n=== DASHBOARD SUMMARY ===")
        
        # Total customers
        result = await session.execute(select(func.count(Customer.id)))
        print(f"Total clientes: {result.scalar()}")
        
        # Active policies
        result = await session.execute(select(func.count(Policy.id)).where(Policy.estado == "activo"))
        print(f"Pólizas activas: {result.scalar()}")
        
        # Policies by category
        result = await session.execute(
            select(Insurance.insurance_category, func.count(Policy.id))
            .join(Policy, Policy.insurance_id == Insurance.id)
            .where(Policy.estado == "activo")
            .group_by(Insurance.insurance_category)
        )
        for cat, count in result.all():
            print(f"  {cat}: {count}")
        
        # Active credits
        result = await session.execute(select(func.count(Credit.id)))
        print(f"Créditos: {result.scalar()}")
        
        # Conversations
        result = await session.execute(select(func.count(Conversation.id)))
        print(f"Mensajes de chat: {result.scalar()}")
        
        # Claims
        result = await session.execute(select(func.count(Claim.id)))
        print(f"Siniestros: {result.scalar()}")
        
        # Pipeline (opportunities)
        result = await session.execute(select(func.count(Opportunity.id)))
        print(f"Oportunidades: {result.scalar()}")
        
        # Recent notifications
        result = await session.execute(select(func.count(Notification.id)).where(Notification.tipo == "wpp"))
        print(f"Notificaciones outbound: {result.scalar()}")

    await db.dispose_engine()
    print("\n✅ Dashboard seed completed!")


if __name__ == "__main__":
    asyncio.run(seed_dashboard())