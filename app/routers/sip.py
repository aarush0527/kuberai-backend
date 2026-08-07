from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.dependencies import get_db
from app.serializers import sip_outcome_to_response, sip_to_dict
from app.services.common import new_correlation_id
from app.services.sip_service import create_sip, pause_sip, resume_sip, cancel_sip

router = APIRouter(tags=["sip"])


class SIPCreateRequest(BaseModel):
    user_id: str
    amount: str
    frequency: str 
    start_date: date | None = None  


class SIPActionRequest(BaseModel):
    user_id: str

    sip_id: str | None = None


@router.post("/sip")
def create_sip_endpoint(req: SIPCreateRequest, db: Session = Depends(get_db)):
    correlation_id = new_correlation_id()
    start = req.start_date or date.today()
    outcome = create_sip(db, req.user_id, req.amount, req.frequency, start, correlation_id)
    return sip_outcome_to_response(outcome)


@router.patch("/sip/pause")
def pause_sip_endpoint(req: SIPActionRequest, db: Session = Depends(get_db)):
    correlation_id = new_correlation_id()
    outcome = pause_sip(db, req.user_id, req.sip_id, correlation_id)
    return sip_outcome_to_response(outcome)


@router.patch("/sip/resume")
def resume_sip_endpoint(req: SIPActionRequest, db: Session = Depends(get_db)):
    correlation_id = new_correlation_id()
    outcome = resume_sip(db, req.user_id, req.sip_id, correlation_id)
    return sip_outcome_to_response(outcome)


@router.post("/sip/cancel")
def cancel_sip_endpoint(req: SIPActionRequest, db: Session = Depends(get_db)):
    correlation_id = new_correlation_id()
    outcome = cancel_sip(db, req.user_id, req.sip_id, correlation_id)
    return sip_outcome_to_response(outcome)


@router.get("/users/{user_id}/sips")
def list_user_sips(user_id: str, db: Session = Depends(get_db)):
    sips = db.query(models.SIP).filter_by(user_id=user_id).order_by(models.SIP.created_at).all()
    return [sip_to_dict(s) for s in sips]
