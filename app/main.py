from fastapi import FastAPI

from app.db import init_db
from app.price_provider import (
    SimulatedPriceProvider,
    CachingPriceService,
)


app = FastAPI(title="AurumFlow")


@app.on_event("startup")
def startup():
    init_db()

    provider = SimulatedPriceProvider()

    app.state.price_provider = provider
    app.state.price_service = CachingPriceService(provider)


@app.get("/")
def root():
    return {
        "message": "AurumFlow backend is running"
    }