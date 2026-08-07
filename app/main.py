import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import init_db
from app.llm.groq_client import GroqLLMClient
from app.llm.not_configured_client import NotConfiguredLLMClient
from app.logging_config import configure_logging
from app.price_provider import CachingPriceService, SimulatedPriceProvider
from app.routers import chat, debug, health, price, purchase, sip, users
from app.scheduler import scheduler_loop


def setup_price_service(app: FastAPI):
    provider = SimulatedPriceProvider(settings.price_base_inr_per_gram)

    app.state.price_provider = provider
    app.state.price_service = CachingPriceService(
        provider=provider,
        cache_ttl_seconds=settings.price_cache_ttl_seconds,
        staleness_ceiling_seconds=settings.price_staleness_ceiling_seconds,
    )


def setup_llm(app: FastAPI):
    if settings.groq_api_key:
        app.state.llm_client = GroqLLMClient()
        return

    logging.getLogger("startup").warning(
        "GROQ_API_KEY not configured. Chat endpoint will use fallback client."
    )
    app.state.llm_client = NotConfiguredLLMClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    init_db()

    setup_price_service(app)
    setup_llm(app)

    scheduler = asyncio.create_task(scheduler_loop(app))

    try:
        yield
    finally:
        scheduler.cancel()


app = FastAPI(
    title="Kuber.AI clone — Task 2 backend",
    lifespan=lifespan,
)

for router in (
    health.router,
    purchase.router,
    sip.router,
    debug.router,
    users.router,
    price.router,
    chat.router,
):
    app.include_router(router)