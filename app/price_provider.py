"""
Gold price source

Decision: default to a SIMULATED feed rather than a live third-party API.

Policy: short-TTL cache (60s default) for the happy path; on a fetch
failure, fall back to the cached price ONLY if it's younger than a hard
staleness ceiling (10 min default); beyond that, fail safe — no purchase
ever executes against a price we can no longer vouch for.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


class PriceUnavailableError(Exception):
    pass


@dataclass
class PriceQuote:
    price_per_gram: Decimal
    fetched_at: datetime
    source: str
    is_stale: bool = False


class PriceProvider(ABC):
    @abstractmethod
    async def fetch(self) -> Decimal:

        ...


class SimulatedPriceProvider(PriceProvider):

    name = "simulated"

    def __init__(self, base_price: Decimal):
        self._price = base_price
        self.force_fail = False

    async def fetch(self) -> Decimal:
        if self.force_fail:
            raise PriceUnavailableError("simulated price source outage (forced)")

        drift_pct = Decimal(str(random.uniform(-0.5, 0.5))) / Decimal(100)
        next_price = self._price * (Decimal("1") + drift_pct)
        next_price = next_price.quantize(Decimal("0.0001"))
        if next_price <= 0:
            next_price = Decimal("1.0000")
        self._price = next_price
        return self._price


class CachingPriceService:

    def __init__(self, provider: PriceProvider, cache_ttl_seconds: int, staleness_ceiling_seconds: int):
        self._provider = provider
        self._cache_ttl = cache_ttl_seconds
        self._staleness_ceiling = staleness_ceiling_seconds
        self._cached: PriceQuote | None = None

    async def get_price(self) -> PriceQuote:
        now = datetime.now(timezone.utc)

        if self._cached is not None and (now - self._cached.fetched_at).total_seconds() < self._cache_ttl:
            return self._cached

        try:
            price = await self._provider.fetch()
        except PriceUnavailableError:
            return self._fall_back_to_cache(now)

        quote = PriceQuote(price_per_gram=price, fetched_at=now, source=self._provider.name, is_stale=False)
        self._cached = quote
        return quote

    def clear_cache(self) -> None:
  
        self._cached = None

    def _fall_back_to_cache(self, now: datetime) -> PriceQuote:
        if self._cached is not None:
            age = (now - self._cached.fetched_at).total_seconds()
            if age < self._staleness_ceiling:
                return PriceQuote(
                    price_per_gram=self._cached.price_per_gram,
                    fetched_at=self._cached.fetched_at,
                    source=self._cached.source,
                    is_stale=True,
                )
        raise PriceUnavailableError("price source unreachable and no usable cached price")
