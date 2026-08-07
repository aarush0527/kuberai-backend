from sqlalchemy.orm import Session

from app import models
from app.logging_config import audit_logger


def build_event(
    db: Session,
    user_id: str | None,
    correlation_id: str,
    event_type: str,
    payload: dict,
) -> models.Event:

    evt = models.Event(
        user_id=user_id,
        correlation_id=correlation_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(evt)
    audit_logger().info(
        event_type,
        extra={
            "extra_fields": {
                "user_id": user_id,
                "correlation_id": correlation_id,
                "event_type": event_type,
                "payload": payload,
            }
        },
    )
    return evt


def log_event_now(
    db: Session,
    user_id: str | None,
    correlation_id: str,
    event_type: str,
    payload: dict,
) -> models.Event:

    evt = build_event(db, user_id, correlation_id, event_type, payload)
    db.commit()
    return evt
