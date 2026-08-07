from fastapi import APIRouter, Depends

from app.dependencies import get_price_service

router = APIRouter(tags=["price"])


@router.get("/price")
async def current_price(price_service=Depends(get_price_service)):
    quote = await price_service.get_price()
    return {
        "price_per_gram": str(quote.price_per_gram),
        "source": quote.source,
        "is_stale": quote.is_stale,
        "fetched_at": quote.fetched_at.isoformat(),
    }
