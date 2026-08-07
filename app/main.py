import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import init_db
from app.llm.groq_client import GroqLLMClient
from app.llm.not_configured_client import NotConfiguredLLMClient
from app.logging_config import configure_logging
from app.price_provider import SimulatedPriceProvider, CachingPriceService
from app.scheduler import scheduler_loop
from app.routers import health, purchase, sip, debug, users, price, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    init_db()

    provider = SimulatedPriceProvider(settings.price_base_inr_per_gram)
    app.state.price_provider = provider
    app.state.price_service = CachingPriceService(
        provider,
        cache_ttl_seconds=settings.price_cache_ttl_seconds,
        staleness_ceiling_seconds=settings.price_staleness_ceiling_seconds,
    )

    if settings.groq_api_key:
        app.state.llm_client = GroqLLMClient()
    else:
        logging.getLogger("startup").warning(
            "GROQ_API_KEY not set — /chat will respond with a not-configured "
            "message; every other endpoint works normally."
        )
        app.state.llm_client = NotConfiguredLLMClient()

    scheduler_task = asyncio.create_task(scheduler_loop(app))
    try:
        yield
    finally:
        scheduler_task.cancel()


app = FastAPI(title="Kuber.AI clone \u2014 Task 2 backend", lifespan=lifespan)

app.include_router(health.router)
app.include_router(purchase.router)
app.include_router(sip.router)
app.include_router(debug.router)
app.include_router(users.router)
app.include_router(price.router)
app.include_router(chat.router)
