import uuid

from sqlalchemy.orm import Session

from app import models


def new_correlation_id() -> str:

    return uuid.uuid4().hex[:16]


def get_or_create_user(db: Session, user_id: str, display_name: str | None = None) -> models.User:

    user = db.get(models.User, user_id)
    if user is None:
        user = models.User(id=user_id, display_name=display_name or user_id)
        db.add(user)
        db.commit()
    return user
