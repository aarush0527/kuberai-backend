from decimal import Decimal

import pytest
from freezegun import freeze_time

from app.price_provider import (
    PriceProvider,
    PriceUnavailableError,
    SimulatedPriceProvider,
    CachingPriceService,
)


class ScriptedProvider(PriceProvider):
  

    name = "scripted"

    def __init__(self, script: list):
        self._script = list(script)
        self.call_count = 0

    async def fetch(self) -> Decimal:
        self.call_count += 1
        result = self._script.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


async def test_fresh_fetch_returns_price_and_marks_not_stale():
    provider = ScriptedProvider([Decimal("14500.0000")])
    service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)

    quote = await service.get_price()

    assert quote.price_per_gram == Decimal("14500.0000")
    assert quote.is_stale is False
    assert provider.call_count == 1


async def test_within_ttl_serves_cache_without_refetching():
    provider = ScriptedProvider([Decimal("14500.0000"), Decimal("99999.0000")])
    service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)

    with freeze_time("2026-08-05 12:00:00"):
        first = await service.get_price()

    with freeze_time("2026-08-05 12:00:10"):  # +10s, inside the 60s TTL
        second = await service.get_price()

    assert first.price_per_gram == second.price_per_gram == Decimal("14500.0000")
    assert provider.call_count == 1  # provider was never called a second time


async def test_after_ttl_expiry_refetches():
    provider = ScriptedProvider([Decimal("14500.0000"), Decimal("14550.0000")])
    service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)

    with freeze_time("2026-08-05 12:00:00"):
        await service.get_price()

    with freeze_time("2026-08-05 12:02:00"):  # +120s, past the 60s TTL
        second = await service.get_price()

    assert second.price_per_gram == Decimal("14550.0000")
    assert provider.call_count == 2


async def test_failure_within_staleness_ceiling_serves_stale_cache():
    provider = ScriptedProvider([Decimal("14500.0000"), PriceUnavailableError("outage")])
    service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)

    with freeze_time("2026-08-05 12:00:00"):
        await service.get_price()  

    with freeze_time("2026-08-05 12:03:00"):  # +180s: past TTL, inside 600s ceiling
        quote = await service.get_price()

    assert quote.is_stale is True
    assert quote.price_per_gram == Decimal("14500.0000")


def _has_no_usable_price(quote_or_error):
    return isinstance(quote_or_error, PriceUnavailableError)


async def test_failure_beyond_staleness_ceiling_fails_safe_no_stale_price_used():
    provider = ScriptedProvider([Decimal("14500.0000"), PriceUnavailableError("still down")])
    service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)

    with freeze_time("2026-08-05 12:00:00"):
        await service.get_price()

    with freeze_time("2026-08-05 12:15:00"):  # +900s: past the 600s ceiling
        with pytest.raises(PriceUnavailableError):
            await service.get_price()


async def test_immediate_failure_with_no_prior_cache_raises():
    provider = ScriptedProvider([PriceUnavailableError("down from the start")])
    service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)

    with pytest.raises(PriceUnavailableError):
        await service.get_price()


async def test_clear_cache_makes_forced_outage_immediately_observable():
    provider = ScriptedProvider([Decimal("14500.0000")])
    service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)

    await service.get_price()  # primes a fresh cache entry
    provider._script = [PriceUnavailableError("forced")]

    service.clear_cache()

    with pytest.raises(PriceUnavailableError):
        await service.get_price()


async def test_simulated_provider_force_fail_toggle():
    provider = SimulatedPriceProvider(Decimal("14500.0000"))
    provider.force_fail = True

    with pytest.raises(PriceUnavailableError):
        await provider.fetch()

    provider.force_fail = False
    price = await provider.fetch() 
    assert price > 0


async def test_simulated_provider_produces_positive_bounded_moving_price():
    provider = SimulatedPriceProvider(Decimal("14500.0000"))
    p1 = await provider.fetch()
    p2 = await provider.fetch()
    assert p1 > 0 and p2 > 0
    assert abs(p2 - p1) / p1 < Decimal("0.01") 
