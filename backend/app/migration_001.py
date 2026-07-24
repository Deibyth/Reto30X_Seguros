"""Migration 001 — Add outbound scheduling columns to notifications table.

The Notification model was extended with scheduling/delivery fields but the
actual SQLite table was never migrated. This adds the missing columns.
"""

import asyncio
import logging
import sys

from sqlalchemy import text

import app.database as db
from app.config import Settings

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger("migration_001")


async def migrate() -> None:
    settings = Settings()
    db.init_engine(settings.database_url, echo=False)

    async with db.engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(
            text("PRAGMA table_info(notifications)")
        )
        columns = {row[1] for row in result.fetchall()}

        additions = []

        if "scheduled_at" not in columns:
            additions.append(
                "ALTER TABLE notifications ADD COLUMN scheduled_at DATETIME"
            )
        if "sent_at" not in columns:
            additions.append(
                "ALTER TABLE notifications ADD COLUMN sent_at DATETIME"
            )
        if "responded_at" not in columns:
            additions.append(
                "ALTER TABLE notifications ADD COLUMN responded_at DATETIME"
            )
        if "error_log" not in columns:
            additions.append(
                "ALTER TABLE notifications ADD COLUMN error_log TEXT"
            )
        if "intento_actual" not in columns:
            additions.append(
                "ALTER TABLE notifications ADD COLUMN intento_actual INTEGER NOT NULL DEFAULT 0"
            )
        if "max_intentos" not in columns:
            additions.append(
                "ALTER TABLE notifications ADD COLUMN max_intentos INTEGER NOT NULL DEFAULT 1"
            )
        if "opportunity_id" not in columns:
            additions.append(
                "ALTER TABLE notifications ADD COLUMN opportunity_id VARCHAR(36) REFERENCES opportunities(id)"
            )
        if "audio_url" not in columns:
            additions.append(
                "ALTER TABLE notifications ADD COLUMN audio_url VARCHAR(500)"
            )

        if not additions:
            logger.info("✅ All columns already exist — nothing to do")
            return

        for stmt in additions:
            logger.info("  ➕ %s", stmt.split("ADD COLUMN")[1].strip())
            await conn.execute(text(stmt))

        logger.info("✅ Migration applied: %d column(s) added", len(additions))

    await db.dispose_engine()


if __name__ == "__main__":
    asyncio.run(migrate())
