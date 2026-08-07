from fastapi import Request

from app.db import get_db  # re-exported for convenient single import point
from app.llm.base import LLMClient
from app.price_provider import CachingPriceService, SimulatedPriceProvider


def get_price_service(request: Request) -> CachingPriceService:
    return request.app.state.price_service


def get_price_provider(request: Request) -> SimulatedPriceProvider:
    return request.app.state.price_provider


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client


__all__ = ["get_db", "get_price_service", "get_price_provider", "get_llm_client"]
