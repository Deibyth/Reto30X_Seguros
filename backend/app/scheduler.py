"""APScheduler integration for outbound proactive messaging."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class OutboundScheduler:
    """Manages the outbound messaging background job via APScheduler."""

    def __init__(
        self,
        outbound_service,
        interval_minutes: int = 15,
    ):
        self._service = outbound_service
        self._scheduler = AsyncIOScheduler()
        self._interval = interval_minutes

    def start(self):
        self._scheduler.add_job(
            self._run_outbound,
            trigger=IntervalTrigger(minutes=self._interval),
            id="outbound_job",
            name="Proactive outbound messaging",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Outbound scheduler started (interval=%d min)", self._interval)

    async def run_once(self):
        """Run the outbound pipeline once immediately (used at startup)."""
        logger.info("Outbound scheduler: running first cycle immediately")
        await self._run_outbound()

    async def stop(self):
        self._scheduler.shutdown(wait=False)
        logger.info("Outbound scheduler stopped")

    async def _run_outbound(self):
        """Run the full outbound pipeline: select → generate → notify."""
        try:
            prospects = await self._service.select_prospects(limit=50)
            if not prospects:
                logger.info("Outbound job: no eligible prospects found")
            else:
                count = 0
                for prospect in prospects:
                    try:
                        content = await self._service.generate_message(prospect)
                        await self._service.create_notification(prospect, content)
                        count += 1
                    except Exception as e:
                        logger.error(
                            "Outbound job: failed for customer %s: %s",
                            prospect.customer.id, e,
                        )
                        continue

                logger.info(
                    "Outbound job: %d new notifications created", count
                )

            # Process re-attempts
            try:
                reattempt_count = await self._service.process_reattempts()
                if reattempt_count > 0:
                    logger.info(
                        "Outbound job: %d re-attempt records created",
                        reattempt_count,
                    )
            except Exception as e:
                logger.error(
                    "Outbound job: reattempt processing failed: %s", e
                )
        except Exception as e:
            logger.error("Outbound job failed: %s", e)
