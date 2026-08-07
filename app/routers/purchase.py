from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_price_service
from app.serializers import purchase_outcome_to_response
from app.services.common import new_correlation_id
from app.services.purchase_service import execute_purchase

router = APIRouter(tags=["purchase"])


class PurchaseRequest(BaseModel):
    user_id: str

    amount: str
    idempotency_key: str | None = None


@router.post("/purchase")
async def purchase(req: PurchaseRequest, db: Session = Depends(get_db), price_service=Depends(get_price_service)):
    correlation_id = new_correlation_id()
    outcome = await execute_purchase(db, req.user_id, req.amount, correlation_id, price_service, req.idempotency_key)
    return purchase_outcome_to_response(outcome)
