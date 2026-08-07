from fastapi import FastAPI

from app.config import settings
from app.db import init_db
from app.price_provider import (
    SimulatedPriceProvider,
    CachingPriceService,
)

app = FastAPI(title="AurumFlow")


@app.on_event("startup")
def startup():
    init_db()

    provider = SimulatedPriceProvider(
        settings.price_base_inr_per_gram
    )

    app.state.price_provider = provider
    app.state.price_service = CachingPriceService(
        provider,
        cache_ttl_seconds=settings.price_cache_ttl_seconds,
        staleness_ceiling_seconds=settings.price_staleness_ceiling_seconds,
    )


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "AurumFlow backend is running",
    }