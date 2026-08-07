import asyncio
import logging

from app.config import settings
from app.db import SessionLocal
from app.services.sip_service import execute_due_installments

logger = logging.getLogger("scheduler")


async def scheduler_loop(app) -> None:
    while True:
        await asyncio.sleep(settings.scheduler_poll_interval_seconds)
        db = SessionLocal()
        try:
            results = await execute_due_installments(db, app.state.price_service)
            if results:
                logger.info(
                    "scheduler tick processed installments",
                    extra={"extra_fields": {"count": len(results), "results": results}},
                )
        except Exception:
            logger.exception("scheduler tick failed")
        finally:
            db.close()
