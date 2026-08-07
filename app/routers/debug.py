from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_price_service, get_price_provider
from app.services.sip_service import execute_due_installments

router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/price-source/fail")
def toggle_price_failure(
    enabled: bool = True,
    provider=Depends(get_price_provider),
    price_service=Depends(get_price_service),
):
    provider.force_fail = enabled

    price_service.clear_cache()
    return {"force_fail": provider.force_fail}


@router.post("/scheduler/tick")
async def manual_scheduler_tick(db: Session = Depends(get_db), price_service=Depends(get_price_service)):
    results = await execute_due_installments(db, price_service)
    return {"processed": len(results), "results": results}
