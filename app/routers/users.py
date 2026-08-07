from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.dependencies import get_db

router = APIRouter(tags=["users"])


@router.get("/users/{user_id}/journey")
def user_journey(user_id: str, db: Session = Depends(get_db)):
    events = (
        db.query(models.Event)
        .filter_by(user_id=user_id)
        .order_by(models.Event.created_at)
        .all()
    )
    return [
        {
            "id": e.id,
            "correlation_id": e.correlation_id,
            "event_type": e.event_type,
            "payload": e.payload,
            "at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]
