"""OutboundService — proactive WhatsApp outreach for credit and insurance."""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import AIClient
from app.services.tts import TTSService
from app.models.application import Application
from app.models.credit import Credit
from app.models.customer import Customer
from app.models.notification import Notification
from app.models.opportunity import Opportunity
from app.models.policy import Policy

SMMLV = 1_423_500


@dataclass
class Prospect:
    customer: Customer
    recommended_product_type: str
    opportunity: Optional[Opportunity] = None
    score: float = 0.0


class OutboundService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        ai_client: Optional[AIClient] = None,
        tts_service: Optional["TTSService"] = None,
    ):
        self._session_maker = session_maker
        self._ai_client = ai_client
        self._tts_service = tts_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def select_prospects(self, limit: int = 50) -> list[Prospect]:
        async with self._session_maker() as session:
            cutoff_30d = datetime.utcnow() - timedelta(days=30)

            # 1. Single query: all potentially eligible customers
            customers = (
                (
                    await session.execute(
                        select(Customer).where(
                            Customer.salario.isnot(None),
                            Customer.salario >= SMMLV,
                            Customer.score_crediticio.isnot(None),
                            Customer.score_crediticio >= 0.0,
                        )
                    )
                )
                .scalars()
                .all()
            )

            if not customers:
                return []

            customer_ids = [c.id for c in customers]

            # 2. Batch: Policies for all candidates
            policy_rows = (
                (
                    await session.execute(
                        select(Policy.customer_id).where(
                            Policy.customer_id.in_(customer_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
            customers_with_policy = set(policy_rows)

            # 3. Batch: Credits (via Application) — used for both product check
            #    and debt-margin calculation
            credit_details = (
                (
                    await session.execute(
                        select(
                            Credit.monto_solicitado,
                            Credit.plazo_meses,
                            Application.customer_id,
                        ).join(
                            Application,
                            Credit.application_id == Application.id,
                        ).where(
                            Application.customer_id.in_(customer_ids)
                        )
                    )
                )
                .all()
            )
            customers_with_credit: set[str] = set()
            debt_payments: dict[str, float] = {}
            for monto, plazo, cust_id in credit_details:
                customers_with_credit.add(cust_id)
                if plazo and plazo > 0:
                    monthly = monto / plazo
                    debt_payments[cust_id] = (
                        debt_payments.get(cust_id, 0) + monthly
                    )

            # 4. Batch: recent Notifications (last 30d)
            recent_notif_rows = (
                (
                    await session.execute(
                        select(Notification.customer_id).where(
                            Notification.customer_id.in_(customer_ids),
                            Notification.created_at >= cutoff_30d,
                        )
                    )
                )
                .scalars()
                .all()
            )
            customers_with_recent_notif = set(recent_notif_rows)

            # 5. Batch: pending Opportunities ordered by score desc
            opp_rows = (
                (
                    await session.execute(
                        select(Opportunity).where(
                            Opportunity.customer_id.in_(customer_ids),
                            Opportunity.estado == "pendiente",
                        ).order_by(
                            Opportunity.customer_id,
                            Opportunity.score.desc().nullslast(),
                        )
                    )
                )
                .scalars()
                .all()
            )
            # Keep the highest-scored opportunity per customer
            best_opp: dict[str, Opportunity] = {}
            for opp in opp_rows:
                if opp.customer_id not in best_opp:
                    best_opp[opp.customer_id] = opp

            # 6. Per-customer checks in Python (no N+1)
            prospects: list[Prospect] = []
            for customer in customers:
                if not self._is_eligible_contract(customer):
                    continue

                # Debt margin: exclude if existing commitments exceed 50 % of salary
                estimated_payment = debt_payments.get(customer.id, 0.0)
                if estimated_payment > customer.salario * 0.5:
                    continue

                # Si ya tiene una póliza activa, no contactar — es cliente existente
                if customer.id in customers_with_policy:
                    continue

                product_type = "seguro"

                if customer.id in customers_with_recent_notif:
                    continue

                opportunity = best_opp.get(customer.id)
                if opportunity:
                    product_type = opportunity.tipo

                prospects.append(
                    Prospect(
                        customer=customer,
                        recommended_product_type=product_type,
                        opportunity=opportunity,
                        score=opportunity.score if opportunity else 0.0,
                    )
                )

            prospects.sort(key=lambda p: p.score, reverse=True)
            return prospects[:limit]

    @staticmethod
    def _product_type_to_label(product_type: str) -> str:
        """Convert internal product type to user-friendly label."""
        labels = {
            "movilidad": "seguro de movilidad (vehículo/moto)",
            "vida": "seguro de vida",
            "hogar": "seguro de hogar",
            "mascotas": "seguro para mascotas",
            "viajes": "seguro de viajes",
            "accidentes": "seguro de accidentes personales",
            "credito": "crédito",
        }
        return labels.get(product_type, "seguro")

    async def generate_message(self, prospect: Prospect) -> str:
        content = ""
        product_label = self._product_type_to_label(prospect.recommended_product_type)
        
        if self._ai_client:
            try:
                system_prompt = (
                    f"Eres Anna, asesora de Colsubsidio. "
                    f"Genera un mensaje corto y natural para WhatsApp dirigido a "
                    f"{prospect.customer.nombre_completo}. "
                    f"El mensaje debe comunicar ESPECÍFICAMENTE que revisando su perfil "
                    f"encontramos viabilidad para {product_label}. "
                    f"DEBES MENCIONAR EL TIPO EXACTO DE SEGURO en el mensaje. "
                    f"Ejemplo: '...viabilidad para un seguro de vida...' o "
                    f"'...viabilidad para un seguro de hogar...' "
                    f"Natural, cálido, con energía positiva. "
                    f"Usa signos de admiración y emoción para transmitir calidez y entusiasmo. "
                    f"Ejemplo: '¡Qué alegría saludarte!' o '¡Me encanta poder contarte esto!' "
                    f"No preguntes datos que ya tengamos del cliente. "
                    f"Máximo 180 caracteres. "
                    f"IMPORTANTE: El mensaje DEBE empezar con: "
                    f"'Hola [nombre], soy Anna, tu asesora de Colsubsidio. "
                    f"o una variacion natural similar que siempre incluya "
                    f"tu nombre y el de la persona. "
                    f"Debe cerrar de forma amable y cálida, algo como: "
                    f"'¡Si te interesa, aquí estoy para lo que necesites! 😊' "
                    f"No hagas preguntas directas de momento. "
                    f"NO incluyas 'STOP' ni 'responder STOP' ni 'darse de baja'. "
                    f"TONO: Usa SIEMPRE 'tú' (tuteo colombiano neutro). "
                    f"NUNCA uses 'vos', 'contás', 'tenés' ni voseo. "
                    f"VARIEDAD: No repitas la misma estructura en cada mensaje. "
                    f"Alterna las aperturas y cierres para que no suene a plantilla."
                )
                result = await self._ai_client.chat_raw(
                    openai_messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"Genera un mensaje para {prospect.customer.nombre_completo} "
                            f"ofreciendo {product_label}. Menciona explícitamente el tipo de seguro.",
                        },
                    ],
                )
                if result and result.reply:
                    content = result.reply.strip()
            except Exception:
                pass

        if not content:
            name = prospect.customer.nombre_completo or "cliente"
            content = (
                f"¡Hola {name}! Soy Anna, tu asesora de Colsubsidio."
                f" ¡Revisamos tu perfil y encontramos viabilidad para {product_label}!"
                f" Si te interesa, aquí estoy para lo que necesites. ¡Me encantaría ayudarte!"
            )

        return content

    async def create_notification(
        self, prospect: Prospect, content: str
    ) -> Notification:
        # Generate TTS audio for outbound prospect messages
        audio_url: str | None = None
        if self._tts_service and content:
            try:
                # Reemplazar "Anna" por "Ana" solo para el audio (TTS pronuncia natural)
                tts_text = content.replace("Anna", "Ana")
                # generate() returns URL str on success or None on failure (no exception)
                result = await self._tts_service.generate(tts_text)
                if result is not None:
                    # Guardamos la URL que generate() devolvió — puede ser Cloudinary
                    # o local /audio/{md5}.mp3. Es confiable porque el archivo existe
                    # en el servidor cuando es local, o en Cloudinary cuando subió.
                    audio_url = result
                else:
                    logger.warning("TTS returned None — no audio file was generated")
            except Exception:
                logger.warning("TTS generation failed for outbound — continuing with text")

        async with self._session_maker() as session:
            notification = Notification(
                customer_id=prospect.customer.id,
                tipo="wpp",
                contenido=content,
                estado="pendiente",
                scheduled_at=datetime.utcnow(),
                audio_url=audio_url,
                opportunity_id=prospect.opportunity.id
                if prospect.opportunity
                else None,
            )
            session.add(notification)
            await session.commit()
            await session.refresh(notification)
            return notification

    async def process_reattempts(self) -> int:
        count = 0
        async with self._session_maker() as session:
            cutoff = datetime.utcnow() - timedelta(days=5)

            stmt = select(Notification).where(
                and_(
                    Notification.estado == "enviado",
                    Notification.sent_at.isnot(None),
                    Notification.sent_at < cutoff,
                    Notification.responded_at.is_(None),
                    Notification.intento_actual < Notification.max_intentos,
                )
            )
            result = await session.execute(stmt)
            sent_notifications = result.scalars().all()

            for original in sent_notifications:
                retry = Notification(
                    customer_id=original.customer_id,
                    tipo=original.tipo,
                    contenido=original.contenido,
                    estado="reintento",
                    scheduled_at=datetime.utcnow(),
                    intento_actual=original.intento_actual + 1,
                    max_intentos=original.max_intentos,
                    opportunity_id=original.opportunity_id,
                )
                session.add(retry)
                original.intento_actual += 1
                count += 1

            if count > 0:
                await session.commit()

        return count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_eligible_contract(customer: Customer) -> bool:
        if not customer.tipo_contrato or customer.antiguedad_meses is None:
            return False
        contrato = customer.tipo_contrato.lower()
        if "indefinido" in contrato:
            return customer.antiguedad_meses >= 2
        if any(kw in contrato for kw in ("fijo", "temporal", "termino")):
            return customer.antiguedad_meses >= 6
        # Contratos de prestación de servicios u obra/labor: requieren más
        # antigüedad porque son de duración determinada
        if any(kw in contrato for kw in ("prestacion", "servicios", "obra", "labor")):
            return customer.antiguedad_meses >= 12
        return False

    @staticmethod
    async def _has_product(
        session: AsyncSession, customer: Customer, product_type: str
    ) -> bool:
        if product_type == "seguro":
            result = await session.execute(
                select(Policy)
                .where(Policy.customer_id == customer.id)
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

        if product_type == "credito":
            result = await session.execute(
                select(Credit)
                .join(Application, Credit.application_id == Application.id)
                .where(Application.customer_id == customer.id)
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

        return False

    @staticmethod
    async def _has_recent_notification(
        session: AsyncSession, customer: Customer, cutoff: datetime
    ) -> bool:
        result = await session.execute(
            select(Notification)
            .where(
                Notification.customer_id == customer.id,
                Notification.created_at >= cutoff,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None