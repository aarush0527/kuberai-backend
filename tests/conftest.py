from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User
from app.price_provider import SimulatedPriceProvider, CachingPriceService


@pytest.fixture()
def db_session():

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def make_user(db_session):
    def _make(user_id: str = "user_test1", display_name: str = "Test User") -> User:
        user = User(id=user_id, display_name=display_name)
        db_session.add(user)
        db_session.commit()
        return user

    return _make


@pytest.fixture()
def price_service():
    provider = SimulatedPriceProvider(Decimal("14500.0000"))
    service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)
    service.provider = provider  # convenience handle for tests that need it
    return service
