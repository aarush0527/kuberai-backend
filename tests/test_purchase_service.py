import asyncio
import os
import tempfile
import threading
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.models import Base
from app.price_provider import SimulatedPriceProvider, CachingPriceService
from app.services.common import get_or_create_user
from app.services.purchase_service import execute_purchase


# Bounds & precision — end to end through execute_purchase, asserting on real DB state (was a transaction actually created), not just reply text.


async def test_valid_odd_amount_executes_and_records_exact_values(db_session, make_user, price_service):
    make_user()
    outcome = await execute_purchase(db_session, "user_test1", "333.33", "corr-1", price_service)

    assert outcome.success is True
    assert outcome.transaction is not None
    assert Decimal(str(outcome.transaction.rupee_amount)) == Decimal("333.33")
    assert outcome.transaction.status == models.TransactionStatus.COMPLETED.value

    rows = db_session.query(models.Transaction).filter_by(user_id="user_test1").all()
    assert len(rows) == 1


async def test_below_minimum_is_rejected_no_transaction_created(db_session, make_user, price_service):
    make_user()
    outcome = await execute_purchase(db_session, "user_test1", "0.5", "corr-2", price_service)

    assert outcome.success is False
    assert outcome.reason_code == "AMOUNT_BELOW_MIN"
    assert db_session.query(models.Transaction).count() == 0


async def test_negative_amount_is_rejected(db_session, make_user, price_service):
    make_user()
    outcome = await execute_purchase(db_session, "user_test1", "-5000", "corr-3", price_service)

    assert outcome.success is False
    assert outcome.reason_code == "AMOUNT_NOT_POSITIVE"
    assert db_session.query(models.Transaction).count() == 0


async def test_absurdly_large_amount_is_rejected(db_session, make_user, price_service):
    make_user()
    outcome = await execute_purchase(db_session, "user_test1", "100000000000", "corr-4", price_service)

    assert outcome.success is False
    assert outcome.reason_code == "AMOUNT_ABOVE_MAX"
    assert db_session.query(models.Transaction).count() == 0


async def test_bad_precision_amount_is_rejected(db_session, make_user, price_service):
    make_user()
    outcome = await execute_purchase(db_session, "user_test1", "333.333", "corr-5", price_service)

    assert outcome.success is False
    assert outcome.reason_code == "AMOUNT_BAD_PRECISION"



# Price-source resilience


async def test_price_unavailable_rejects_purchase_no_transaction_created(db_session, make_user, price_service):
    make_user()
    price_service.provider.force_fail = True

    outcome = await execute_purchase(db_session, "user_test1", "500.00", "corr-6", price_service)

    assert outcome.success is False
    assert outcome.reason_code == "PRICE_UNAVAILABLE"
    assert db_session.query(models.Transaction).count() == 0



# Idempotency — the literal "same purchase request, sent twice" case.


async def test_same_purchase_request_sent_twice_charges_once(db_session, make_user, price_service):
    make_user()

    first = await execute_purchase(db_session, "user_test1", "500.00", "corr-7a", price_service)
    second = await execute_purchase(db_session, "user_test1", "500.00", "corr-7b", price_service)

    assert first.success is True and second.success is True
    assert second.deduped is True
    assert first.transaction.id == second.transaction.id

    rows = db_session.query(models.Transaction).filter_by(user_id="user_test1").all()
    assert len(rows) == 1  # charged exactly once


async def test_same_amount_after_dedup_window_is_a_new_legitimate_purchase(db_session, make_user, price_service, monkeypatch):
    make_user()
    import app.services.purchase_service as ps

    monkeypatch.setattr(ps.settings, "purchase_dedup_window_seconds", 1)

    first = await execute_purchase(db_session, "user_test1", "500.00", "corr-8a", price_service)
    await asyncio.sleep(1.1)
    second = await execute_purchase(db_session, "user_test1", "500.00", "corr-8b", price_service)

    assert first.success is True and second.success is True
    assert second.deduped is False
    assert first.transaction.id != second.transaction.id
    assert db_session.query(models.Transaction).filter_by(user_id="user_test1").count() == 2



# Real concurrency — two threads, separate sessions, same explicit
# idempotency key, fired together. Regardless of which one "wins" the
# race at the DB level, exactly one row must exist and both callers must
# get a consistent, successful result pointing at it.


def test_truly_concurrent_duplicate_purchase_results_in_exactly_one_transaction():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionFactory = sessionmaker(bind=engine)

        seed = SessionFactory()
        get_or_create_user(seed, "user_race")
        seed.close()

        barrier = threading.Barrier(2)
        results = []

        def worker():
            session = SessionFactory()
            provider = SimulatedPriceProvider(Decimal("14500.0000"))
            local_price_service = CachingPriceService(provider, cache_ttl_seconds=60, staleness_ceiling_seconds=600)
            barrier.wait()  # align both threads to fire as close together as possible
            outcome = asyncio.run(execute_purchase(
                session, "user_race", "500.00", "race-correlation",
                local_price_service, idempotency_key="race-key-fixed",
            ))

            txn_id = outcome.transaction.id if outcome.transaction else None
            results.append((outcome.success, txn_id))
            session.close()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 2
        assert all(success for success, _ in results)
        assert results[0][1] == results[1][1]

        verify = SessionFactory()
        rows = verify.query(models.Transaction).filter_by(idempotency_key="race-key-fixed").all()
        assert len(rows) == 1
        verify.close()
    finally:
        os.remove(path)
