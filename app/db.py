import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Base

if settings.database_url.startswith("sqlite:///"):
    raw_path = settings.database_url[len("sqlite:///"):]
    if raw_path != ":memory:":
        db_dir = os.path.dirname(raw_path) or "."
        os.makedirs(db_dir, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
